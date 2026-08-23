from __future__ import annotations

import json
import msvcrt
import os
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app_v2 import __version__
from app_v2.services.error_logging import sanitize_text

if TYPE_CHECKING:
    from app_v2.services.action_safety import ExecutionPlan

AUDIT_FILE_NAME = "operations.jsonl"
AUDIT_MAX_BYTES = 1_000_000
AUDIT_BACKUP_COUNT = 3
AUDIT_MAX_LINE_BYTES = 65_536
AUDIT_LOCK_TIMEOUT_SECONDS = 0.1
VALID_AUDIT_EVENTS = frozenset(
    {
        "prepared",
        "cancelled",
        "approved",
        "started",
        "cancel_requested",
        "delegated",
        "result",
    }
)
VALID_RISKS = frozenset({"normal", "caution", "danger"})
VALID_APPROVAL_MODES = frozenset({"", "automatic", "user"})
VALID_STATUSES = frozenset(
    {
        "",
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
        "delegated",
    }
)
RESULT_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "interrupted", "delegated"}
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.-]{0,127}$")
PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
EVENT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_PATH_LOCKS: dict[Path, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def default_audit_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return root / "IT Toolkit" / "audit" / AUDIT_FILE_NAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Geçersiz denetim alanı: {field_name}")
    cleaned = value.strip()
    if not IDENTIFIER_PATTERN.fullmatch(cleaned):
        raise ValueError(f"Geçersiz denetim alanı: {field_name}")
    return cleaned


def _path_lock(path: Path) -> threading.RLock:
    resolved = path.resolve(strict=False)
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(resolved, threading.RLock())


def _validate_exit_code(value: int | None) -> int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not -(2**31) <= value <= (2**32 - 1)
    ):
        raise ValueError("Geçersiz denetim çıkış kodu.")
    return value


def _validate_timestamp(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError("Geçersiz denetim zaman damgası.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Geçersiz denetim zaman damgası.") from exc
    if parsed.tzinfo is None:
        raise ValueError("Geçersiz denetim zaman damgası.")
    return value


def _validate_event_shape(
    event: str,
    *,
    approval_mode: str,
    task_id: str,
    status: str,
    exit_code: int | None,
) -> None:
    if event in {"prepared", "cancelled"}:
        valid = not approval_mode and not task_id and not status
    elif event == "approved":
        valid = (
            approval_mode in {"automatic", "user"}
            and not task_id
            and not status
        )
    elif event == "started":
        valid = not approval_mode and bool(task_id) and status == "running"
    elif event == "cancel_requested":
        valid = (
            not approval_mode
            and bool(task_id)
            and status in {"queued", "running"}
        )
    elif event == "delegated":
        valid = not approval_mode and bool(task_id) and status == "delegated"
    else:
        valid = (
            event == "result"
            and not approval_mode
            and bool(task_id)
            and status in RESULT_STATUSES
        )
    if not valid or (event != "result" and exit_code is not None):
        raise ValueError("Denetim olayı ve durum alanları birbiriyle çelişiyor.")


def _clean_text(
    value: str,
    *,
    limit: int,
    personal_values: tuple[str, ...] | None,
) -> str:
    cleaned = sanitize_text(
        value,
        personal_values=personal_values,
    )
    cleaned = " ".join(cleaned.replace("\x00", " ").split())
    if len(cleaned) > limit:
        cleaned = cleaned[: max(0, limit - 1)].rstrip() + "…"
    return cleaned


@dataclass(frozen=True, slots=True)
class AuditEvent:
    schema_version: int
    event_id: str
    timestamp: str
    app_version: str
    event: str
    plan_id: str
    action_key: str
    title: str
    category: str
    risk: str
    admin_required: bool
    approval_mode: str = ""
    task_id: str = ""
    status: str = ""
    exit_code: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AuditLog:
    def __init__(
        self,
        path: Path | None = None,
        *,
        max_bytes: int = AUDIT_MAX_BYTES,
        backup_count: int = AUDIT_BACKUP_COUNT,
        personal_values: tuple[str, ...] | None = None,
    ) -> None:
        if max_bytes < 256:
            raise ValueError("Denetim günlüğü boyut sınırı en az 256 bayt olmalıdır.")
        if backup_count < 0:
            raise ValueError("Denetim günlüğü yedek sayısı negatif olamaz.")
        self.path = path or default_audit_path()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.personal_values = personal_values
        self._lock = _path_lock(self.path)

    def record_plan(
        self,
        event: str,
        plan: ExecutionPlan,
        *,
        approval_mode: str = "",
        task_id: str = "",
        status: str = "",
        exit_code: int | None = None,
    ) -> bool:
        return self.record(
            event,
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            title=plan.title,
            category=plan.category,
            risk=plan.impact.risk,
            admin_required=plan.admin_required,
            approval_mode=approval_mode,
            task_id=task_id,
            status=status,
            exit_code=exit_code,
        )

    def record(
        self,
        event: str,
        *,
        plan_id: str,
        action_key: str,
        title: str,
        category: str,
        risk: str,
        admin_required: bool,
        approval_mode: str = "",
        task_id: str = "",
        status: str = "",
        exit_code: int | None = None,
    ) -> bool:
        if not isinstance(event, str) or event not in VALID_AUDIT_EVENTS:
            raise ValueError(f"Geçersiz denetim olayı: {event}")
        if not isinstance(risk, str) or risk not in VALID_RISKS:
            raise ValueError(f"Geçersiz denetim risk seviyesi: {risk}")
        if (
            not isinstance(approval_mode, str)
            or approval_mode not in VALID_APPROVAL_MODES
        ):
            raise ValueError(f"Geçersiz onay biçimi: {approval_mode}")
        if not isinstance(plan_id, str) or not PLAN_ID_PATTERN.fullmatch(plan_id):
            raise ValueError("Geçersiz denetim alanı: plan_id")
        if not isinstance(title, str) or not isinstance(category, str):
            raise TypeError("Geçersiz denetim metni.")
        if not isinstance(admin_required, bool):
            raise TypeError("Geçersiz yönetici gereksinimi.")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise ValueError("Geçersiz denetim durumu.")

        action_key_value = _validate_identifier(action_key, "action_key")
        if _clean_text(
            action_key_value,
            limit=128,
            personal_values=self.personal_values,
        ) != action_key_value:
            raise ValueError("Denetim eylem anahtarı hassas veri içeriyor.")
        if task_id and (
            not isinstance(task_id, str)
            or not EVENT_ID_PATTERN.fullmatch(task_id)
        ):
            raise ValueError("Geçersiz denetim alanı: task_id")
        exit_code_value = _validate_exit_code(exit_code)
        _validate_event_shape(
            event,
            approval_mode=approval_mode,
            task_id=task_id,
            status=status,
            exit_code=exit_code_value,
        )

        event_record = AuditEvent(
            schema_version=1,
            event_id=uuid.uuid4().hex,
            timestamp=_now(),
            app_version=__version__,
            event=event,
            plan_id=plan_id,
            action_key=action_key_value,
            title=_clean_text(
                title,
                limit=160,
                personal_values=self.personal_values,
            ),
            category=_clean_text(
                category,
                limit=120,
                personal_values=self.personal_values,
            ),
            risk=risk,
            admin_required=admin_required,
            approval_mode=approval_mode,
            task_id=task_id,
            status=status,
            exit_code=exit_code_value,
        )
        serialized = json.dumps(
            event_record.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"
        encoded_size = len(serialized.encode("utf-8"))
        if encoded_size > self.max_bytes:
            return False

        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self._process_lock():
                    separator_needed = self._line_separator_needed()
                    self._rotate_if_needed(encoded_size + int(separator_needed))
                    separator_needed = self._line_separator_needed()
                    with self.path.open(
                        "a",
                        encoding="utf-8",
                        newline="\n",
                    ) as stream:
                        if separator_needed:
                            stream.write("\n")
                        stream.write(serialized)
                        stream.flush()
        except OSError:
            return False
        return True

    def read_events(self, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        if limit <= 0:
            return ()
        events: deque[dict[str, object]] = deque(maxlen=limit)
        try:
            with self._lock:
                if not self.path.parent.exists():
                    return ()
                with self._process_lock():
                    paths = [
                        self._backup_path(index)
                        for index in range(self.backup_count, 0, -1)
                    ]
                    paths.append(self.path)
                    for path in paths:
                        if not path.exists():
                            continue
                        for line in self._bounded_lines(path):
                            try:
                                value = json.loads(line)
                                event = self._event_from_mapping(value)
                            except (json.JSONDecodeError, TypeError, ValueError):
                                continue
                            events.append(event)
        except OSError:
            return ()
        return tuple(events)

    def result_task_ids(self) -> frozenset[str]:
        return frozenset(
            task_id for task_id, _plan_id in self.result_events_by_task()
        )

    def result_events_by_task(
        self,
    ) -> dict[tuple[str, str], dict[str, object]]:
        results: dict[tuple[str, str], dict[str, object]] = {}
        for event in self.read_events(limit=100_000):
            if event["event"] != "result" or not event["task_id"]:
                continue
            key = (str(event["task_id"]), str(event["plan_id"]))
            results[key] = event
        return results

    def _event_from_mapping(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Geçersiz denetim kaydı.")
        event_id = value.get("event_id")
        plan_id = value.get("plan_id")
        event = value.get("event")
        risk = value.get("risk")
        approval_mode = value.get("approval_mode")
        status = value.get("status")
        if not isinstance(event_id, str) or not EVENT_ID_PATTERN.fullmatch(event_id):
            raise ValueError("Geçersiz olay kimliği.")
        if not isinstance(plan_id, str) or not PLAN_ID_PATTERN.fullmatch(plan_id):
            raise ValueError("Geçersiz plan kimliği.")
        if not isinstance(event, str) or event not in VALID_AUDIT_EVENTS:
            raise ValueError("Geçersiz olay.")
        if not isinstance(risk, str) or risk not in VALID_RISKS:
            raise ValueError("Geçersiz risk.")
        if (
            not isinstance(approval_mode, str)
            or approval_mode not in VALID_APPROVAL_MODES
        ):
            raise ValueError("Geçersiz onay biçimi.")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise ValueError("Geçersiz durum.")
        if not isinstance(value.get("admin_required"), bool):
            raise TypeError("Geçersiz yönetici gereksinimi.")
        if not isinstance(value.get("title"), str) or not isinstance(
            value.get("category"),
            str,
        ):
            raise TypeError("Geçersiz denetim metni.")
        app_version = value.get("app_version")
        if not isinstance(app_version, str):
            raise TypeError("Geçersiz uygulama sürümü.")
        action_key = _validate_identifier(
            value.get("action_key"),
            "action_key",
        )
        if _clean_text(
            action_key,
            limit=128,
            personal_values=self.personal_values,
        ) != action_key:
            raise ValueError("Denetim eylem anahtarı hassas veri içeriyor.")
        task_id_value = value.get("task_id", "")
        if task_id_value and (
            not isinstance(task_id_value, str)
            or not EVENT_ID_PATTERN.fullmatch(task_id_value)
        ):
            raise ValueError("Geçersiz görev kimliği.")
        task_id = str(task_id_value)
        exit_code = _validate_exit_code(value.get("exit_code"))
        _validate_event_shape(
            event,
            approval_mode=approval_mode,
            task_id=task_id,
            status=status,
            exit_code=exit_code,
        )
        restored = AuditEvent(
            schema_version=1,
            event_id=event_id,
            timestamp=_validate_timestamp(value.get("timestamp")),
            app_version=_clean_text(
                app_version,
                limit=40,
                personal_values=self.personal_values,
            ),
            event=event,
            plan_id=plan_id,
            action_key=action_key,
            title=_clean_text(
                value["title"],
                limit=160,
                personal_values=self.personal_values,
            ),
            category=_clean_text(
                value["category"],
                limit=120,
                personal_values=self.personal_values,
            ),
            risk=risk,
            admin_required=value["admin_required"],
            approval_mode=approval_mode,
            task_id=task_id,
            status=status,
            exit_code=exit_code,
        )
        return restored.to_dict()

    @staticmethod
    def _bounded_lines(path: Path) -> Iterator[str]:
        with path.open("rb") as stream:
            while True:
                raw = stream.readline(AUDIT_MAX_LINE_BYTES + 1)
                if not raw:
                    return
                if len(raw) > AUDIT_MAX_LINE_BYTES:
                    while raw and not raw.endswith(b"\n"):
                        raw = stream.readline(AUDIT_MAX_LINE_BYTES + 1)
                    continue
                yield raw.decode("utf-8", errors="replace")

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        lock_path = self.path.with_name(".audit.lock")
        with lock_path.open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            deadline = time.monotonic() + AUDIT_LOCK_TIMEOUT_SECONDS
            while True:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.001)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                time.sleep(0.002)

    def _rotate_if_needed(self, incoming_size: int) -> None:
        try:
            current_size = self.path.stat().st_size
        except FileNotFoundError:
            return
        if current_size + incoming_size <= self.max_bytes:
            return

        if self.backup_count == 0:
            self.path.unlink(missing_ok=True)
            return

        self._backup_path(self.backup_count).unlink(missing_ok=True)
        for index in range(self.backup_count - 1, 0, -1):
            source = self._backup_path(index)
            if source.exists():
                source.replace(self._backup_path(index + 1))
        self.path.replace(self._backup_path(1))

    def _line_separator_needed(self) -> bool:
        try:
            if self.path.stat().st_size == 0:
                return False
            with self.path.open("rb") as stream:
                stream.seek(-1, os.SEEK_END)
                return stream.read(1) != b"\n"
        except FileNotFoundError:
            return False

    def _backup_path(self, index: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{index}")
