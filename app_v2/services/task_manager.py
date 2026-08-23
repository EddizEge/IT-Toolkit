from __future__ import annotations

import json
import locale
import os
import re
import subprocess
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from app_v2.registry import ACTION_LOOKUP, TOGGLE_LOOKUP
from app_v2.services.action_safety import (
    ExecutionPlan,
    build_undo_plan,
    execution_plan_for_action,
    execution_plan_for_toggle,
    expected_undo_key,
)
from app_v2.services.audit_log import AuditLog
from app_v2.services.command_runner import (
    CREATE_NO_WINDOW,
    create_command_script,
    is_running_as_admin,
    remove_command_script,
    run_command,
    trusted_system_executable,
)
from app_v2.services.recovery import (
    restore_point_failure_message,
    restore_point_process,
)
from app_v2.services.settings_service import get_toggle_status
from app_v2.services.undo_execution import (
    PROTECTED_ACTION_KEYS,
    protected_action_process,
    registered_process_failure_message,
    undo_process,
)

ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {
    "succeeded",
    "failed",
    "cancelled",
    "interrupted",
    "delegated",
}
OUTPUT_LIMIT = 200_000
HISTORY_LIMIT = 100
PROGRESS_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\s*%")
PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
ACTION_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.-]{0,127}$")
UNDO_STATES = {"none", "available", "running", "completed", "unknown"}
RESTORE_POINT_STATUSES = {
    "not_applicable",
    "skipped",
    "created",
    "failed_override",
}
NORMAL_PROCESS_EXIT = QProcess.ExitStatus.NormalExit


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_history_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return root / "IT Toolkit" / "task_history.json"


def status_text(status: str) -> str:
    return {
        "queued": "Sırada",
        "running": "Çalışıyor",
        "succeeded": "Tamamlandı",
        "failed": "Başarısız",
        "cancelled": "İptal edildi",
        "interrupted": "Yarım kaldı",
        "delegated": "Harici görev",
    }.get(status, status)


@dataclass
class TaskRecord:
    id: str
    title: str
    command: str
    category: str
    status: str = "queued"
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    output: str = ""
    message: str = ""
    exit_code: int | None = None
    progress: int | None = None
    admin: bool = False
    cancellable: bool = True
    plan_id: str = ""
    action_key: str = ""
    risk: str = "normal"
    audit_result_recorded: bool = False
    parent_plan_id: str = ""
    undo_key: str = ""
    undo_state: str = "none"
    restore_point_status: str = "not_applicable"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> TaskRecord:
        allowed = cls.__dataclass_fields__
        payload = {
            key: item for key, item in value.items() if key in allowed
        }
        for field_name in ("id", "title", "command", "category", "created_at"):
            if not isinstance(payload.get(field_name), str):
                raise TypeError(f"Geçersiz görev geçmişi alanı: {field_name}")
        if not ACTION_KEY_PATTERN.fullmatch(str(payload["id"])):
            raise ValueError("Geçersiz görev kimliği.")
        status = payload.get("status", "queued")
        if status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
            raise ValueError("Geçersiz görev durumu.")
        payload["status"] = status
        for field_name in ("started_at", "finished_at"):
            field_value = payload.get(field_name)
            if field_value is not None and not isinstance(field_value, str):
                raise ValueError(f"Geçersiz görev geçmişi alanı: {field_name}")
        for field_name in ("output", "message"):
            field_value = payload.get(field_name, "")
            if not isinstance(field_value, str):
                raise TypeError(f"Geçersiz görev geçmişi alanı: {field_name}")
            payload[field_name] = field_value
        exit_code = payload.get("exit_code")
        if exit_code is not None and (
            isinstance(exit_code, bool) or not isinstance(exit_code, int)
        ):
            raise ValueError("Geçersiz görev çıkış kodu.")
        progress = payload.get("progress")
        if progress is not None and (
            isinstance(progress, bool)
            or not isinstance(progress, int)
            or not 0 <= progress <= 100
        ):
            raise ValueError("Geçersiz görev ilerlemesi.")
        for field_name, default in (
            ("admin", False),
            ("cancellable", True),
            ("audit_result_recorded", False),
        ):
            field_value = payload.get(field_name, default)
            if not isinstance(field_value, bool):
                raise TypeError(f"Geçersiz görev geçmişi alanı: {field_name}")
            payload[field_name] = field_value
        plan_id = payload.get("plan_id", "")
        if not isinstance(plan_id, str) or not PLAN_ID_PATTERN.fullmatch(plan_id):
            payload["plan_id"] = ""
        action_key = payload.get("action_key", "")
        if (
            not isinstance(action_key, str)
            or not action_key
            or not ACTION_KEY_PATTERN.fullmatch(action_key)
        ):
            payload["action_key"] = ""
        if (
            not payload["plan_id"]
            or not payload["action_key"]
            or not PLAN_ID_PATTERN.fullmatch(str(payload["id"]))
        ):
            payload["plan_id"] = ""
            payload["action_key"] = ""
            payload["audit_result_recorded"] = False
        parent_plan_id = payload.get("parent_plan_id", "")
        if (
            not isinstance(parent_plan_id, str)
            or (
                parent_plan_id
                and (
                    not PLAN_ID_PATTERN.fullmatch(parent_plan_id)
                    or parent_plan_id == payload["plan_id"]
                )
            )
        ):
            parent_plan_id = ""
        payload["parent_plan_id"] = parent_plan_id
        undo_key = payload.get("undo_key", "")
        if (
            not isinstance(undo_key, str)
            or (undo_key and not ACTION_KEY_PATTERN.fullmatch(undo_key))
            or (
                undo_key
                and expected_undo_key(str(payload["action_key"])) != undo_key
            )
        ):
            undo_key = ""
        payload["undo_key"] = undo_key
        undo_state = payload.get("undo_state", "none")
        if undo_state not in UNDO_STATES:
            undo_state = "none"
        payload["undo_state"] = undo_state
        restore_status = payload.get(
            "restore_point_status",
            "not_applicable",
        )
        if restore_status not in RESTORE_POINT_STATUSES:
            restore_status = "not_applicable"
        payload["restore_point_status"] = restore_status
        if not payload["plan_id"]:
            payload["parent_plan_id"] = ""
            payload["undo_key"] = ""
            payload["undo_state"] = "none"
            payload["restore_point_status"] = "not_applicable"
        if not payload["undo_key"]:
            payload["undo_state"] = "none"
        if payload["parent_plan_id"] and not (
            str(payload["action_key"]).startswith("undo:")
            or payload["action_key"] == "restore_point"
        ):
            payload["parent_plan_id"] = ""
        risk = payload.get("risk", "normal")
        if risk not in {"normal", "caution", "danger"}:
            payload["risk"] = "normal"
        return cls(**payload)


class TaskManager(QObject):
    task_added = Signal(object)
    task_updated = Signal(object)
    output_added = Signal(str, str)
    counts_changed = Signal(int, int, int)
    history_cleared = Signal()
    notification = Signal(str, str, str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        history_path: Path | None = None,
        script_directory: Path | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        super().__init__(parent)
        self.history_path = history_path or _default_history_path()
        self.script_directory = script_directory
        self.audit_log = audit_log or AuditLog()
        self._tasks: list[TaskRecord] = []
        self._processes: dict[str, QProcess] = {}
        self._script_paths: dict[str, Path] = {}
        self._killers: list[QProcess] = []
        self._success_codes: dict[str, set[int]] = {}
        self._cancel_requested: set[str] = set()
        self._audit_results = self.audit_log.result_events_by_task()
        self._audited_terminal_tasks = set(self._audit_results)
        self._audit_retry_timers: dict[str, QTimer] = {}
        self._audit_retry_attempts: dict[str, int] = {}
        self._active_restore_task_id = ""
        self._shutting_down = False
        self._load_history()

    @property
    def tasks(self) -> tuple[TaskRecord, ...]:
        return tuple(self._tasks)

    def task(self, task_id: str) -> TaskRecord | None:
        return next((item for item in self._tasks if item.id == task_id), None)

    def invalidate_undo(self, task_id: str) -> bool:
        """Durum kayması görülen geri alma kaydını güvenli biçimde kapat."""

        task = self.task(task_id)
        if (
            task is None
            or task.status != "succeeded"
            or task.undo_state != "available"
        ):
            return False
        task.undo_state = "unknown"
        self._task_changed(task)
        return True

    def start_command(
        self,
        title: str,
        command: str,
        *,
        category: str = "Genel",
        admin: bool = False,
        keep_open: bool = False,
        success_codes: Iterable[int] = (0,),
        plan_id: str = "",
        action_key: str = "",
        risk: str = "normal",
        parent_plan_id: str = "",
        undo_key: str = "",
        restore_point_status: str = "not_applicable",
    ) -> TaskRecord:
        self._ensure_accepting_tasks()
        self._validate_recovery_context(
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id=parent_plan_id,
            undo_key=undo_key,
            restore_point_status=restore_point_status,
        )
        if parent_plan_id:
            raise ValueError(
                "Geri alma görevleri yalnız doğrulanmış geri alma planıyla "
                "başlatılabilir."
            )
        if action_key in PROTECTED_ACTION_KEYS:
            raise ValueError(
                "Korumalı eylem yalnız doğrulanmış dosyasız yürütücüyle "
                "başlatılabilir."
            )
        self._ensure_unique_plan_id(plan_id)
        return self._start_command_task(
            title,
            command,
            category=category,
            admin=admin,
            keep_open=keep_open,
            success_codes=success_codes,
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id="",
            undo_key=undo_key,
            restore_point_status=restore_point_status,
        )

    def start_undo(self, plan: ExecutionPlan) -> TaskRecord:
        """Merkezi kayıttan yeniden üretilen tek kullanımlık geri almayı başlat."""

        self._ensure_accepting_tasks()
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("Geri alma için geçerli bir işlem planı gerekir.")
        if not plan.parent_plan_id:
            raise ValueError("Geri alma planının üst işlem kimliği eksik.")
        parent = self._find_undo_parent(plan.parent_plan_id)
        if parent is None:
            raise ValueError("Geri alınabilir üst işlem bulunamadı.")
        expected = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        if expected is None or not self._plan_semantics_match(plan, expected):
            raise ValueError(
                "Geri alma planı merkezi güvenli kayıtla eşleşmiyor."
            )
        self._ensure_unique_plan_id(plan.plan_id)
        self._validate_recovery_context(
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            risk=plan.impact.risk,
            parent_plan_id=plan.parent_plan_id,
            undo_key=plan.impact.recovery.undo_key,
            restore_point_status="not_applicable",
        )
        elevated = plan.admin_required and not is_running_as_admin()
        try:
            program, arguments = undo_process(
                parent.action_key,
                parent.undo_key,
                elevated=elevated,
            )
        except OSError as exc:
            raise ValueError(
                "Güvenilir Windows geri alma bileşeni doğrulanamadı."
            ) from exc
        parent = self._reserve_undo_parent(
            plan.parent_plan_id,
            plan.action_key,
        )
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=plan.title,
            command=plan.command,
            category=plan.category,
            created_at=_now(),
            admin=plan.admin_required,
            cancellable=not elevated,
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            risk=plan.impact.risk,
            parent_plan_id=plan.parent_plan_id,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self.task_updated.emit(parent)
        self._emit_counts()
        self._start_program_task(
            task,
            program,
            arguments,
            success_codes=plan.success_codes,
        )
        return task

    def start_protected_action(
        self,
        plan: ExecutionPlan,
        *,
        restore_point_status: str,
    ) -> TaskRecord:
        """Restore kapsamındaki kritik eylemi dosyasız izin listesinden başlat."""

        self._ensure_accepting_tasks()
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("Korumalı eylem için geçerli işlem planı gerekir.")
        if plan.parent_plan_id or plan.action_key not in PROTECTED_ACTION_KEYS:
            raise ValueError("İşlem dosyasız korumalı eylem listesinde değil.")

        if plan.action_key == "rdp":
            _page_key, action = ACTION_LOOKUP["rdp"]
            expected = execution_plan_for_action(action)
        else:
            parts = plan.action_key.split(":")
            enabled = parts[2] == "on"
            toggle = TOGGLE_LOOKUP.get(parts[1])
            if toggle is None:
                raise ValueError("Korumalı ayar kaydı bulunamadı.")
            expected = execution_plan_for_toggle(
                toggle,
                enabled,
                previous_enabled=not enabled,
            )
        if not self._plan_semantics_match(plan, expected):
            raise ValueError(
                "Korumalı işlem planı merkezi güvenli kayıtla eşleşmiyor."
            )
        allowed_restore_statuses = (
            {"skipped", "created", "failed_override"}
            if plan.impact.recovery.restore_point_mode == "optional"
            else {"not_applicable"}
        )
        if restore_point_status not in allowed_restore_statuses:
            raise ValueError("Korumalı işlem geri yükleme durumu tutarsız.")
        self._validate_recovery_context(
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            risk=plan.impact.risk,
            parent_plan_id="",
            undo_key=plan.impact.recovery.undo_key,
            restore_point_status=restore_point_status,
        )
        self._ensure_unique_plan_id(plan.plan_id)
        elevated = plan.admin_required and not is_running_as_admin()
        try:
            program, arguments = protected_action_process(
                plan.action_key,
                elevated=elevated,
            )
        except OSError as exc:
            raise ValueError(
                "Güvenilir Windows işlem bileşeni doğrulanamadı."
            ) from exc

        undo_key = plan.impact.recovery.undo_key
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=plan.title,
            command=plan.command,
            category=plan.category,
            created_at=_now(),
            admin=plan.admin_required,
            cancellable=not elevated,
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            risk=plan.impact.risk,
            undo_key=undo_key,
            undo_state="available" if undo_key else "none",
            restore_point_status=restore_point_status,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self._emit_counts()
        self._start_program_task(
            task,
            program,
            arguments,
            success_codes=plan.success_codes,
        )
        return task

    def _start_command_task(
        self,
        title: str,
        command: str,
        *,
        category: str,
        admin: bool,
        keep_open: bool,
        success_codes: Iterable[int],
        plan_id: str,
        action_key: str,
        risk: str,
        parent_plan_id: str,
        undo_key: str,
        restore_point_status: str,
        parent_task: TaskRecord | None = None,
    ) -> TaskRecord:
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=title,
            command=command,
            category=category,
            created_at=_now(),
            admin=admin,
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id=parent_plan_id,
            undo_key=undo_key,
            undo_state="available" if undo_key else "none",
            restore_point_status=restore_point_status,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self._emit_counts()
        if parent_task:
            self.task_updated.emit(parent_task)

        if not command.strip():
            self._finish_immediately(
                task,
                False,
                "Çalıştırılacak komut bulunamadı.",
            )
            return task

        if admin and not is_running_as_admin():
            task.cancellable = False
            ok, message = run_command(
                command,
                admin=True,
                keep_open=keep_open,
            )
            if ok:
                task.status = "delegated"
                task.message = (
                    "İşlem yönetici penceresine devredildi. Güvenlik sınırı nedeniyle "
                    "canlı çıktı ve tamamlanma durumu uygulamaya aktarılamaz."
                )
                task.output = f"{message}\n{task.message}\n"
                task.progress = 100
                task.finished_at = _now()
                self.notification.emit(
                    task.title,
                    "Yönetici penceresinde başlatıldı.",
                    "warning",
                )
                self._record_audit("delegated", task)
            else:
                task.status = "failed"
                task.message = message
                task.output = f"{message}\n"
                task.progress = 0
                task.finished_at = _now()
                self.notification.emit(task.title, message, "danger")
            self._commit_terminal(task)
            return task

        try:
            command_program = trusted_system_executable("cmd.exe")
        except (OSError, ValueError):
            self._finish_immediately(
                task,
                False,
                "Güvenilir Windows komut işlemcisi doğrulanamadı.",
            )
            return task
        self._success_codes[task.id] = set(success_codes)
        try:
            script_path = create_command_script(
                command,
                directory=self.script_directory,
            )
        except OSError as exc:
            self._success_codes.pop(task.id, None)
            self._finish_immediately(
                task,
                False,
                f"Görev dosyası oluşturulamadı: {exc}",
            )
            return task

        self._start_program_task(
            task,
            command_program,
            ("/d", "/c", os.fspath(script_path)),
            success_codes=success_codes,
            script_path=script_path,
        )
        return task

    def _start_program_task(
        self,
        task: TaskRecord,
        program: str,
        arguments: Iterable[str],
        *,
        success_codes: Iterable[int],
        script_path: Path | None = None,
    ) -> None:
        self._success_codes[task.id] = set(success_codes)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setProgram(program)
        process.setArguments(list(arguments))
        program_directory = os.path.dirname(program)
        if os.path.isabs(program) and program_directory:
            process.setWorkingDirectory(program_directory)
        process.started.connect(lambda task_id=task.id: self._on_started(task_id))
        process.readyReadStandardOutput.connect(
            lambda task_id=task.id: self._read_output(task_id)
        )
        process.errorOccurred.connect(
            lambda error, task_id=task.id: self._on_error(task_id, error)
        )
        process.finished.connect(
            lambda code, exit_status, task_id=task.id: self._on_finished(
                task_id,
                code,
                exit_status,
            )
        )
        if script_path is not None:
            self._script_paths[task.id] = script_path
        self._processes[task.id] = process
        process.start()
        self._save_history()

    def start_restore_point(
        self,
        title: str,
        *,
        parent_plan_id: str,
        parent_action_key: str,
        risk: str,
    ) -> TaskRecord:
        self._ensure_accepting_tasks()
        self._validate_recovery_context(
            plan_id=parent_plan_id,
            action_key=parent_action_key,
            risk=risk,
            parent_plan_id="",
            undo_key="",
            restore_point_status="not_applicable",
        )
        child_plan_id = uuid.uuid4().hex
        self._ensure_unique_plan_id(child_plan_id)
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=f"Geri yükleme noktası: {title}",
            command="registered:restore_point",
            category="İşlem güvenliği",
            created_at=_now(),
            admin=True,
            cancellable=False,
            plan_id=child_plan_id,
            parent_plan_id=parent_plan_id,
            action_key="restore_point",
            risk=risk,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self._emit_counts()

        try:
            prepared = self.audit_log.record(
                "prepared",
                plan_id=task.plan_id,
                parent_plan_id=task.parent_plan_id,
                action_key=task.action_key,
                title=task.title,
                category=task.category,
                risk=task.risk,
                admin_required=True,
            )
            approved = prepared and self.audit_log.record(
                "approved",
                plan_id=task.plan_id,
                parent_plan_id=task.parent_plan_id,
                action_key=task.action_key,
                title=task.title,
                category=task.category,
                risk=task.risk,
                admin_required=True,
                approval_mode="user",
            )
        except (TypeError, ValueError):
            approved = False
        if not approved:
            self._finish_immediately(
                task,
                False,
                "Geri yükleme noktası denetim kaydı hazırlanamadı.",
            )
            return task
        if self._active_restore_task_id:
            self._finish_immediately(
                task,
                False,
                "Başka bir geri yükleme noktası işlemi devam ediyor.",
            )
            return task
        try:
            program, arguments = restore_point_process(
                child_plan_id,
                parent_action_key,
                elevated=not is_running_as_admin(),
            )
        except OSError:
            self._finish_immediately(
                task,
                False,
                "Güvenilir Windows PowerShell yolu doğrulanamadı. Ana işlem "
                "henüz başlamadı.",
            )
            return task
        except ValueError as exc:
            self._finish_immediately(task, False, str(exc))
            return task
        self._active_restore_task_id = task.id
        self._start_program_task(
            task,
            program,
            arguments,
            success_codes=(0,),
        )
        return task

    def start_manual_restore(
        self,
        title: str,
        *,
        plan_id: str,
        action_key: str,
        risk: str,
    ) -> TaskRecord:
        """Önceden onaylanmış bağımsız geri yükleme noktası planını başlat."""

        self._ensure_accepting_tasks()
        self._validate_recovery_context(
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id="",
            undo_key="",
            restore_point_status="not_applicable",
        )
        if action_key != "restore":
            raise ValueError("Geçersiz bağımsız geri yükleme eylemi.")
        self._ensure_unique_plan_id(plan_id)
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=title,
            command="registered:restore_point",
            category="İşlem güvenliği",
            created_at=_now(),
            admin=True,
            cancellable=False,
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self._emit_counts()
        if self._active_restore_task_id:
            self._finish_immediately(
                task,
                False,
                "Başka bir geri yükleme noktası işlemi devam ediyor.",
            )
            return task
        try:
            program, arguments = restore_point_process(
                plan_id,
                action_key,
                elevated=not is_running_as_admin(),
            )
        except OSError:
            self._finish_immediately(
                task,
                False,
                "Güvenilir Windows PowerShell yolu doğrulanamadı.",
            )
            return task
        except ValueError as exc:
            self._finish_immediately(task, False, str(exc))
            return task
        self._active_restore_task_id = task.id
        self._start_program_task(
            task,
            program,
            arguments,
            success_codes=(0,),
        )
        return task

    def record_result(
        self,
        title: str,
        message: str,
        *,
        success: bool,
        category: str = "Genel",
        output: str = "",
        plan_id: str = "",
        action_key: str = "",
        risk: str = "normal",
        admin: bool = False,
        parent_plan_id: str = "",
        undo_key: str = "",
        restore_point_status: str = "not_applicable",
    ) -> TaskRecord:
        self._ensure_accepting_tasks()
        if action_key in PROTECTED_ACTION_KEYS:
            raise ValueError(
                "Korumalı eylem sonucu genel sonuç API'siyle kaydedilemez."
            )
        self._validate_recovery_context(
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id=parent_plan_id,
            undo_key=undo_key,
            restore_point_status=restore_point_status,
        )
        if parent_plan_id:
            raise ValueError(
                "Geri alma sonucu yalnız çalışan doğrulanmış görevden "
                "üretilebilir."
            )
        self._ensure_unique_plan_id(plan_id)
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=title,
            command="",
            category=category,
            status="succeeded" if success else "failed",
            created_at=_now(),
            started_at=_now(),
            finished_at=_now(),
            message=message,
            output=output or f"{message}\n",
            progress=100 if success else 0,
            cancellable=False,
            admin=admin,
            plan_id=plan_id,
            action_key=action_key,
            risk=risk,
            parent_plan_id=parent_plan_id,
            undo_key=undo_key,
            undo_state=(
                "available" if success and undo_key else "none"
            ),
            restore_point_status=restore_point_status,
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self.notification.emit(
            title,
            message,
            "success" if success else "danger",
        )
        self._commit_terminal(task)
        return task

    def cancel(self, task_id: str) -> bool:
        task = self.task(task_id)
        process = self._processes.get(task_id)
        if (
            not task
            or not process
            or task.status not in ACTIVE_STATUSES
            or not task.cancellable
        ):
            return False

        self._cancel_requested.add(task_id)
        self._record_audit("cancel_requested", task)
        self._append_output(task, "\n[IT Toolkit] İptal isteği gönderildi.\n")
        process_id = int(process.processId())
        if process_id:
            try:
                taskkill_program = trusted_system_executable("taskkill.exe")
            except (OSError, ValueError):
                process.kill()
            else:
                killer = QProcess(self)
                killer.setProgram(taskkill_program)
                killer.setArguments(
                    ["/PID", str(process_id), "/T", "/F"]
                )
                killer.finished.connect(
                    lambda _code, _status, item=killer: self._remove_killer(
                        item
                    )
                )
                self._killers.append(killer)
                killer.start()
        else:
            process.kill()

        QTimer.singleShot(1_500, lambda: self._force_kill(task_id))
        return True

    def clear_finished(self) -> None:
        self._retry_pending_terminal_audits()
        self._tasks = [
            task
            for task in self._tasks
            if task.status in ACTIVE_STATUSES
            or task.undo_state == "running"
            or (task.plan_id and not task.audit_result_recorded)
        ]
        pending_count = sum(
            bool(task.plan_id) and not task.audit_result_recorded
            for task in self._tasks
        )
        if pending_count:
            self.notification.emit(
                "Denetim kaydı bekleniyor",
                f"{pending_count} görev, yerel sonuç kaydı tamamlanana kadar "
                "geçmişte korunuyor.",
                "warning",
            )
        self._save_history()
        self.history_cleared.emit()
        self._emit_counts()

    def report_text(self, task_id: str) -> str:
        task = self.task(task_id)
        if not task:
            return ""
        return "\n".join(
            (
                "IT Toolkit Görev Raporu",
                "=" * 24,
                f"Görev: {task.title}",
                f"Kategori: {task.category}",
                f"Durum: {status_text(task.status)}",
                f"Oluşturulma: {task.created_at}",
                f"Başlangıç: {task.started_at or '—'}",
                f"Bitiş: {task.finished_at or '—'}",
                f"Çıkış kodu: {task.exit_code if task.exit_code is not None else '—'}",
                f"Yönetici görevi: {'Evet' if task.admin else 'Hayır'}",
                f"Denetim kimliği: {task.plan_id or '—'}",
                f"Üst işlem kimliği: {task.parent_plan_id or '—'}",
                (
                    "Geri yükleme noktası: "
                    f"{self._restore_point_status_text(task.restore_point_status)}"
                ),
                f"Geri alma: {self._undo_state_text(task.undo_state)}",
                f"Mesaj: {task.message or '—'}",
                "",
                "Çıktı",
                "-" * 24,
                task.output or "Çıktı bulunmuyor.",
            )
        )

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        try:
            taskkill_program = trusted_system_executable("taskkill.exe")
        except (OSError, ValueError):
            taskkill_program = ""
        for task_id, process in tuple(self._processes.items()):
            task = self.task(task_id)
            if not task or process.state() == QProcess.ProcessState.NotRunning:
                continue
            task.status = "interrupted"
            task.finished_at = _now()
            task.message = "Uygulama kapatıldığı için görev yarım kaldı."
            process.blockSignals(True)
            process_id = int(process.processId())
            try:
                if process_id and taskkill_program:
                    subprocess.run(
                        [
                            taskkill_program,
                            "/PID",
                            str(process_id),
                            "/T",
                            "/F",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=CREATE_NO_WINDOW,
                        timeout=2,
                        check=False,
                    )
                else:
                    process.kill()
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
            process.waitForFinished(500)
            self._cleanup_process(task_id)
            parent = self._settle_recovery(task)
            if parent:
                self.task_updated.emit(parent)
            self._save_history()
            if self._record_terminal_audit(task):
                self._save_history()
        self._retry_pending_terminal_audits()
        for timer in self._audit_retry_timers.values():
            timer.stop()
            timer.deleteLater()
        self._audit_retry_timers.clear()
        self._audit_retry_attempts.clear()
        self._save_history()

    def _on_started(self, task_id: str) -> None:
        task = self.task(task_id)
        if not task:
            return
        task.status = "running"
        task.started_at = _now()
        task.message = "Görev çalışıyor."
        self._append_output(task, f"[IT Toolkit] {task.title} başlatıldı.\n")
        self._record_audit("started", task)
        self._task_changed(task)

    def _read_output(self, task_id: str) -> None:
        task = self.task(task_id)
        process = self._processes.get(task_id)
        if not task or not process:
            return
        raw = bytes(process.readAllStandardOutput())
        if not raw:
            return
        chunk = self._decode_output(raw)
        self._append_output(task, chunk)
        previous_progress = task.progress
        progress_values = [
            int(value)
            for value in PROGRESS_PATTERN.findall(chunk)
            if int(value) <= 100
        ]
        if progress_values:
            task.progress = progress_values[-1]
        if task.progress != previous_progress:
            self.task_updated.emit(task)

    def _on_error(
        self,
        task_id: str,
        error: QProcess.ProcessError,
    ) -> None:
        task = self.task(task_id)
        process = self._processes.get(task_id)
        if not task or not process:
            return
        if task.status in TERMINAL_STATUSES:
            return
        if error == QProcess.ProcessError.Crashed and task_id in self._cancel_requested:
            return
        if process.state() != QProcess.ProcessState.NotRunning:
            return
        task.status = "failed"
        task.finished_at = _now()
        if task.action_key in {"restore", "restore_point"}:
            task.message = (
                "Geri yükleme noktası işlemi başlatılamadı. Ana işlem "
                "henüz başlamadı."
            )
        else:
            task.message = f"Görev başlatılamadı: {process.errorString()}"
        self._append_output(task, f"\n[IT Toolkit] {task.message}\n")
        self.notification.emit(task.title, task.message, "danger")
        self._cleanup_process(task_id)
        self._commit_terminal(task)

    def _on_finished(
        self,
        task_id: str,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        task = self.task(task_id)
        process = self._processes.get(task_id)
        if not task:
            return
        if task.status in TERMINAL_STATUSES and task_id not in self._cancel_requested:
            return
        if process:
            self._read_output(task_id)

        task.exit_code = exit_code
        task.finished_at = _now()
        if task_id in self._cancel_requested:
            task.status = "cancelled"
            task.message = "Görev kullanıcı tarafından iptal edildi."
            tone = "warning"
        elif (
            exit_status == NORMAL_PROCESS_EXIT
            and exit_code in self._success_codes.get(task_id, {0})
        ):
            task.status = "succeeded"
            task.message = (
                "Geri yükleme noktası oluşturuldu ve doğrulandı."
                if task.action_key in {"restore", "restore_point"}
                else "Görev başarıyla tamamlandı."
            )
            task.progress = 100
            tone = "success"
        else:
            task.status = "failed"
            if exit_status != NORMAL_PROCESS_EXIT:
                task.message = (
                    "Geri yükleme noktası doğrulama süreci beklenmedik "
                    "biçimde sonlandı. Ana işlem henüz başlamadı."
                    if task.action_key in {"restore", "restore_point"}
                    else "Görev beklenmedik biçimde sonlandı."
                )
            else:
                protected_message = (
                    registered_process_failure_message(exit_code)
                    if task.action_key.startswith("undo:")
                    or task.action_key in PROTECTED_ACTION_KEYS
                    else None
                )
                task.message = (
                    restore_point_failure_message(exit_code)
                    if task.action_key in {"restore", "restore_point"}
                    else protected_message
                    or f"Görev {exit_code} çıkış koduyla tamamlandı."
                )
            tone = "danger"
        self._append_output(task, f"\n[IT Toolkit] {task.message}\n")
        self.notification.emit(task.title, task.message, tone)
        self._cleanup_process(task_id)
        self._commit_terminal(task)

    def _finish_immediately(
        self,
        task: TaskRecord,
        success: bool,
        message: str,
    ) -> None:
        task.status = "succeeded" if success else "failed"
        task.started_at = _now()
        task.finished_at = _now()
        task.message = message
        task.output = f"{message}\n"
        task.progress = 100 if success else 0
        task.cancellable = False
        self.notification.emit(
            task.title,
            message,
            "success" if success else "danger",
        )
        self._commit_terminal(task)

    def _force_kill(self, task_id: str) -> None:
        process = self._processes.get(task_id)
        if process and process.state() != QProcess.ProcessState.NotRunning:
            process.kill()

    def _remove_killer(self, killer: QProcess) -> None:
        if killer in self._killers:
            self._killers.remove(killer)
        killer.deleteLater()

    def _append_output(self, task: TaskRecord, chunk: str) -> None:
        if not chunk:
            return
        task.output += chunk
        if len(task.output) > OUTPUT_LIMIT:
            task.output = (
                "[IT Toolkit] Çıktının eski bölümü boyut sınırı nedeniyle kaldırıldı.\n"
                + task.output[-OUTPUT_LIMIT:]
            )
        self.output_added.emit(task.id, chunk)

    def _task_changed(self, task: TaskRecord) -> None:
        self.task_updated.emit(task)
        self._save_history()
        self._emit_counts()

    def _commit_terminal(self, task: TaskRecord) -> None:
        parent = self._settle_recovery(task)
        self._task_changed(task)
        if parent:
            self._task_changed(parent)
        if self._record_terminal_audit(task):
            self._save_history()
        elif task.plan_id and not task.audit_result_recorded:
            self._schedule_terminal_audit_retry(task.id)

    def _cleanup_process(self, task_id: str) -> None:
        process = self._processes.pop(task_id, None)
        if process:
            process.deleteLater()
        remove_command_script(self._script_paths.pop(task_id, None))
        self._success_codes.pop(task_id, None)
        self._cancel_requested.discard(task_id)
        if self._active_restore_task_id == task_id:
            self._active_restore_task_id = ""

    def _load_history(self) -> None:
        if not self.history_path.exists():
            return
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
            values = payload if isinstance(payload, list) else []
        except (OSError, ValueError, TypeError):
            self._tasks = []
            return

        self._tasks = []
        for item in values:
            if not isinstance(item, dict):
                continue
            try:
                self._tasks.append(TaskRecord.from_dict(item))
            except (TypeError, ValueError):
                continue

        changed = False
        root_plan_counts: dict[str, int] = {}
        for task in self._tasks:
            if task.plan_id and not task.parent_plan_id:
                root_plan_counts[task.plan_id] = (
                    root_plan_counts.get(task.plan_id, 0) + 1
                )
        duplicated_root_plan_ids = {
            plan_id
            for plan_id, count in root_plan_counts.items()
            if count > 1
        }
        for task in self._tasks:
            if (
                task.plan_id in duplicated_root_plan_ids
                and not task.parent_plan_id
                and task.undo_state != "none"
                and task.undo_state != "unknown"
            ):
                task.undo_state = "unknown"
                changed = True
        for task in self._tasks:
            result = self._audit_results.get((task.id, task.plan_id))
            if result:
                previous = task.to_dict()
                self._restore_terminal_result(task, result)
                changed = task.to_dict() != previous or changed
            elif task.status in ACTIVE_STATUSES:
                task.status = "interrupted"
                task.finished_at = _now()
                task.message = (
                    "Önceki uygulama oturumunda görev yarım kaldı."
                )
                task.cancellable = False
                task.audit_result_recorded = False
                changed = True
        for task in self._tasks:
            if task.status in TERMINAL_STATUSES and (
                task.undo_key or task.parent_plan_id
            ):
                changed = bool(self._settle_recovery(task)) or changed
        for task in self._tasks:
            if not task.parent_plan_id and task.undo_state == "running":
                task.undo_state = "unknown"
                changed = True
        self._trim_history()
        if changed:
            self._save_history()
        audit_changed = False
        for task in self._tasks:
            if not task.plan_id or task.status not in TERMINAL_STATUSES:
                continue
            task_key = (task.id, task.plan_id)
            if task_key in self._audited_terminal_tasks:
                if not task.audit_result_recorded:
                    task.audit_result_recorded = True
                    audit_changed = True
                continue
            recorded = self._record_terminal_audit(task)
            audit_changed = recorded or audit_changed
            if not recorded and not task.audit_result_recorded:
                self._schedule_terminal_audit_retry(task.id)
        if audit_changed:
            self._save_history()

    def _save_history(self) -> None:
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.history_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    [task.to_dict() for task in self._tasks],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.history_path)
        except OSError:
            return

    def _trim_history(self) -> None:
        if len(self._tasks) <= HISTORY_LIMIT:
            return
        protected = [
            task
            for task in self._tasks
            if task.status in ACTIVE_STATUSES
            or task.undo_state == "running"
            or (task.plan_id and not task.audit_result_recorded)
        ]
        finished = [
            task
            for task in self._tasks
            if task.status not in ACTIVE_STATUSES
            and task.undo_state != "running"
            and not (task.plan_id and not task.audit_result_recorded)
        ]
        self._tasks = protected + finished[
            : max(0, HISTORY_LIMIT - len(protected))
        ]

    @staticmethod
    def _validate_audit_context(
        plan_id: str,
        action_key: str,
        risk: str,
    ) -> None:
        if not isinstance(plan_id, str) or not isinstance(action_key, str):
            raise TypeError("Denetim kimlikleri metin olmalıdır.")
        if not isinstance(risk, str) or risk not in {
            "normal",
            "caution",
            "danger",
        }:
            raise ValueError("Geçersiz denetim risk seviyesi.")
        if not plan_id:
            if action_key:
                raise ValueError("Eylem anahtarı için plan kimliği eksik.")
            return
        if not PLAN_ID_PATTERN.fullmatch(plan_id):
            raise ValueError("Geçersiz denetim plan kimliği.")
        if not ACTION_KEY_PATTERN.fullmatch(action_key):
            raise ValueError("Geçersiz denetim eylem anahtarı.")

    def _ensure_accepting_tasks(self) -> None:
        if self._shutting_down:
            raise RuntimeError(
                "Uygulama kapanırken yeni görev başlatılamaz."
            )

    def _ensure_unique_plan_id(self, plan_id: str) -> None:
        if not plan_id:
            return
        if any(task.plan_id == plan_id for task in self._tasks):
            raise ValueError("İşlem planı daha önce görev olarak kullanıldı.")
        prior_execution = any(
            event.get("plan_id") == plan_id
            and event.get("event") in {"started", "delegated", "result"}
            for event in self.audit_log.read_events(limit=100_000)
        )
        if prior_execution:
            raise ValueError("İşlem planı daha önce yürütüldü.")

    def _find_undo_parent(self, parent_plan_id: str) -> TaskRecord | None:
        matches = [
            item
            for item in self._tasks
            if item.plan_id == parent_plan_id and not item.parent_plan_id
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _plan_semantics_match(
        plan: ExecutionPlan,
        expected: ExecutionPlan,
    ) -> bool:
        return (
            plan.parent_plan_id == expected.parent_plan_id
            and plan.action_key == expected.action_key
            and plan.title == expected.title
            and plan.category == expected.category
            and plan.command == expected.command
            and plan.urls == expected.urls
            and plan.admin_required == expected.admin_required
            and plan.keep_open == expected.keep_open
            and plan.success_codes == expected.success_codes
            and plan.impact == expected.impact
        )

    @staticmethod
    def _undo_task_matches_parent(
        task: TaskRecord,
        parent: TaskRecord,
    ) -> bool:
        expected = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        return bool(
            expected is not None
            and task.parent_plan_id == parent.plan_id
            and task.action_key == expected.action_key
            and task.title == expected.title
            and task.category == expected.category
            and task.command == expected.command
            and task.admin == expected.admin_required
            and task.risk == expected.impact.risk
        )

    @classmethod
    def _validate_recovery_context(
        cls,
        *,
        plan_id: str,
        action_key: str,
        risk: str,
        parent_plan_id: str,
        undo_key: str,
        restore_point_status: str,
    ) -> None:
        cls._validate_audit_context(plan_id, action_key, risk)
        if (
            not isinstance(restore_point_status, str)
            or restore_point_status not in RESTORE_POINT_STATUSES
        ):
            raise ValueError("Geçersiz geri yükleme noktası durumu.")
        if not plan_id:
            if (
                parent_plan_id
                or undo_key
                or restore_point_status != "not_applicable"
            ):
                raise ValueError(
                    "Kurtarma bilgisi denetim planı olmadan kullanılamaz."
                )
            return
        if not isinstance(parent_plan_id, str) or (
            parent_plan_id
            and (
                not PLAN_ID_PATTERN.fullmatch(parent_plan_id)
                or parent_plan_id == plan_id
            )
        ):
            raise ValueError("Geçersiz üst işlem planı kimliği.")
        if not isinstance(undo_key, str):
            raise TypeError("Geri alma anahtarı metin olmalıdır.")
        if parent_plan_id:
            if not action_key.startswith("undo:"):
                raise ValueError(
                    "Yalnız kayıtlı geri alma planı üst işleme bağlanabilir."
                )
            if undo_key or restore_point_status != "not_applicable":
                raise ValueError("Geri alma planı kurtarma zinciri üretemez.")
        elif action_key.startswith("undo:"):
            raise ValueError("Geri alma planının üst işlem kimliği eksik.")
        if undo_key and (
            not ACTION_KEY_PATTERN.fullmatch(undo_key)
            or expected_undo_key(action_key) != undo_key
        ):
            raise ValueError("Eylem için geri alma anahtarı doğrulanamadı.")

    def _reserve_undo_parent(
        self,
        parent_plan_id: str,
        child_action_key: str,
    ) -> TaskRecord | None:
        if not parent_plan_id:
            return None
        parent = self._find_undo_parent(parent_plan_id)
        if (
            parent is None
            or parent.status != "succeeded"
            or parent.undo_state != "available"
            or not parent.undo_key
            or expected_undo_key(parent.action_key) != parent.undo_key
            or child_action_key != f"undo:{parent.action_key}"
        ):
            raise ValueError(
                "Geri alınabilir üst işlem bulunamadı veya durumu değişti."
            )
        if parent.action_key.startswith("toggle:"):
            parts = parent.action_key.split(":")
            current, _status = get_toggle_status(parts[1])
            expected = len(parts) == 3 and parts[2] == "on"
            if current is None or current != expected:
                parent.undo_state = "unknown"
                self._task_changed(parent)
                raise ValueError(
                    "Ayar durumu onay sırasında değişti; geri alma durduruldu."
                )
        parent.undo_state = "running"
        self._save_history()
        return parent

    def _settle_recovery(self, task: TaskRecord) -> TaskRecord | None:
        if task.parent_plan_id and task.action_key.startswith("undo:"):
            parent = self._find_undo_parent(task.parent_plan_id)
            if parent is None:
                return None
            if not self._undo_task_matches_parent(task, parent):
                if parent.undo_state in {"available", "running", "completed"}:
                    parent.undo_state = "unknown"
                    return parent
                return None
            if task.status == "succeeded":
                desired_state = "completed"
            elif (
                task.status == "failed"
                and task.exit_code is None
                and task.started_at is None
            ):
                desired_state = "available"
            else:
                desired_state = "unknown"
            if parent.undo_state == desired_state:
                return None
            parent.undo_state = (
                desired_state
                if parent.undo_state == "running"
                else "unknown"
            )
            return parent
        if task.undo_key and task.undo_state in {"none", "available"}:
            task.undo_state = (
                "available" if task.status == "succeeded" else "none"
            )
        return None

    @staticmethod
    def _restore_point_status_text(status: str) -> str:
        return {
            "not_applicable": "Uygulanmadı",
            "skipped": "Kullanıcı tarafından atlandı",
            "created": "Oluşturuldu ve doğrulandı",
            "failed_override": "Doğrulanamadı; açık onayla devam edildi",
        }.get(status, "Bilinmiyor")

    @staticmethod
    def _undo_state_text(state: str) -> str:
        return {
            "none": "Sunulmuyor",
            "available": "Kullanılabilir",
            "running": "Çalışıyor",
            "completed": "Tamamlandı",
            "unknown": "Sonuç doğrulanamadı",
        }.get(state, "Bilinmiyor")

    def _record_audit(self, event: str, task: TaskRecord) -> bool:
        if not task.plan_id:
            return True
        try:
            return self.audit_log.record(
                event,
                plan_id=task.plan_id,
                parent_plan_id=task.parent_plan_id,
                action_key=task.action_key,
                title=task.title,
                category=task.category,
                risk=task.risk,
                admin_required=task.admin,
                task_id=task.id,
                status=task.status,
                exit_code=task.exit_code,
            )
        except (TypeError, ValueError):
            return False

    def _record_terminal_audit(self, task: TaskRecord) -> bool:
        if not task.plan_id or task.audit_result_recorded:
            return False
        task_key = (task.id, task.plan_id)
        if task_key in self._audited_terminal_tasks:
            task.audit_result_recorded = True
            self._audit_retry_attempts.pop(task.id, None)
            return True
        if not self._record_audit("result", task):
            return False
        self._audited_terminal_tasks.add(task_key)
        task.audit_result_recorded = True
        self._audit_retry_attempts.pop(task.id, None)
        return True

    def _schedule_terminal_audit_retry(self, task_id: str) -> None:
        if task_id in self._audit_retry_timers:
            return
        attempt = self._audit_retry_attempts.get(task_id, 0)
        delays = (2_000, 5_000, 15_000, 30_000, 60_000)
        if attempt >= len(delays):
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda selected_id=task_id: self._retry_terminal_audit(selected_id)
        )
        self._audit_retry_timers[task_id] = timer
        self._audit_retry_attempts[task_id] = attempt + 1
        timer.start(delays[attempt])

    def _retry_terminal_audit(self, task_id: str) -> None:
        timer = self._audit_retry_timers.pop(task_id, None)
        if timer:
            timer.stop()
            timer.deleteLater()
        task = self.task(task_id)
        if (
            not task
            or task.status not in TERMINAL_STATUSES
            or task.audit_result_recorded
        ):
            return
        if self._record_terminal_audit(task):
            self._save_history()
        else:
            self._schedule_terminal_audit_retry(task.id)

    def _retry_pending_terminal_audits(self) -> None:
        changed = False
        for task in self._tasks:
            if (
                task.plan_id
                and task.status in TERMINAL_STATUSES
                and not task.audit_result_recorded
            ):
                changed = self._record_terminal_audit(task) or changed
        if changed:
            self._save_history()

    @staticmethod
    def _restore_terminal_result(
        task: TaskRecord,
        result: dict[str, object],
    ) -> None:
        task.status = str(result["status"])
        task.finished_at = str(result["timestamp"])
        task.exit_code = (
            int(result["exit_code"])
            if result["exit_code"] is not None
            else None
        )
        task.message = (
            "Görev sonucu yerel denetim günlüğünden geri yüklendi."
        )
        task.progress = (
            100 if task.status in {"succeeded", "delegated"} else 0
        )
        task.cancellable = False
        task.audit_result_recorded = True

    def _emit_counts(self) -> None:
        running = sum(
            task.status in ACTIVE_STATUSES for task in self._tasks
        )
        succeeded = sum(task.status == "succeeded" for task in self._tasks)
        failed = sum(
            task.status in {"failed", "interrupted"}
            for task in self._tasks
        )
        self.counts_changed.emit(running, succeeded, failed)

    @staticmethod
    def _decode_output(raw: bytes) -> str:
        encodings = (
            "utf-8",
            locale.getpreferredencoding(False),
            "cp857",
            "cp1254",
        )
        for encoding in dict.fromkeys(encodings):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace")
