from __future__ import annotations

import base64
from collections.abc import Callable

from app_v2.services.command_runner import (
    trusted_system_executable,
    trusted_windows_powershell,
)

ELEVATION_FAILED_EXIT_CODE = 41
ELEVATED_RESULT_MISSING_EXIT_CODE = 42
PRECONDITION_QUERY_FAILED_EXIT_CODE = 43
PRECONDITION_MISMATCH_EXIT_CODE = 44
SMB_PRECONDITION_TIMEOUT_MS = 30_000

_POWERSHELL_PREFIX = (
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-EncodedCommand",
)
_UndoPair = tuple[str, str]
_ScriptBuilder = Callable[[], str]
PROTECTED_ACTION_KEYS = frozenset(
    {"rdp", "toggle:smb1:on", "toggle:smb1:off"}
)


def undo_process(
    action_key: str,
    undo_key: str,
    *,
    elevated: bool,
) -> tuple[str, tuple[str, ...]]:
    """İzinli geri alma çifti için dosyasız, güvenilir süreci üret.

    ``action_key`` tamamlanan ana işlemi, ``undo_key`` ise merkezi politikada
    kayıtlı ters işlemi belirtir. Fonksiyon serbest komut veya kullanıcı metni
    kabul etmez.
    """

    if not isinstance(action_key, str) or not isinstance(undo_key, str):
        raise TypeError("Geri alma eylem anahtarları metin olmalıdır.")
    if not isinstance(elevated, bool):
        raise TypeError("Yükseltilmiş işlem bilgisi boolean olmalıdır.")

    builder = _UNDO_BUILDERS.get((action_key, undo_key))
    if builder is None:
        raise ValueError(
            "Eylem ve geri alma anahtarı doğrulanmış izin listesiyle "
            "eşleşmiyor."
        )

    return _registered_process(builder, elevated=elevated)


def protected_action_process(
    action_key: str,
    *,
    elevated: bool,
) -> tuple[str, tuple[str, ...]]:
    """Restore korumalı kritik eylemi serbest komut almadan üret."""

    if not isinstance(action_key, str):
        raise TypeError("Korumalı eylem anahtarı metin olmalıdır.")
    if not isinstance(elevated, bool):
        raise TypeError("Yükseltilmiş işlem bilgisi boolean olmalıdır.")
    builder = _PROTECTED_ACTION_BUILDERS.get(action_key)
    if builder is None:
        raise ValueError("Bu eylem dosyasız korumalı işlem listesinde değil.")
    return _registered_process(builder, elevated=elevated)


def registered_process_failure_message(exit_code: int | None) -> str | None:
    """Korumalı işlem kodları için güvenli, yönlendirici mesaj üret."""

    return {
        ELEVATION_FAILED_EXIT_CODE: (
            "Yönetici onayı alınamadı veya UAC penceresi kapatıldı."
        ),
        ELEVATED_RESULT_MISSING_EXIT_CODE: (
            "Yükseltilmiş işlemin doğrulanmış sonucu alınamadı. Mevcut ayarı "
            "kontrol edin."
        ),
        PRECONDITION_QUERY_FAILED_EXIT_CODE: (
            "İşlem öncesi Windows durumu doğrulanamadı. Mevcut ayarı yenileyip "
            "tekrar kontrol edin."
        ),
        PRECONDITION_MISMATCH_EXIT_CODE: (
            "Onaydan sonra ayar durumu değiştiği için işlem güvenli biçimde "
            "durduruldu. Mevcut ayarı yenileyin."
        ),
    }.get(exit_code)


def _registered_process(
    builder: _ScriptBuilder,
    *,
    elevated: bool,
) -> tuple[str, tuple[str, ...]]:
    powershell_program = trusted_windows_powershell()
    inner_command = _encode_powershell(builder())
    inner_arguments = _encoded_arguments(inner_command)
    if not elevated:
        return powershell_program, inner_arguments

    outer_command = _encode_powershell(
        _elevation_wrapper(inner_command, powershell_program)
    )
    return powershell_program, _encoded_arguments(outer_command)


def _native_program(name: str) -> str:
    return _powershell_single_quoted(trusted_system_executable(name))


def _script_header() -> tuple[str, ...]:
    return (
        "$ErrorActionPreference='Stop'",
        "$PSModuleAutoLoadingPreference='None'",
        "$env:PSModulePath=[System.IO.Path]::Combine($PSHOME,'Modules')",
    )


def _native_step(
    program: str,
    arguments: tuple[str, ...],
    *,
    success_codes: tuple[int, ...] = (0,),
) -> tuple[str, ...]:
    if not success_codes or any(
        isinstance(code, bool) or not isinstance(code, int)
        for code in success_codes
    ):
        raise ValueError("Geçersiz yerel araç başarı kodu.")
    rendered_arguments = " ".join(
        _powershell_single_quoted(argument) for argument in arguments
    )
    success_expression = " -and ".join(
        f"$stepExit -ne {code}" for code in success_codes
    )
    invocation = f"& {program}"
    if rendered_arguments:
        invocation += f" {rendered_arguments}"
    return (
        invocation,
        "$stepExit=[int]$LASTEXITCODE",
        f"if ({success_expression}) {{ exit $stepExit }}",
    )


def _native_script(
    executable_name: str,
    steps: tuple[tuple[str, ...], ...],
    *,
    precondition: tuple[str, ...] = (),
) -> str:
    program = _native_program(executable_name)
    lines = list(_script_header())
    lines.extend(precondition)
    for arguments in steps:
        lines.extend(_native_step(program, arguments))
    lines.append("exit 0")
    return "\n".join(lines)


def _registry_dword_precondition(
    sub_key: str,
    value_name: str,
    *,
    accepted_values: tuple[int, ...] = (),
    require_missing: bool = False,
) -> tuple[str, ...]:
    values_invalid = any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in accepted_values
    )
    if values_invalid or require_missing == bool(accepted_values):
        raise ValueError("Geçersiz kayıt defteri ön koşulu.")
    accepted_expression = " -or ".join(
        f"$preconditionNumber -eq {value}" for value in accepted_values
    )
    missing_match = "$true" if require_missing else "$false"
    lines = [
        "$preconditionBase=$null",
        "$preconditionKey=$null",
        "$preconditionValue=$null",
        "$preconditionKind=$null",
        "$preconditionQueryFailed=$false",
        "try {",
        (
            "  $preconditionBase=[Microsoft.Win32.RegistryKey]::OpenBaseKey("
            "[Microsoft.Win32.RegistryHive]::LocalMachine,"
            "[Microsoft.Win32.RegistryView]::Registry64)"
        ),
        (
            "  $preconditionKey=$preconditionBase.OpenSubKey("
            f"{_powershell_single_quoted(sub_key)})"
        ),
        "  if ($null -ne $preconditionKey) {",
        (
            "    $preconditionValue=$preconditionKey.GetValue("
            f"{_powershell_single_quoted(value_name)},$null,"
            "[Microsoft.Win32.RegistryValueOptions]::"
            "DoNotExpandEnvironmentNames)"
        ),
    ]
    if not require_missing:
        lines.extend(
            (
                "    if ($null -ne $preconditionValue) {",
                (
                    "      $preconditionKind=$preconditionKey.GetValueKind("
                    f"{_powershell_single_quoted(value_name)})"
                ),
                "    }",
            )
        )
    lines.extend(
        (
            "  }",
            "}",
        "catch { $preconditionQueryFailed=$true }",
        "finally {",
        "  if ($null -ne $preconditionKey) { $preconditionKey.Dispose() }",
        "  if ($null -ne $preconditionBase) { $preconditionBase.Dispose() }",
        "}",
        (
            "if ($preconditionQueryFailed) "
            f"{{ exit {PRECONDITION_QUERY_FAILED_EXIT_CODE} }}"
        ),
        "if ($null -eq $preconditionValue) {",
        f"  $preconditionMatches={missing_match}",
        "}",
        "else {",
        )
    )
    if require_missing:
        lines.append("  $preconditionMatches=$false")
    else:
        lines.extend(
            (
                (
                    "  if ($preconditionKind -ne "
                    "[Microsoft.Win32.RegistryValueKind]::DWord) "
                    f"{{ exit {PRECONDITION_MISMATCH_EXIT_CODE} }}"
                ),
                "  try {",
                (
                    "    $preconditionNumber="
                    "[System.Convert]::ToInt32($preconditionValue)"
                ),
                "  }",
                f"  catch {{ exit {PRECONDITION_QUERY_FAILED_EXIT_CODE} }}",
                f"  $preconditionMatches=({accepted_expression})",
            )
        )
    lines.extend(
        (
            "}",
            (
                "if (-not $preconditionMatches) "
                f"{{ exit {PRECONDITION_MISMATCH_EXIT_CODE} }}"
            ),
        )
    )
    return tuple(lines)


def _windows_update_precondition(*, enabled: bool) -> tuple[str, ...]:
    policy_check = _registry_dword_precondition(
        r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
        "NoAutoUpdate",
        accepted_values=() if enabled else (1,),
        require_missing=enabled,
    )
    service_check = _registry_dword_precondition(
        r"SYSTEM\CurrentControlSet\Services\wuauserv",
        "Start",
        accepted_values=(3,) if enabled else (4,),
    )
    return (*policy_check, *service_check)


def _smb1_precondition(*, enabled: bool) -> tuple[str, ...]:
    dism_program = _native_program("dism.exe")
    expected_state = "Enabled" if enabled else "Disabled"
    return (
        "$preconditionProcess=$null",
        "$preconditionQueryFailed=$false",
        "$featureOutput=''",
        "$preconditionExit=-1",
        "$preconditionInfo=[System.Diagnostics.ProcessStartInfo]::new()",
        f"$preconditionInfo.FileName={dism_program}",
        "$preconditionInfo.UseShellExecute=$false",
        "$preconditionInfo.RedirectStandardOutput=$true",
        "$preconditionInfo.CreateNoWindow=$true",
        (
            "$preconditionInfo.WorkingDirectory="
            "[System.IO.Path]::GetDirectoryName($preconditionInfo.FileName)"
        ),
        (
            "$preconditionInfo.Arguments="
            "'/Online /Get-FeatureInfo /FeatureName:SMB1Protocol /English'"
        ),
        "try {",
        "  $preconditionProcess=[System.Diagnostics.Process]::Start($preconditionInfo)",
        (
            "  if ($null -eq $preconditionProcess) "
            "{ throw 'Feature query process missing' }"
        ),
        (
            "  $preconditionOutputTask="
            "$preconditionProcess.StandardOutput.ReadToEndAsync()"
        ),
        (
            "  if (-not $preconditionProcess.WaitForExit("
            f"{SMB_PRECONDITION_TIMEOUT_MS})) {{"
        ),
        "    try { $preconditionProcess.Kill() } catch { }",
        "    try { $preconditionProcess.WaitForExit(2000) } catch { }",
        "    $preconditionQueryFailed=$true",
        "  }",
        "  else {",
        "    $preconditionExit=[int]$preconditionProcess.ExitCode",
        (
            "    $featureOutput="
            "$preconditionOutputTask.GetAwaiter().GetResult()"
        ),
        "  }",
        "}",
        "catch { $preconditionQueryFailed=$true }",
        "finally {",
        "  if ($null -ne $preconditionProcess) { $preconditionProcess.Dispose() }",
        "}",
        (
            "if ($preconditionQueryFailed) "
            f"{{ exit {PRECONDITION_QUERY_FAILED_EXIT_CODE} }}"
        ),
        (
            "if ($preconditionExit -ne 0) "
            f"{{ exit {PRECONDITION_QUERY_FAILED_EXIT_CODE} }}"
        ),
        (
            "$preconditionMatch="
            "[System.Text.RegularExpressions.Regex]::Match("
            "$featureOutput,'(?im)^\\s*State\\s*:\\s*"
            "(Enabled|Disabled)\\s*$')"
        ),
        (
            "if (-not $preconditionMatch.Success) "
            f"{{ exit {PRECONDITION_QUERY_FAILED_EXIT_CODE} }}"
        ),
        (
            f"if ($preconditionMatch.Groups[1].Value -ne '{expected_state}') "
            f"{{ exit {PRECONDITION_MISMATCH_EXIT_CODE} }}"
        ),
    )


def _windows_update_on_script() -> str:
    lines = list(_script_header())
    lines.extend(_windows_update_precondition(enabled=False))
    steps = (
        (
            _native_program("sc.exe"),
            ("config", "wuauserv", "start=", "demand"),
        ),
        (_native_program("net.exe"), ("start", "wuauserv")),
        (
            _native_program("reg.exe"),
            (
                "delete",
                r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
                "/v",
                "NoAutoUpdate",
                "/f",
            ),
        ),
    )
    for program, arguments in steps:
        lines.extend(_native_step(program, arguments))
    lines.append("exit 0")
    return "\n".join(lines)


def _windows_update_off_script() -> str:
    lines = list(_script_header())
    lines.extend(_windows_update_precondition(enabled=True))
    steps = (
        (_native_program("net.exe"), ("stop", "wuauserv")),
        (
            _native_program("sc.exe"),
            ("config", "wuauserv", "start=", "disabled"),
        ),
        (
            _native_program("reg.exe"),
            (
                "add",
                r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
                "/v",
                "NoAutoUpdate",
                "/t",
                "REG_DWORD",
                "/d",
                "1",
                "/f",
            ),
        ),
    )
    for program, arguments in steps:
        lines.extend(_native_step(program, arguments))
    lines.append("exit 0")
    return "\n".join(lines)


def _hibernation_on_script() -> str:
    return _native_script(
        "powercfg.exe",
        (("-h", "on"),),
        precondition=_registry_dword_precondition(
            r"SYSTEM\CurrentControlSet\Control\Power",
            "HibernateEnabled",
            accepted_values=(0,),
        ),
    )


def _hibernation_off_script() -> str:
    return _native_script(
        "powercfg.exe",
        (("-h", "off"),),
        precondition=_registry_dword_precondition(
            r"SYSTEM\CurrentControlSet\Control\Power",
            "HibernateEnabled",
            accepted_values=(1,),
        ),
    )


def _smb1_script(*, enabled: bool) -> str:
    operation = "/Enable-Feature" if enabled else "/Disable-Feature"
    arguments = (
        "/Online",
        operation,
        "/FeatureName:SMB1Protocol",
        *(("/All",) if enabled else ()),
        "/NoRestart",
    )
    lines = list(_script_header())
    lines.extend(_smb1_precondition(enabled=not enabled))
    lines.extend(
        _native_step(
            _native_program("dism.exe"),
            arguments,
            success_codes=(0, 3010),
        )
    )
    lines.append("exit 0")
    return "\n".join(lines)


def _smb1_on_script() -> str:
    return _smb1_script(enabled=True)


def _smb1_off_script() -> str:
    return _smb1_script(enabled=False)


def _usb_write_protect_on_script() -> str:
    return _native_script(
        "reg.exe",
        (
            (
                "add",
                r"HKLM\System\CurrentControlSet\Control\StorageDevicePolicies",
                "/v",
                "WriteProtect",
                "/t",
                "REG_DWORD",
                "/d",
                "1",
                "/f",
            ),
        ),
        precondition=_registry_dword_precondition(
            r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies",
            "WriteProtect",
            require_missing=True,
        ),
    )


def _usb_write_protect_off_script() -> str:
    return _native_script(
        "reg.exe",
        (
            (
                "delete",
                r"HKLM\System\CurrentControlSet\Control\StorageDevicePolicies",
                "/v",
                "WriteProtect",
                "/f",
            ),
        ),
        precondition=_registry_dword_precondition(
            r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies",
            "WriteProtect",
            accepted_values=(1,),
        ),
    )


def _shutdown_cancel_script() -> str:
    return _native_script("shutdown.exe", (("/a",),))


def _rdp_on_script() -> str:
    lines = list(_script_header())
    steps = (
        (
            _native_program("reg.exe"),
            (
                "add",
                (
                    r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control"
                    r"\Terminal Server"
                ),
                "/v",
                "fDenyTSConnections",
                "/t",
                "REG_DWORD",
                "/d",
                "0",
                "/f",
            ),
        ),
        (
            _native_program("netsh.exe"),
            (
                "advfirewall",
                "firewall",
                "set",
                "rule",
                "group=@FirewallAPI.dll,-28752",
                "new",
                "enable=Yes",
            ),
        ),
    )
    for program, arguments in steps:
        lines.extend(_native_step(program, arguments))
    lines.append("exit 0")
    return "\n".join(lines)


_UNDO_BUILDERS: dict[_UndoPair, _ScriptBuilder] = {
    (
        "toggle:windows_update:on",
        "toggle:windows_update:off",
    ): _windows_update_off_script,
    (
        "toggle:windows_update:off",
        "toggle:windows_update:on",
    ): _windows_update_on_script,
    (
        "toggle:hibernation:on",
        "toggle:hibernation:off",
    ): _hibernation_off_script,
    (
        "toggle:hibernation:off",
        "toggle:hibernation:on",
    ): _hibernation_on_script,
    ("toggle:smb1:on", "toggle:smb1:off"): _smb1_off_script,
    ("toggle:smb1:off", "toggle:smb1:on"): _smb1_on_script,
    (
        "toggle:usb_write_protect:on",
        "toggle:usb_write_protect:off",
    ): _usb_write_protect_off_script,
    (
        "toggle:usb_write_protect:off",
        "toggle:usb_write_protect:on",
    ): _usb_write_protect_on_script,
    ("shutdown_schedule", "shutdown_cancel"): _shutdown_cancel_script,
}

_PROTECTED_ACTION_BUILDERS: dict[str, _ScriptBuilder] = {
    "rdp": _rdp_on_script,
    "toggle:smb1:on": _smb1_on_script,
    "toggle:smb1:off": _smb1_off_script,
}


def _encoded_arguments(encoded_command: str) -> tuple[str, ...]:
    return (*_POWERSHELL_PREFIX, encoded_command)


def _encode_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


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
            "$PSModuleAutoLoadingPreference='None'",
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
