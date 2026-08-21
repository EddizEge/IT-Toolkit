from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
from typing import Any, Literal

import psutil

from app_v2 import __version__
from app_v2.services.error_logging import sanitize_text
from app_v2.services.system_monitor import _run_powershell

Severity = Literal["good", "info", "warning", "critical"]


@dataclass(frozen=True)
class HealthFinding:
    key: str
    category: str
    title: str
    summary: str
    severity: Severity
    evidence: str
    recommendation: str
    deduction: int = 0


@dataclass(frozen=True)
class HealthReport:
    generated_at: str
    score: int
    label: str
    summary: str
    device_type: str
    device_recommendations: tuple[str, ...]
    findings: tuple[HealthFinding, ...]

    @property
    def critical_count(self) -> int:
        return sum(item.severity == "critical" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.findings)

    @property
    def good_count(self) -> int:
        return sum(item.severity == "good" for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "score": self.score,
            "label": self.label,
            "summary": self.summary,
            "device_type": self.device_type,
            "device_recommendations": list(self.device_recommendations),
            "findings": [asdict(item) for item in self.findings],
        }


def _score_label(score: int) -> str:
    if score >= 90:
        return "Çok iyi"
    if score >= 75:
        return "İyi"
    if score >= 60:
        return "Dikkat"
    return "Kritik"


def _report_summary(
    score: int,
    critical_count: int,
    warning_count: int,
) -> str:
    if critical_count:
        return (
            f"{critical_count} kritik ve {warning_count} uyarı düzeyinde "
            "bulgu incelenmeli."
        )
    if warning_count:
        return f"{warning_count} uyarı bulundu; cihaz kullanılabilir durumda."
    if score >= 90:
        return "Kontrol edilen temel alanlarda önemli bir sorun görülmedi."
    return "Kritik sorun görülmedi; bilgi amaçlı sonuçları inceleyin."


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _device_profile(data: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    raw_type = str(data.get("device_type") or "").casefold()
    battery = data.get("battery")
    if any(marker in raw_type for marker in ("laptop", "notebook", "portable")):
        device_type = "Dizüstü / taşınabilir cihaz"
    elif any(marker in raw_type for marker in ("desktop", "tower", "workstation")):
        device_type = "Masaüstü / sabit sistem"
    elif battery:
        device_type = "Dizüstü / taşınabilir cihaz"
    else:
        device_type = "Masaüstü / sabit sistem"

    if device_type.startswith("Dizüstü"):
        recommendations = (
            "Havalandırma kanallarını kapatmayın ve cihazı yumuşak yüzeyde yoğun yük altında kullanmayın.",
            "Pil şişmesi, aşırı ısınma veya ani kapanma görülürse cihazı kullanmayı bırakıp yetkili servise başvurun.",
            "Uzun süre prizde kullanımda üreticinin resmi şarj sınırı özelliği varsa etkinleştirmeyi değerlendirin.",
        )
    else:
        recommendations = (
            "Kritik veriler için cihazdan ayrı en az bir güncel yedek bulundurun.",
            "Kasa hava akışını ve toz birikimini düzenli aralıklarla fiziksel olarak kontrol edin.",
            "Elektrik kesintilerinin sık olduğu ortamlarda uygun kapasiteli bir UPS kullanmayı değerlendirin.",
        )
    return device_type, recommendations


def evaluate_health(data: dict[str, Any]) -> HealthReport:
    findings: list[HealthFinding] = []
    device_type, device_recommendations = _device_profile(data)

    volumes = _records(data.get("volumes"))
    if not volumes:
        findings.append(
            HealthFinding(
                "disk-data",
                "Depolama",
                "Disk alanı okunamadı",
                "Yerel sürücü kullanım bilgisi alınamadı.",
                "info",
                "Sabit sürücü verisi döndürülmedi.",
                "Görevi yönetici oturumunda tekrar deneyin.",
            )
        )
    for volume in volumes:
        drive = str(volume.get("drive") or "Disk")
        percent = round(float(volume.get("percent") or 0))
        free_gb = float(volume.get("free_gb") or 0)
        if free_gb < 5:
            severity: Severity = "critical"
            deduction = 25
            summary = "Sürücüde kritik düzeyde az boş alan kaldı."
            recommendation = (
                "Gereksiz dosyaları temizleyin veya verileri başka bir sürücüye taşıyın."
            )
        elif free_gb < 15 or (percent >= 95 and free_gb < 50):
            severity = "warning"
            deduction = 12
            summary = "Sürücü boş alanı güvenli eşiklerin altında."
            recommendation = "En az 15 GB veya sürücünün %15'i kadar boş alan bırakın."
        elif percent >= 90:
            severity = "info"
            deduction = 0
            summary = "Kullanım oranı yüksek, ancak kullanılabilir boş alan yeterli."
            recommendation = "Büyük dosya artışını izleyin; boş alan 50 GB altına inerse temizlik yapın."
        else:
            severity = "good"
            deduction = 0
            summary = "Sürücüde yeterli boş alan var."
            recommendation = "Düzenli depolama kontrolüne devam edin."
        findings.append(
            HealthFinding(
                f"volume-{drive}",
                "Depolama",
                f"{drive} disk alanı",
                summary,
                severity,
                f"Kullanım %{percent}; boş alan {free_gb:.1f} GB.",
                recommendation,
                deduction,
            )
        )

    physical_disks = _records(data.get("physical_disks"))
    if not physical_disks:
        findings.append(
            HealthFinding(
                "physical-disk-data",
                "Depolama",
                "Fiziksel disk sağlığı bilinmiyor",
                "Windows fiziksel disk sağlık durumu bildirmedi.",
                "info",
                "Get-PhysicalDisk sonucu alınamadı.",
                "Üreticinin tanılama aracını kullanarak SMART kontrolü yapın.",
            )
        )
    for index, disk in enumerate(physical_disks):
        name = str(disk.get("name") or f"Fiziksel disk {index + 1}")
        health = str(disk.get("health") or "Bilinmiyor")
        operational = str(disk.get("operational") or "Bilinmiyor")
        normalized = f"{health} {operational}".casefold()
        unhealthy = any(
            marker in normalized
            for marker in ("unhealthy", "warning", "degraded", "lost communication")
        )
        if unhealthy:
            severity = "critical"
            deduction = 30
            summary = "Windows disk sağlığında sorun bildiriyor."
            recommendation = "Verileri hemen yedekleyin ve diski üretici aracıyla test edin."
        elif "healthy" in normalized or operational.casefold() == "ok":
            severity = "good"
            deduction = 0
            summary = "Windows diski sağlıklı olarak raporluyor."
            recommendation = "Düzenli yedek almaya devam edin."
        else:
            severity = "info"
            deduction = 0
            summary = "Disk sağlık durumu kesin olarak sınıflandırılamadı."
            recommendation = "Üreticinin SMART aracından ek kontrol yapın."
        findings.append(
            HealthFinding(
                f"physical-disk-{index}",
                "Depolama",
                name,
                summary,
                severity,
                f"Sağlık: {health}; çalışma durumu: {operational}.",
                recommendation,
                deduction,
            )
        )

    memory_percent = round(float(data.get("memory_percent") or 0))
    if memory_percent >= 95:
        severity = "critical"
        deduction = 15
        summary = "Bellek kullanımı kritik düzeyde yüksek."
        recommendation = "Yoğun uygulamaları kapatın ve bellek tüketimini tekrar ölçün."
    elif memory_percent >= 85:
        severity = "warning"
        deduction = 8
        summary = "Bellek kullanımı yüksek."
        recommendation = "Görev Yöneticisi'nde en çok bellek kullanan uygulamaları inceleyin."
    else:
        severity = "good"
        deduction = 0
        summary = "Anlık bellek kullanımı normal aralıkta."
        recommendation = "Uzun süreli yavaşlamalarda ölçümü tekrar çalıştırın."
    findings.append(
        HealthFinding(
            "memory",
            "Performans",
            "Bellek kullanımı",
            summary,
            severity,
            f"Tanılama anındaki kullanım %{memory_percent}.",
            recommendation,
            deduction,
        )
    )

    uptime_days = int(data.get("uptime_days") or 0)
    if uptime_days >= 30:
        severity = "warning"
        deduction = 8
        summary = "Windows uzun süredir yeniden başlatılmamış."
        recommendation = "Uygun zamanda tam bir yeniden başlatma planlayın."
    elif uptime_days >= 14:
        severity = "warning"
        deduction = 4
        summary = "Çalışma süresi bakım eşiğini aştı."
        recommendation = "Güncellemeleri tamamlamak için yeniden başlatmayı değerlendirin."
    else:
        severity = "good"
        deduction = 0
        summary = "Çalışma süresi olağan aralıkta."
        recommendation = "Düzenli bakım düzenini koruyun."
    findings.append(
        HealthFinding(
            "uptime",
            "Windows",
            "Yeniden başlatma düzeni",
            summary,
            severity,
            f"Son başlangıçtan beri {uptime_days} gün geçti.",
            recommendation,
            deduction,
        )
    )

    reboot_required = data.get("reboot_required")
    if reboot_required is True:
        findings.append(
            HealthFinding(
                "pending-reboot",
                "Windows",
                "Bekleyen yeniden başlatma",
                "Windows bir bakım işlemini tamamlamak için yeniden başlatma bekliyor.",
                "warning",
                "Bekleyen yeniden başlatma kayıtları bulundu.",
                "Çalışmaları kaydedip uygun zamanda bilgisayarı yeniden başlatın.",
                8,
            )
        )
    elif reboot_required is False:
        findings.append(
            HealthFinding(
                "pending-reboot",
                "Windows",
                "Bekleyen yeniden başlatma",
                "Bekleyen zorunlu yeniden başlatma görünmüyor.",
                "good",
                "Bilinen yeniden başlatma kayıtları bulunmadı.",
                "Windows Update durumunu düzenli kontrol edin.",
            )
        )
    else:
        findings.append(
            HealthFinding(
                "pending-reboot",
                "Windows",
                "Yeniden başlatma durumu bilinmiyor",
                "Bekleyen yeniden başlatma durumu okunamadı.",
                "info",
                "Kayıt defteri sorgusu sonuç vermedi.",
                "Windows Update ekranını el ile kontrol edin.",
            )
        )

    update_days = data.get("last_update_days")
    if update_days is None:
        severity = "info"
        deduction = 0
        summary = "Son Windows güncelleme tarihi okunamadı."
        evidence = "Get-HotFix sonucu tarih içermiyor."
        recommendation = "Windows Update ekranından güncellemeleri denetleyin."
    else:
        days = max(0, int(update_days))
        evidence = f"Son kayıtlı düzeltme {days} gün önce kuruldu."
        if days > 60:
            severity = "critical"
            deduction = 15
            summary = "Windows güncellemeleri uzun süredir uygulanmamış olabilir."
            recommendation = "Windows Update'i açıp kritik güncellemeleri yükleyin."
        elif days > 30:
            severity = "warning"
            deduction = 8
            summary = "Son kayıtlı Windows düzeltmesi eski."
            recommendation = "Windows Update üzerinden yeni güncellemeleri denetleyin."
        else:
            severity = "good"
            deduction = 0
            summary = "Windows düzeltme geçmişi güncel görünüyor."
            recommendation = "Otomatik güncellemeleri açık tutun."
    findings.append(
        HealthFinding(
            "windows-update",
            "Windows",
            "Windows güncelleme durumu",
            summary,
            severity,
            evidence,
            recommendation,
            deduction,
        )
    )

    battery = data.get("battery")
    if battery and battery.get("wear_percent") is not None:
        capacity = max(0, min(100, round(float(battery["wear_percent"]))))
        if capacity < 50:
            severity = "critical"
            deduction = 20
            summary = "Pil kapasitesi ciddi ölçüde azalmış."
            recommendation = "Pil değişimini planlayın ve şişme belirtilerini kontrol edin."
        elif capacity < 70:
            severity = "warning"
            deduction = 10
            summary = "Pil kapasitesinde belirgin yıpranma var."
            recommendation = "Pil çalışma süresini izleyin ve değişim planı oluşturun."
        else:
            severity = "good"
            deduction = 0
            summary = "Pil kapasitesi normal aralıkta."
            recommendation = "Aşırı sıcaklık ve sürekli tam şarjdan kaçının."
        findings.append(
            HealthFinding(
                "battery",
                "Donanım",
                "Pil sağlığı",
                summary,
                severity,
                f"Tam dolum kapasitesi, tasarım kapasitesinin %{capacity}'i.",
                recommendation,
                deduction,
            )
        )
    else:
        findings.append(
            HealthFinding(
                "battery",
                "Donanım",
                "Pil sağlığı",
                "Uyumlu fiziksel pil algılanmadı veya kapasite bilgisi sunulmadı.",
                "info",
                "Windows pil kapasite verisi döndürmedi.",
                "Masaüstü cihazlarda işlem gerekmez.",
            )
        )

    severity_order = {"critical": 0, "warning": 1, "info": 2, "good": 3}
    findings.sort(key=lambda item: (severity_order[item.severity], item.category, item.title))
    score = max(0, 100 - sum(item.deduction for item in findings))
    critical_count = sum(item.severity == "critical" for item in findings)
    warning_count = sum(item.severity == "warning" for item in findings)
    return HealthReport(
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        score=score,
        label=_score_label(score),
        summary=_report_summary(score, critical_count, warning_count),
        device_type=device_type,
        device_recommendations=device_recommendations,
        findings=tuple(findings),
    )


def _collect_windows_health() -> dict[str, Any]:
    script = r"""
    $volumes = @(Get-Volume -ErrorAction SilentlyContinue |
        Where-Object DriveType -eq 'Fixed' |
        Where-Object { $null -ne $_.DriveLetter } |
        ForEach-Object {
            $used = $_.Size - $_.SizeRemaining
            $percent = if ($_.Size -gt 0) {
                [Math]::Round(($used / $_.Size) * 100)
            } else { 0 }
            [ordered]@{
                drive = "$($_.DriveLetter):"
                percent = $percent
                free_gb = [Math]::Round($_.SizeRemaining / 1GB, 2)
            }
        })
    $physical = @(Get-PhysicalDisk -ErrorAction SilentlyContinue |
        ForEach-Object {
            [ordered]@{
                name = $_.FriendlyName
                health = [string]$_.HealthStatus
                operational = [string]($_.OperationalStatus -join ', ')
            }
        })
    $battery = $null
    try {
        $full = Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity `
            -ErrorAction Stop | Select-Object -First 1
        $design = Get-CimInstance -Namespace root\wmi -ClassName BatteryStaticData `
            -ErrorAction Stop | Select-Object -First 1
        if ($full.FullChargedCapacity -gt 0 -and $design.DesignedCapacity -gt 0) {
            $battery = [ordered]@{
                wear_percent = [Math]::Round(
                    ($full.FullChargedCapacity / $design.DesignedCapacity) * 100
                )
            }
        }
    } catch {}
    $lastUpdateDays = $null
    try {
        $hotfix = Get-HotFix -ErrorAction Stop |
            Where-Object InstalledOn |
            Sort-Object InstalledOn -Descending |
            Select-Object -First 1
        if ($hotfix) {
            $lastUpdateDays = [Math]::Max(
                0,
                [int]((Get-Date) - $hotfix.InstalledOn).TotalDays
            )
        }
    } catch {}
    $rebootRequired = (
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')
    )
    $deviceType = 'Desktop'
    try {
        $chassis = @(
            (Get-CimInstance Win32_SystemEnclosure -ErrorAction Stop |
                Select-Object -First 1).ChassisTypes
        )
        $portableTypes = @(8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32)
        if (@($chassis | Where-Object { $_ -in $portableTypes }).Count -gt 0) {
            $deviceType = 'Laptop'
        }
    } catch {
        if ($battery) { $deviceType = 'Laptop' }
    }
    [ordered]@{
        volumes = $volumes
        physical_disks = $physical
        battery = $battery
        last_update_days = $lastUpdateDays
        reboot_required = $rebootRequired
        device_type = $deviceType
    } | ConvertTo-Json -Depth 5 -Compress
    """
    output = _run_powershell(script, timeout=30)
    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise TypeError("Windows sağlık sorgusu geçersiz veri döndürdü.")
    return payload


def collect_health_data() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    uptime_days = max(0, int((time.time() - psutil.boot_time()) / 86_400))
    data: dict[str, Any] = {
        "memory_percent": round(memory.percent),
        "uptime_days": uptime_days,
        "volumes": [],
        "physical_disks": [],
        "battery": None,
        "last_update_days": None,
        "reboot_required": None,
        "device_type": "",
    }
    try:
        data.update(_collect_windows_health())
    except (
        OSError,
        RuntimeError,
        subprocess.TimeoutExpired,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        volumes: list[dict[str, Any]] = []
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except OSError:
                continue
            if usage.total <= 0:
                continue
            volumes.append(
                {
                    "drive": partition.device.rstrip("\\"),
                    "percent": round(usage.percent),
                    "free_gb": usage.free / (1024**3),
                }
            )
        data["volumes"] = volumes
    return data


def collect_health_report() -> HealthReport:
    return evaluate_health(collect_health_data())


def report_text(report: HealthReport, technician_notes: str = "") -> str:
    safe_notes = sanitize_text(technician_notes.strip())
    lines = [
        "IT Toolkit Sağlık Tanılama Raporu",
        "=" * 36,
        f"Tarih: {report.generated_at}",
        f"Sağlık puanı: {report.score}/100 ({report.label})",
        f"Özet: {report.summary}",
        f"Cihaz türü: {report.device_type}",
        "",
    ]
    labels = {
        "critical": "KRİTİK",
        "warning": "UYARI",
        "info": "BİLGİ",
        "good": "İYİ",
    }
    for item in report.findings:
        lines.extend(
            (
                f"[{labels[item.severity]}] {item.title} — {item.category}",
                item.summary,
                f"Kanıt: {item.evidence}",
                f"Öneri: {item.recommendation}",
                "",
            )
        )
    lines.extend(
        (
            "Cihaza özel güvenli öneriler",
            "-" * 30,
            *(f"- {item}" for item in report.device_recommendations),
            "",
        )
    )
    if safe_notes:
        lines.extend(
            (
                "Teknisyen notları",
                "-" * 30,
                safe_notes,
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def customer_report_html(
    report: HealthReport,
    technician_notes: str = "",
) -> str:
    safe_notes = sanitize_text(technician_notes.strip())
    severity_labels = {
        "critical": ("Kritik", "#B4232F", "#FDECEE"),
        "warning": ("Uyarı", "#8A5A00", "#FFF4D6"),
        "info": ("Bilgi", "#245A9A", "#EAF3FF"),
        "good": ("İyi", "#16734A", "#E8F7F0"),
    }
    finding_rows: list[str] = []
    for index, finding in enumerate(report.findings):
        label, color, background = severity_labels[finding.severity]
        impact = f"−{finding.deduction} puan" if finding.deduction else "Puan etkisi yok"
        if index and index % 4 == 0:
            finding_rows.append("<div class='page-break'></div>")
        finding_rows.append(
            "<table class='finding' width='100%' cellspacing='0'><tr><td>"
            f"<h3 style='font-size:16px;margin:0 0 8px 0'>{escape(finding.title)} "
            f"<span style='color:{color};background:{background}'>[{label}]</span></h3>"
            f"<p>{escape(finding.summary)}</p>"
            f"<p><b>Kanıt:</b> {escape(finding.evidence)}</p>"
            f"<p><b>Öneri:</b> {escape(finding.recommendation)}</p>"
            f"<small>{escape(finding.category)} • {impact}</small>"
            "</td></tr></table><div class='finding-space'>&nbsp;</div>"
        )
    device_items = "".join(
        f"<li>{escape(item)}</li>" for item in report.device_recommendations
    )
    notes_html = (
        "<h2>Teknisyen notları</h2>"
        f"<div class='notes'>{escape(safe_notes).replace(chr(10), '<br>')}</div>"
        if safe_notes
        else "<h2>Teknisyen notları</h2><div class='notes muted'>Not eklenmedi.</div>"
    )
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>IT Toolkit Müşteri Teslim Raporu</title>
<style>
@page {{ size: A4; margin: 18mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; color:#172033; margin:0; line-height:1.45; }}
h1 {{ color:#174EA6; margin-bottom:4px; }}
h2 {{ color:#243B64; margin-top:24px; border-bottom:1px solid #D9E2F0; padding-bottom:6px; }}
.meta {{ color:#5D6A7B; margin-bottom:18px; }}
.score {{ background:#EEF4FF; border:1px solid #BFD3F4; border-radius:12px; padding:18px; }}
.finding {{ border:1px solid #D9E2F0; page-break-inside:avoid; }}
.finding td {{ padding:12px; }}
.finding-space {{ font-size:8px; }}
.page-break {{ page-break-before:always; }}
.finding p {{ margin:7px 0; }}
.finding small, .muted {{ color:#6B778A; }}
.notes {{ background:#F7F9FC; border:1px solid #D9E2F0; border-radius:10px; padding:14px; min-height:46px; }}
footer {{ margin-top:28px; color:#7A8699; font-size:11px; border-top:1px solid #D9E2F0; padding-top:9px; }}
</style>
</head>
<body>
<h1>IT Toolkit Müşteri Teslim Raporu</h1>
<div class="meta">Tarih: {escape(report.generated_at)} • Cihaz: {escape(report.device_type)}</div>
<div class="score"><h2 style="font-size:28px;color:#174EA6;border:0;margin:0 0 8px 0">{report.score}/100 — {escape(report.label)}</h2><p>{escape(report.summary)}</p></div>
<h2>Tanılama bulguları</h2>
{''.join(finding_rows)}
<h2>Cihaza özel güvenli öneriler</h2>
<ul>{device_items}</ul>
{notes_html}
<footer>IT Toolkit v{escape(__version__)} • Yönet • Tanıla • Çöz</footer>
</body>
</html>
"""
