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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> TaskRecord:
        allowed = cls.__dataclass_fields__
        return cls(**{key: item for key, item in value.items() if key in allowed})


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
    ) -> None:
        super().__init__(parent)
        self.history_path = history_path or _default_history_path()
        self.script_directory = script_directory
        self._tasks: list[TaskRecord] = []
        self._processes: dict[str, QProcess] = {}
        self._script_paths: dict[str, Path] = {}
        self._killers: list[QProcess] = []
        self._success_codes: dict[str, set[int]] = {}
        self._cancel_requested: set[str] = set()
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
    ) -> TaskRecord:
        task = TaskRecord(
            id=uuid.uuid4().hex,
            title=title,
            command=command,
            category=category,
            created_at=_now(),
            admin=admin,
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
            else:
                task.status = "failed"
                task.message = message
                task.output = f"{message}\n"
                task.progress = 0
                task.finished_at = _now()
                self.notification.emit(task.title, message, "danger")
            self._task_changed(task)
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
    ) -> TaskRecord:
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
        )
        self._tasks.insert(0, task)
        self._trim_history()
        self.task_added.emit(task)
        self.notification.emit(
            title,
            message,
            "success" if success else "danger",
        )
        self._task_changed(task)
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
        self._tasks = [
            task for task in self._tasks if task.status in ACTIVE_STATUSES
        ]
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

    def _on_started(self, task_id: str) -> None:
        task = self.task(task_id)
        if not task:
            return
        task.status = "running"
        task.started_at = _now()
        task.message = "Görev çalışıyor."
        self._append_output(task, f"[IT Toolkit] {task.title} başlatıldı.\n")
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
        self._task_changed(task)

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
        self._task_changed(task)

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
        self._task_changed(task)

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
            self._tasks = [
                TaskRecord.from_dict(item)
                for item in values
                if isinstance(item, dict)
            ]
        except (OSError, ValueError, TypeError):
            self._tasks = []
            return

        changed = False
        for task in self._tasks:
            if task.status in ACTIVE_STATUSES:
                task.status = "interrupted"
                task.finished_at = _now()
                task.message = "Önceki uygulama oturumunda görev yarım kaldı."
                task.cancellable = False
                changed = True
        self._trim_history()
        if changed:
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
        active = [task for task in self._tasks if task.status in ACTIVE_STATUSES]
        finished = [
            task for task in self._tasks if task.status not in ACTIVE_STATUSES
        ]
        self._tasks = active + finished[: max(0, HISTORY_LIMIT - len(active))]

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
