from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from app_v2.registry import ToolAction

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _default_script_directory() -> Path:
    return Path(tempfile.gettempdir()) / "IT Toolkit" / "tasks"


def create_command_script(
    command: str,
    *,
    directory: Path | None = None,
    self_delete: bool = False,
) -> Path:
    root = directory or _default_script_directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"task-{uuid.uuid4().hex}.cmd"
    lines = [
        "@echo off",
        "chcp 65001>nul",
        "call :IT_TOOLKIT_TASK",
        'set "IT_TOOLKIT_EXIT=%ERRORLEVEL%"',
    ]
    if self_delete:
        lines.append('del /q "%~f0" >nul 2>&1')
    lines.extend(
        (
            "exit /b %IT_TOOLKIT_EXIT%",
            "",
            ":IT_TOOLKIT_TASK",
            command,
            "exit /b %ERRORLEVEL%",
        )
    )
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return path


def remove_command_script(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def run_command(command: str, *, admin: bool, keep_open: bool) -> tuple[bool, str]:
    switch = "/k" if keep_open else "/c"
    script: Path | None = None
    try:
        script = create_command_script(command, self_delete=True)
        if admin:
            parameters = subprocess.list2cmdline(
                ["/d", switch, os.fspath(script)]
            )
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "cmd.exe",
                parameters,
                None,
                1,
            )
            if result <= 32:
                remove_command_script(script)
                return False, f"Windows komutu başlatamadı (kod: {result})."
            return True, "Yönetici yetkisi isteği açıldı."

        flags = CREATE_NEW_CONSOLE if keep_open else CREATE_NO_WINDOW
        subprocess.Popen(
            ["cmd.exe", "/d", switch, os.fspath(script)],
            creationflags=flags,
        )
        return True, "İşlem başlatıldı."
    except (AttributeError, OSError, ValueError) as exc:
        remove_command_script(script)
        return False, f"İşlem başlatılamadı: {exc}"


def run_action(action: ToolAction) -> tuple[bool, str]:
    return run_command(
        action.command,
        admin=action.admin,
        keep_open=action.keep_open,
    )
