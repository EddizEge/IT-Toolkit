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

from app_v2.services.audit_log import AuditLog
from app_v2.services.command_runner import (
    CREATE_NO_WINDOW,
    create_command_script,
    is_running_as_admin,
    remove_command_script,
    run_command,
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
        self._load_history()

    @property
    def tasks(self) -> tuple[TaskRecord, ...]:
        return tuple(self._tasks)

    def task(self, task_id: str) -> TaskRecord | None:
        return next((item for item in self._tasks if item.id == task_id), None)

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
    ) -> TaskRecord:
        self._validate_audit_context(plan_id, action_key, risk)
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
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self._emit_counts()

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

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setProgram("cmd.exe")
        process.setArguments(["/d", "/c", os.fspath(script_path)])
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
        self._script_paths[task.id] = script_path
        self._processes[task.id] = process
        process.start()
        self._save_history()
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
    ) -> TaskRecord:
        self._validate_audit_context(plan_id, action_key, risk)
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
            killer = QProcess(self)
            killer.setProgram("taskkill")
            killer.setArguments(
                ["/PID", str(process_id), "/T", "/F"]
            )
            killer.finished.connect(
                lambda _code, _status, item=killer: self._remove_killer(item)
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
                f"Mesaj: {task.message or '—'}",
                "",
                "Çıktı",
                "-" * 24,
                task.output or "Çıktı bulunmuyor.",
            )
        )

    def shutdown(self) -> None:
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
                if process_id:
                    subprocess.run(
                        [
                            "taskkill",
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
        task.message = f"Görev başlatılamadı: {process.errorString()}"
        self._append_output(task, f"\n[IT Toolkit] {task.message}\n")
        self.notification.emit(task.title, task.message, "danger")
        self._cleanup_process(task_id)
        self._commit_terminal(task)

    def _on_finished(
        self,
        task_id: str,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
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
        elif exit_code in self._success_codes.get(task_id, {0}):
            task.status = "succeeded"
            task.message = "Görev başarıyla tamamlandı."
            task.progress = 100
            tone = "success"
        else:
            task.status = "failed"
            task.message = f"Görev {exit_code} çıkış koduyla tamamlandı."
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
        self._task_changed(task)
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
        for task in self._tasks:
            if task.status in ACTIVE_STATUSES:
                result = self._audit_results.get((task.id, task.plan_id))
                if result:
                    self._restore_terminal_result(task, result)
                else:
                    task.status = "interrupted"
                    task.finished_at = _now()
                    task.message = (
                        "Önceki uygulama oturumunda görev yarım kaldı."
                    )
                    task.cancellable = False
                    task.audit_result_recorded = False
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
            or (task.plan_id and not task.audit_result_recorded)
        ]
        finished = [
            task
            for task in self._tasks
            if task.status not in ACTIVE_STATUSES
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
        if not plan_id:
            return
        if not PLAN_ID_PATTERN.fullmatch(plan_id):
            raise ValueError("Geçersiz denetim plan kimliği.")
        if not ACTION_KEY_PATTERN.fullmatch(action_key):
            raise ValueError("Geçersiz denetim eylem anahtarı.")
        if risk not in {"normal", "caution", "danger"}:
            raise ValueError("Geçersiz denetim risk seviyesi.")

    def _record_audit(self, event: str, task: TaskRecord) -> bool:
        if not task.plan_id:
            return True
        try:
            return self.audit_log.record(
                event,
                plan_id=task.plan_id,
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
