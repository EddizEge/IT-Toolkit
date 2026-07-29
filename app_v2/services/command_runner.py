from __future__ import annotations

import ctypes
import subprocess

from app_v2.registry import ToolAction

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def run_command(command: str, *, admin: bool, keep_open: bool) -> tuple[bool, str]:
    switch = "/k" if keep_open else "/c"
    try:
        if admin:
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "cmd.exe",
                f'{switch} {command}',
                None,
                1,
            )
            if result <= 32:
                return False, f"Windows komutu başlatamadı (kod: {result})."
            return True, "Yönetici yetkisi isteği açıldı."

        flags = CREATE_NEW_CONSOLE if keep_open else CREATE_NO_WINDOW
        subprocess.Popen(["cmd.exe", switch, command], creationflags=flags)
        return True, "İşlem başlatıldı."
    except (AttributeError, OSError, ValueError) as exc:
        return False, f"İşlem başlatılamadı: {exc}"


def run_action(action: ToolAction) -> tuple[bool, str]:
    return run_command(
        action.command,
        admin=action.admin,
        keep_open=action.keep_open,
    )
