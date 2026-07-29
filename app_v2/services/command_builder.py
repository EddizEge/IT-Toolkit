from __future__ import annotations

import base64
from collections.abc import Iterable


def powershell_command(script: str) -> str:
    """PowerShell kodunu cmd.exe tırnak kurallarından bağımsız çalıştır."""
    prepared = "$ProgressPreference='SilentlyContinue';" + script
    encoded = base64.b64encode(prepared.encode("utf-16-le")).decode("ascii")
    return (
        "powershell.exe -NoLogo -NoProfile -NonInteractive "
        f"-EncodedCommand {encoded}"
    )


def fail_fast_sequence(
    commands: Iterable[str],
    *,
    max_success_code: int = 0,
) -> str:
    """Komutları sırayla çalıştır ve ilk gerçek hatayı görev sonucuna taşı."""
    threshold = max_success_code + 1
    lines: list[str] = []
    for command in commands:
        if not command.strip():
            continue
        lines.append(command)
        lines.append(f"if errorlevel {threshold} exit /b %errorlevel%")
    return "\r\n".join(lines)


def aggregate_sequence(
    commands: Iterable[str],
    *,
    max_success_code: int = 0,
) -> str:
    """Bütün komutları çalıştır ve herhangi biri başarısızsa görevi başarısız yap."""
    threshold = max_success_code + 1
    lines = [
        "setlocal EnableDelayedExpansion",
        'set "IT_TOOLKIT_RESULT=0"',
    ]
    for command in commands:
        if not command.strip():
            continue
        lines.append(command)
        lines.append(
            f'if errorlevel {threshold} set "IT_TOOLKIT_RESULT=1"'
        )
    lines.extend(
        (
            "endlocal & exit /b %IT_TOOLKIT_RESULT%",
        )
    )
    return "\r\n".join(lines)
