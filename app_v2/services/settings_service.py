from __future__ import annotations

import os
import winreg

from app_v2.registry import ToggleAction
from app_v2.services.command_runner import run_command


def _read_reg_dword(key_path: str, value_name: str) -> int | None:
    try:
        root_name, sub_key = key_path.split("\\", 1)
        root = winreg.HKEY_LOCAL_MACHINE if root_name == "HKLM" else winreg.HKEY_CURRENT_USER
        with winreg.OpenKey(
            root,
            sub_key,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return int(value)
    except OSError:
        return None


def get_toggle_status(key: str) -> tuple[bool | None, str]:
    if key == "windows_update":
        disabled = _read_reg_dword(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
            "NoAutoUpdate",
        )
        return (False, "Kapalı") if disabled == 1 else (True, "Açık")

    if key == "hibernation":
        enabled = _read_reg_dword(
            r"HKLM\SYSTEM\CurrentControlSet\Control\Power",
            "HibernateEnabled",
        )
        if enabled is None:
            enabled = _read_reg_dword(
                r"HKLM\SYSTEM\CurrentControlSet\Control\Power",
                "HibernateEnabledDefault",
            )
        if enabled is None:
            enabled = 1 if os.path.exists(r"C:\hiberfil.sys") else 0
        return (enabled == 1, "Açık" if enabled == 1 else "Kapalı")

    if key == "smb1":
        start_value = _read_reg_dword(
            r"HKLM\SYSTEM\CurrentControlSet\Services\mrxsmb10",
            "Start",
        )
        if start_value is None:
            return False, "Kapalı"
        enabled = start_value in {2, 3}
        return enabled, "Açık" if enabled else "Kapalı"

    if key == "usb_write_protect":
        protected = _read_reg_dword(
            r"HKLM\System\CurrentControlSet\Control\StorageDevicePolicies",
            "WriteProtect",
        )
        enabled = protected == 1
        return enabled, "Korumalı" if enabled else "Yazma açık"

    return None, "Bilinmiyor"


def set_toggle(toggle: ToggleAction, enabled: bool) -> tuple[bool, str]:
    return run_command(
        toggle.command_on if enabled else toggle.command_off,
        admin=True,
        keep_open=False,
    )
