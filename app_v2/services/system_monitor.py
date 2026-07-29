from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from collections.abc import Callable
from typing import Any

import psutil
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class WorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:  # noqa: BLE001 - background worker boundary
            try:
                self.signals.failed.emit(str(exc))
            except RuntimeError:
                pass
            return
        try:
            self.signals.completed.emit(result)
        except RuntimeError:
            pass


def _primary_ip() -> str:
    stats = psutil.net_if_stats()
    for interface, addresses in psutil.net_if_addrs().items():
        if interface in stats and not stats[interface].isup:
            continue
        for address in addresses:
            if address.family == socket.AF_INET and not address.address.startswith("127."):
                return address.address
    return "Bağlantı yok"


def collect_metrics() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    boot_seconds = max(0, int(time.time() - psutil.boot_time()))
    days, remainder = divmod(boot_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, _ = divmod(remainder, 60)
    uptime = f"{days} gün {hours} sa" if days else f"{hours} sa {minutes} dk"
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.15)),
        "ram_percent": round(memory.percent),
        "ram_used_gb": (memory.total - memory.available) / (1024**3),
        "ram_total_gb": memory.total / (1024**3),
        "uptime": uptime,
        "ip": _primary_ip(),
        "username": os.environ.get("USERNAME", "Bilinmiyor"),
    }


def _run_powershell(script: str, timeout: int = 20) -> str:
    prefixed = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + script
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", prefixed],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "PowerShell sorgusu başarısız oldu.")
    return result.stdout.strip()


def collect_system_specs() -> dict[str, str]:
    script = r"""
    $os = (Get-CimInstance Win32_OperatingSystem).Caption
    $cpu = (Get-CimInstance Win32_Processor).Name -replace '  ', ' '
    $gpus = Get-CimInstance Win32_VideoController |
        Where-Object { $_.PNPDeviceID -match "^PCI\\" } |
        Select-Object -ExpandProperty Name
    if (-not $gpus) {
        $gpus = (Get-CimInstance Win32_VideoController | Select-Object -First 1).Name
    }
    $board = Get-CimInstance Win32_BaseBoard
    $boardName = "$($board.Manufacturer) $($board.Product)"
    $net = (Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
        Where-Object Status -eq 'Up' |
        Select-Object -ExpandProperty InterfaceDescription) -join ", "
    if (-not $net) { $net = "Aktif fiziksel bağlantı yok" }
    "$os|$cpu|$($gpus -join ' + ')|$boardName|$net"
    """
    fallback = {
        "os": platform.platform(),
        "cpu": platform.processor() or "Bilinmiyor",
        "gpu": "Bilinmiyor",
        "board": "Bilinmiyor",
        "network": "Bilinmiyor",
    }
    try:
        parts = _run_powershell(script).split("|")
        if len(parts) >= 5:
            return {
                "os": parts[0].strip(),
                "cpu": parts[1].strip(),
                "gpu": parts[2].strip(),
                "board": parts[3].strip(),
                "network": parts[4].strip(),
            }
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
        return fallback
    return fallback


def collect_disks() -> list[dict[str, Any]]:
    script = r"""
    Get-Volume |
        Where-Object DriveType -eq 'Fixed' |
        Where-Object DriveLetter -ne $null |
        ForEach-Object {
            $letter = $_.DriveLetter + ":"
            $model = $_.FileSystemLabel
            if ([string]::IsNullOrWhiteSpace($model)) { $model = "Yerel Disk" }
            try {
                $partition = Get-Partition -DriveLetter $_.DriveLetter -ErrorAction Stop
                $disk = Get-Disk -Number $partition.DiskNumber -ErrorAction Stop
                if ($disk -and $disk.FriendlyName) { $model = $disk.FriendlyName }
            } catch {}
            "$letter|$model|$($_.Size)|$($_.SizeRemaining)"
        }
    """
    disks: list[dict[str, Any]] = []
    try:
        output = _run_powershell(script)
        for line in output.splitlines():
            parts = line.strip().split("|")
            if len(parts) != 4:
                continue
            total = int(parts[2])
            free = int(parts[3])
            used = max(0, total - free)
            percent = round((used / total) * 100) if total else 0
            disks.append(
                {
                    "drive": parts[0],
                    "model": parts[1],
                    "total_gb": total / (1024**3),
                    "used_gb": used / (1024**3),
                    "percent": percent,
                }
            )
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError):
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except OSError:
                continue
            disks.append(
                {
                    "drive": partition.device.rstrip("\\"),
                    "model": partition.fstype or "Yerel Disk",
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "percent": round(usage.percent),
                }
            )
    return sorted(disks, key=lambda item: item["drive"])


class SystemMonitor(QObject):
    metrics_updated = Signal(dict)
    specs_updated = Signal(dict)
    disks_updated = Signal(list)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self._metrics_busy = False
        self._disks_busy = False
        self._specs_busy = False

        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(2_000)
        self._metrics_timer.timeout.connect(self.refresh_metrics)

        self._disks_timer = QTimer(self)
        self._disks_timer.setInterval(12_000)
        self._disks_timer.timeout.connect(self.refresh_disks)

        psutil.cpu_percent(interval=None)

    def start(self) -> None:
        self._metrics_timer.start()
        self._disks_timer.start()
        self.refresh_metrics()
        self.refresh_disks()
        self.refresh_specs()

    def stop(self) -> None:
        self._metrics_timer.stop()
        self._disks_timer.stop()

    def _start_worker(
        self,
        function: Callable[[], Any],
        completed: Callable[[Any], None],
        failed: Callable[[str], None],
    ) -> None:
        worker = FunctionWorker(function)
        self._workers.add(worker)

        def complete_and_release(data: Any) -> None:
            try:
                completed(data)
            finally:
                self._workers.discard(worker)

        def fail_and_release(message: str) -> None:
            try:
                failed(message)
            finally:
                self._workers.discard(worker)

        worker.signals.completed.connect(complete_and_release)
        worker.signals.failed.connect(fail_and_release)
        self._pool.start(worker)

    @Slot()
    def refresh_metrics(self) -> None:
        if self._metrics_busy:
            return
        self._metrics_busy = True

        def done(data: dict[str, Any]) -> None:
            self._metrics_busy = False
            self.metrics_updated.emit(data)

        def failed(message: str) -> None:
            self._metrics_busy = False
            self.error.emit(message)

        self._start_worker(collect_metrics, done, failed)

    @Slot()
    def refresh_disks(self) -> None:
        if self._disks_busy:
            return
        self._disks_busy = True

        def done(data: list[dict[str, Any]]) -> None:
            self._disks_busy = False
            self.disks_updated.emit(data)

        def failed(message: str) -> None:
            self._disks_busy = False
            self.error.emit(message)

        self._start_worker(collect_disks, done, failed)

    @Slot()
    def refresh_specs(self) -> None:
        if self._specs_busy:
            return
        self._specs_busy = True

        def done(data: dict[str, str]) -> None:
            self._specs_busy = False
            self.specs_updated.emit(data)

        def failed(message: str) -> None:
            self._specs_busy = False
            self.error.emit(message)

        self._start_worker(collect_system_specs, done, failed)
