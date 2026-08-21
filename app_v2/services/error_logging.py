from __future__ import annotations

import logging
import os
import platform
import re
import sys
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from app_v2 import __version__

LOGGER_NAME = "it_toolkit"
LOG_FILE_NAME = "application.log"
LOG_MAX_BYTES = 750_000
LOG_BACKUP_COUNT = 3
SHARED_LOG_LIMIT = 12_000

EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)
MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b")
PRODUCT_KEY_PATTERN = re.compile(r"(?i)\b(?:[A-Z0-9]{5}-){4}[A-Z0-9]{5}\b")
SECRET_PATTERN = re.compile(
    r"(?i)\b(password|parola|token|api[_-]?key|secret)\s*[:=]\s*([^\s,;]+)"
)


def default_log_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return root / "IT Toolkit" / "logs"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def close_logging() -> None:
    logger = get_logger()
    for handler in tuple(logger.handlers):
        if getattr(handler, "_it_toolkit_handler", False):
            logger.removeHandler(handler)
            handler.close()


def configure_logging(log_directory: Path | None = None) -> logging.Logger:
    directory = log_directory or default_log_directory()
    directory.mkdir(parents=True, exist_ok=True)

    logger = get_logger()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    close_logging()

    handler = RotatingFileHandler(
        directory / LOG_FILE_NAME,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler._it_toolkit_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


def install_exception_logging(
    notify_user: Callable[[str], None] | None = None,
) -> None:
    logger = get_logger()

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            return
        logger.critical(
            "Yakalanmayan uygulama hatası",
            exc_info=(exception_type, exception, traceback),
        )
        if notify_user:
            try:
                notify_user(str(exception))
            except Exception:
                logger.exception("Hata bildirimi kullanıcıya gösterilemedi.")

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        logger.critical(
            "Arka plan iş parçacığında yakalanmayan hata: %s",
            args.thread.name if args.thread else "bilinmiyor",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception


def sanitize_text(
    value: str,
    *,
    personal_values: tuple[str, ...] | None = None,
) -> str:
    text = value or ""
    candidates = personal_values
    if candidates is None:
        candidates = tuple(
            item
            for item in (
                os.environ.get("USERPROFILE", ""),
                str(Path.home()),
                os.environ.get("USERNAME", ""),
            )
            if item
        )

    for item in sorted(set(candidates), key=len, reverse=True):
        if len(item) < 3:
            continue
        text = re.sub(
            re.escape(item),
            "<KULLANICI>",
            text,
            flags=re.IGNORECASE,
        )

    text = EMAIL_PATTERN.sub("<E-POSTA>", text)
    text = IPV4_PATTERN.sub("<IP_ADRESI>", text)
    text = MAC_PATTERN.sub("<MAC_ADRESI>", text)
    text = PRODUCT_KEY_PATTERN.sub("<URUN_ANAHTARI>", text)
    text = SECRET_PATTERN.sub(r"\1=<MASKELENDI>", text)
    return text


def read_recent_log(
    log_directory: Path | None = None,
    *,
    max_chars: int = SHARED_LOG_LIMIT,
) -> str:
    path = (log_directory or default_log_directory()) / LOG_FILE_NAME
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "Henüz yerel hata günlüğü oluşmadı."
    if len(content) > max_chars:
        content = "[Günlüğün yalnızca son bölümü gösteriliyor]\n" + content[-max_chars:]
    return sanitize_text(content)


def public_environment_summary() -> str:
    return "\n".join(
        (
            f"IT Toolkit: v{__version__}",
            f"Windows: {platform.release()} ({platform.version()})",
            f"Mimari: {platform.machine() or 'Bilinmiyor'}",
            f"Python: {platform.python_version()}",
        )
    )


def shared_diagnostics(log_directory: Path | None = None) -> str:
    return (
        f"{public_environment_summary()}\n\n"
        "Son maskelenmiş uygulama günlüğü:\n"
        f"{read_recent_log(log_directory)}"
    )
