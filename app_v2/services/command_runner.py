from __future__ import annotations

import ctypes
import ntpath
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

from app_v2.registry import ToolAction

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
_TRUSTED_SYSTEM_EXECUTABLES = {
    "cmd.exe": "cmd.exe",
    "dism.exe": "dism.exe",
    "netsh.exe": "netsh.exe",
    "net.exe": "net.exe",
    "powercfg.exe": "powercfg.exe",
    "reg.exe": "reg.exe",
    "sc.exe": "sc.exe",
    "shutdown.exe": "shutdown.exe",
    "taskkill.exe": "taskkill.exe",
}
_SYSTEM_DIRECTORY_INITIAL_BUFFER = 260
_SYSTEM_DIRECTORY_MAX_BUFFER = 32768


def trusted_system_executable(executable_name: str) -> str:
    """Allowlistteki aracı yalnız Windows System32 dizininden çöz."""

    if not isinstance(executable_name, str):
        raise TypeError("Sistem çalıştırılabilir adı metin olmalıdır.")
    canonical_name = _TRUSTED_SYSTEM_EXECUTABLES.get(
        executable_name.casefold()
    )
    if canonical_name is None:
        raise ValueError("Bu sistem çalıştırılabilir dosyasına izin verilmiyor.")

    return ntpath.join(_trusted_system_directory(), canonical_name)


def trusted_windows_powershell() -> str:
    """Windows PowerShell'i doğrulanmış System32 ağacından çöz."""

    return ntpath.join(
        _trusted_system_directory(),
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )


def _trusted_system_directory() -> str:
    system_directory = _get_system_directory_windows()
    if not isinstance(system_directory, str) or not system_directory:
        raise OSError("Windows sistem dizini güvenilir biçimde çözülemedi.")
    if "\x00" in system_directory:
        raise OSError("Windows sistem dizini geçersiz karakter içeriyor.")

    normalized = ntpath.normpath(system_directory)
    drive, tail = ntpath.splitdrive(normalized)
    if (
        len(drive) != 2
        or drive[1] != ":"
        or not tail.startswith("\\")
        or ntpath.basename(normalized).casefold() != "system32"
    ):
        raise OSError("Windows System32 dizini mutlak yerel yol değil.")
    return normalized


def _get_system_directory_windows() -> str:
    """GetSystemDirectoryW sonucunu fallback kullanmadan döndür."""

    if os.name != "nt":
        raise OSError("Windows sistem araçları yalnız Windows'ta kullanılabilir.")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_system_directory = kernel32.GetSystemDirectoryW
    get_system_directory.argtypes = [
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint,
    ]
    get_system_directory.restype = ctypes.c_uint

    capacity = _SYSTEM_DIRECTORY_INITIAL_BUFFER
    while capacity <= _SYSTEM_DIRECTORY_MAX_BUFFER:
        buffer = ctypes.create_unicode_buffer(capacity)
        length = int(get_system_directory(buffer, capacity))
        if length == 0:
            error_code = ctypes.get_last_error()
            raise OSError(
                error_code,
                "GetSystemDirectoryW çağrısı başarısız oldu.",
            )
        if length < capacity:
            return buffer.value
        capacity = length

    raise OSError("Windows sistem dizini güvenli uzunluk sınırını aşıyor.")


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
        command_program = trusted_system_executable("cmd.exe")
        script = create_command_script(command, self_delete=True)
        if admin:
            parameters = subprocess.list2cmdline(
                ["/d", switch, os.fspath(script)]
            )
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                command_program,
                parameters,
                os.path.dirname(command_program),
                1,
            )
            if result <= 32:
                remove_command_script(script)
                return False, f"Windows komutu başlatamadı (kod: {result})."
            return True, "Yönetici yetkisi isteği açıldı."

        flags = CREATE_NEW_CONSOLE if keep_open else CREATE_NO_WINDOW
        subprocess.Popen(
            [command_program, "/d", switch, os.fspath(script)],
            creationflags=flags,
            cwd=os.path.dirname(command_program),
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
