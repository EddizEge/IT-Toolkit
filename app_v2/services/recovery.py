from __future__ import annotations

import base64
import ctypes
import ntpath
import os
import re

PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
ACTION_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.-]{0,127}$")

# Aşama D'nin ilk dar kapsamı. Yeni bir eylem ancak merkezi kurtarma
# politikası incelendikten sonra bu listeye eklenmelidir.
RESTORE_POINT_ACTION_KEYS = frozenset(
    {"restore", "rdp", "toggle:smb1:on"}
)

CHECKPOINT_FAILED_EXIT_CODE = 20
VERIFICATION_FAILED_EXIT_CODE = 21
INITIAL_QUERY_FAILED_EXIT_CODE = 22
TRUSTED_MODULE_FAILED_EXIT_CODE = 23
ELEVATION_FAILED_EXIT_CODE = 41
ELEVATED_RESULT_MISSING_EXIT_CODE = 42
RESTORE_POINT_POLL_TIMEOUT_SECONDS = 30
RESTORE_POINT_POLL_INTERVAL_MS = 500

_POWERSHELL_PREFIX = (
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-EncodedCommand",
)
_SYSTEM_DIRECTORY_INITIAL_BUFFER = 260
_SYSTEM_DIRECTORY_MAX_BUFFER = 32768


def restore_point_process(
    plan_id: str,
    action_key: str,
    *,
    elevated: bool,
) -> tuple[str, tuple[str, ...]]:
    """QProcess komutunu üret; gerekirse sabit UAC sarmalı kullan."""

    _validate_plan_id(plan_id)
    _validate_action_key(action_key)
    if not isinstance(elevated, bool):
        raise TypeError("Yükseltilmiş işlem bilgisi boolean olmalıdır.")

    powershell_program = _resolve_powershell_program()
    description = f"IT Toolkit Restore {plan_id}"
    inner_command = _encode_powershell(_inner_script(description))
    inner_arguments = _encoded_arguments(inner_command)
    if not elevated:
        return powershell_program, inner_arguments

    outer_command = _encode_powershell(
        _elevation_wrapper(inner_command, powershell_program)
    )
    return powershell_program, _encoded_arguments(outer_command)


def restore_point_failure_message(exit_code: int | None) -> str:
    """Ham PowerShell çıktısını göstermeden güvenli kullanıcı mesajı üret."""

    return {
        INITIAL_QUERY_FAILED_EXIT_CODE: (
            "Windows mevcut geri yükleme noktalarını okuyamadı. Sistem "
            "Koruması ayarlarını ve yönetici yetkisini kontrol edin."
        ),
        TRUSTED_MODULE_FAILED_EXIT_CODE: (
            "Windows'un güvenilir Sistem Geri Yükleme bileşeni doğrulanamadı. "
            "Ana işlem henüz başlamadı."
        ),
        CHECKPOINT_FAILED_EXIT_CODE: (
            "Windows yeni geri yükleme noktası oluşturamadı. Son 24 saatte "
            "bir nokta oluşturulmuş olabilir veya Sistem Koruması kapalı "
            "olabilir."
        ),
        VERIFICATION_FAILED_EXIT_CODE: (
            "Yeni geri yükleme noktası 30 saniye içinde doğrulanamadı. "
            "Oluşturulduğu varsayılmadı."
        ),
        ELEVATION_FAILED_EXIT_CODE: (
            "Yönetici onayı alınamadı veya UAC penceresi kapatıldı."
        ),
        ELEVATED_RESULT_MISSING_EXIT_CODE: (
            "Yükseltilmiş işlemin doğrulanmış sonucu alınamadı."
        ),
    }.get(
        exit_code,
        "Geri yükleme noktası doğrulanamadı. Ana işlem henüz başlamadı.",
    )


def _validate_plan_id(plan_id: object) -> None:
    if not isinstance(plan_id, str) or not PLAN_ID_PATTERN.fullmatch(plan_id):
        raise ValueError(
            "Geri yükleme noktası için plan kimliği 32 karakterli küçük "
            "hexadecimal olmalıdır."
        )


def _validate_action_key(action_key: object) -> None:
    if (
        not isinstance(action_key, str)
        or not ACTION_KEY_PATTERN.fullmatch(action_key)
        or action_key not in RESTORE_POINT_ACTION_KEYS
    ):
        raise ValueError(
            "Bu eylem doğrulanmış geri yükleme noktası primitive'i için "
            "izinli değildir."
        )


def _encoded_arguments(encoded_command: str) -> tuple[str, ...]:
    return (*_POWERSHELL_PREFIX, encoded_command)


def _resolve_powershell_program() -> str:
    """PowerShell'i yalnız Windows'un güvenilir sistem dizininden çöz."""

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
    ):
        raise OSError("Windows sistem dizini mutlak yerel yol değil.")

    return ntpath.join(
        normalized,
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )


def _get_system_directory_windows() -> str:
    """GetSystemDirectoryW ile System32 yolunu al; hiçbir fallback kullanma."""

    if os.name != "nt":
        raise OSError(
            "Geri yükleme noktası yalnız Windows üzerinde kullanılabilir."
        )

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


def _encode_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _trusted_management_prelude(
    required_commands: tuple[str, ...],
) -> tuple[str, ...]:
    allowed_commands = {
        "Checkpoint-Computer",
        "Get-ComputerRestorePoint",
        "Start-Process",
    }
    if not required_commands or not set(required_commands) <= allowed_commands:
        raise ValueError("Geçersiz güvenilir PowerShell komut listesi.")

    lines = [
        "$ErrorActionPreference='Stop'",
        "$PSModuleAutoLoadingPreference='None'",
        (
            "$trustedModuleRoot=[System.IO.Path]::GetFullPath("
            "[System.IO.Path]::Combine($PSHOME,'Modules'))"
        ),
        "$env:PSModulePath=$trustedModuleRoot",
        (
            "$managementManifest=[System.IO.Path]::GetFullPath("
            "[System.IO.Path]::Combine($trustedModuleRoot,"
            "'Microsoft.PowerShell.Management',"
            "'Microsoft.PowerShell.Management.psd1'))"
        ),
        "try {",
        "  $trustedPrefix=$trustedModuleRoot.TrimEnd('\\')+'\\'",
        "  if (-not $managementManifest.StartsWith(",
        "      $trustedPrefix,[System.StringComparison]::OrdinalIgnoreCase)) {",
        "    throw 'Trusted module path mismatch'",
        "  }",
        "  if (-not [System.IO.File]::Exists($managementManifest)) {",
        "    throw 'Trusted module manifest missing'",
        "  }",
        (
            "  Microsoft.PowerShell.Core\\Import-Module -Name "
            "$managementManifest -Force -ErrorAction Stop"
        ),
        (
            "  $loadedModule=Microsoft.PowerShell.Core\\Get-Module "
            "-Name 'Microsoft.PowerShell.Management'"
        ),
        "  if ($null -eq $loadedModule) { throw 'Trusted module missing' }",
        "  $loadedPath=[System.IO.Path]::GetFullPath($loadedModule.Path)",
        "  if (-not $loadedPath.Equals(",
        (
            "      $managementManifest,"
            "[System.StringComparison]::OrdinalIgnoreCase)) {"
        ),
        "    throw 'Loaded module path mismatch'",
        "  }",
    ]
    for index, command_name in enumerate(required_commands):
        lines.extend(
            (
                (
                    f"  $trustedCommand{index}="
                    "Microsoft.PowerShell.Core\\Get-Command "
                    "-Name 'Microsoft.PowerShell.Management\\"
                    f"{command_name}' -ErrorAction Stop"
                ),
                (
                    f"  if ($trustedCommand{index}.ModuleName -cne "
                    "'Microsoft.PowerShell.Management') {"
                ),
                "    throw 'Trusted command module mismatch'",
                "  }",
            )
        )
    lines.extend(
        (
            "}",
            f"catch {{ exit {TRUSTED_MODULE_FAILED_EXIT_CODE} }}",
        )
    )
    return tuple(lines)


def _inner_script(description: str) -> str:
    return "\n".join(
        (
            *_trusted_management_prelude(
                ("Checkpoint-Computer", "Get-ComputerRestorePoint")
            ),
            f"$description='{description}'",
            "$beforeSequence=[long]-1",
            "try {",
            (
                "  $beforePoints=@(Microsoft.PowerShell.Management\\"
                "Get-ComputerRestorePoint -ErrorAction Stop)"
            ),
            "  foreach ($point in $beforePoints) {",
            "    $sequence=[long]$point.SequenceNumber",
            "    if ($sequence -gt $beforeSequence) { $beforeSequence=$sequence }",
            "  }",
            "}",
            f"catch {{ exit {INITIAL_QUERY_FAILED_EXIT_CODE} }}",
            "try {",
            (
                "  Microsoft.PowerShell.Management\\Checkpoint-Computer "
                "-Description $description "
                "-RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop"
            ),
            "}",
            f"catch {{ exit {CHECKPOINT_FAILED_EXIT_CODE} }}",
            (
                "$deadline=[DateTime]::UtcNow.AddSeconds("
                f"{RESTORE_POINT_POLL_TIMEOUT_SECONDS})"
            ),
            "do {",
            "  try {",
            (
                "    $afterPoints=@(Microsoft.PowerShell.Management\\"
                "Get-ComputerRestorePoint -ErrorAction Stop)"
            ),
            "    foreach ($point in $afterPoints) {",
            "      if (([long]$point.SequenceNumber -gt $beforeSequence) -and",
            "          ($point.Description -ceq $description)) { exit 0 }",
            "    }",
            "  }",
            "  catch { }",
            (
                "  [System.Threading.Thread]::Sleep("
                f"{RESTORE_POINT_POLL_INTERVAL_MS})"
            ),
            "} while ([DateTime]::UtcNow -lt $deadline)",
            f"exit {VERIFICATION_FAILED_EXIT_CODE}",
        )
    )


def _powershell_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _elevation_wrapper(
    inner_command: str,
    powershell_program: str,
) -> str:
    quoted_program = _powershell_single_quoted(powershell_program)
    return "\n".join(
        (
            "$ErrorActionPreference='Stop'",
            f"$innerCommand='{inner_command}'",
            "$processInfo=[System.Diagnostics.ProcessStartInfo]::new()",
            f"$processInfo.FileName={quoted_program}",
            "$processInfo.UseShellExecute=$true",
            "$processInfo.Verb='runas'",
            (
                "$processInfo.WindowStyle="
                "[System.Diagnostics.ProcessWindowStyle]::Hidden"
            ),
            (
                "$processInfo.WorkingDirectory="
                "[System.IO.Path]::GetDirectoryName($processInfo.FileName)"
            ),
            (
                "$processInfo.Arguments='-NoLogo -NoProfile "
                "-NonInteractive -EncodedCommand '+$innerCommand"
            ),
            "try {",
            "  $process=[System.Diagnostics.Process]::Start($processInfo)",
            "  if ($null -eq $process) { throw 'Elevated process missing' }",
            "  $process.WaitForExit()",
            "}",
            f"catch {{ exit {ELEVATION_FAILED_EXIT_CODE} }}",
            "if ($null -eq $process -or $null -eq $process.ExitCode) {",
            f"  exit {ELEVATED_RESULT_MISSING_EXIT_CODE}",
            "}",
            "exit ([int]$process.ExitCode)",
        )
    )
