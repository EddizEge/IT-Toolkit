from __future__ import annotations

from dataclasses import dataclass

from app_v2.services.command_builder import (
    aggregate_sequence,
    powershell_command,
)


@dataclass(frozen=True)
class TechnicianPreset:
    key: str
    title: str
    description: str
    command: str
    admin: bool = False
    risk: str = "normal"
    impact: str = ""
    interruption: str = ""
    rollback: str = ""


TECHNICIAN_PRESETS = (
    TechnicianPreset(
        "basic_check",
        "Temel sistem kontrolü",
        "Sistem, disk ve ağ bilgilerini tek görevde toplar; sistemde değişiklik yapmaz.",
        aggregate_sequence(
            (
                "systeminfo",
                powershell_command(
                    "Get-PhysicalDisk | Select-Object "
                    "FriendlyName,MediaType,HealthStatus,Size | "
                    "Format-Table -AutoSize"
                ),
                "ipconfig /all",
            )
        ),
    ),
    TechnicianPreset(
        "network_repair",
        "Ağ bağlantısını onar",
        "DNS önbelleğini ve Winsock kataloğunu sıfırlar; yeniden başlatma gerekebilir.",
        aggregate_sequence(("ipconfig /flushdns", "netsh winsock reset")),
        admin=True,
        risk="caution",
    ),
    TechnicianPreset(
        "delivery_report",
        "Teslim öncesi cihaz özeti",
        "Sistem, kurulu uygulama ve ağ bilgilerini Görev Merkezi'nde raporlar.",
        aggregate_sequence(("systeminfo", "winget list", "ipconfig /all")),
    ),
)

PRESET_LOOKUP = {preset.key: preset for preset in TECHNICIAN_PRESETS}
