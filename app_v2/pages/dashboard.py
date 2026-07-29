from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app_v2.services.system_monitor import SystemMonitor
from app_v2.widgets import DiskRow, InfoRow, MetricCard, UptimeCard


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._disk_rows: dict[str, DiskRow] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 30)
        layout.setSpacing(20)

        title = QLabel("Sistem özeti")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Bilgisayarın anlık durumu ve temel donanım bilgileri")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        metric_layout = QHBoxLayout()
        metric_layout.setSpacing(14)
        self.cpu_card = MetricCard("İŞLEMCİ", "blue")
        self.ram_card = MetricCard("BELLEK", "green")
        self.uptime_card = UptimeCard()
        metric_layout.addWidget(self.cpu_card)
        metric_layout.addWidget(self.ram_card)
        metric_layout.addWidget(self.uptime_card)
        layout.addLayout(metric_layout)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        layout.addLayout(columns)

        disk_panel = QFrame()
        disk_panel.setObjectName("Panel")
        disk_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        disk_layout = QVBoxLayout(disk_panel)
        disk_layout.setContentsMargins(18, 17, 18, 18)
        disk_layout.setSpacing(10)
        disk_title = QLabel("Disk kullanımı")
        disk_title.setObjectName("SectionTitle")
        disk_subtitle = QLabel("Fiziksel disk eşleştirmesiyle yerel sürücüler")
        disk_subtitle.setObjectName("CardSubtitle")
        self.disk_rows_layout = QVBoxLayout()
        self.disk_rows_layout.setSpacing(9)
        self.disk_empty = QLabel("Disk bilgileri yükleniyor…")
        self.disk_empty.setObjectName("Muted")
        self.disk_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disk_rows_layout.addWidget(self.disk_empty)
        disk_layout.addWidget(disk_title)
        disk_layout.addWidget(disk_subtitle)
        disk_layout.addSpacing(4)
        disk_layout.addLayout(self.disk_rows_layout)
        disk_layout.addStretch()

        info_panel = QFrame()
        info_panel.setObjectName("Panel")
        info_panel.setMinimumWidth(380)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 17, 18, 18)
        info_layout.setSpacing(4)
        info_title = QLabel("Cihaz bilgileri")
        info_title.setObjectName("SectionTitle")
        info_subtitle = QLabel("Fiziksel donanım filtreleri korunmuştur")
        info_subtitle.setObjectName("CardSubtitle")
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_subtitle)
        info_layout.addSpacing(10)

        self.info_rows = {
            "os": InfoRow("İşletim sistemi"),
            "cpu": InfoRow("İşlemci"),
            "gpu": InfoRow("Ekran kartı"),
            "board": InfoRow("Anakart"),
            "network": InfoRow("Ağ adaptörü"),
            "ip": InfoRow("Yerel IPv4"),
            "username": InfoRow("Kullanıcı"),
        }
        for row in self.info_rows.values():
            info_layout.addWidget(row)
        info_layout.addStretch()

        columns.addWidget(disk_panel, 5)
        columns.addWidget(info_panel, 4)
        layout.addStretch()

        self.monitor = SystemMonitor(self)
        self.monitor.metrics_updated.connect(self._update_metrics)
        self.monitor.specs_updated.connect(self._update_specs)
        self.monitor.disks_updated.connect(self._update_disks)
        self.monitor.start()

    def _update_metrics(self, data: dict[str, Any]) -> None:
        self.cpu_card.set_metric(data["cpu_percent"], "Anlık toplam kullanım")
        self.ram_card.set_metric(
            data["ram_percent"],
            f"{data['ram_used_gb']:.1f} / {data['ram_total_gb']:.1f} GB",
        )
        self.uptime_card.value_label.setText(data["uptime"])
        self.uptime_card.detail_label.setText("Son Windows başlangıcından beri")
        self.info_rows["ip"].value_label.setText(data["ip"])
        self.info_rows["username"].value_label.setText(data["username"])

    def _update_specs(self, data: dict[str, str]) -> None:
        for key in ("os", "cpu", "gpu", "board", "network"):
            self.info_rows[key].value_label.setText(data.get(key, "Bilinmiyor"))

    def _update_disks(self, disks: list[dict[str, Any]]) -> None:
        if disks and self.disk_empty:
            self.disk_empty.hide()

        current_drives = {str(item["drive"]) for item in disks}
        for drive in set(self._disk_rows) - current_drives:
            row = self._disk_rows.pop(drive)
            self.disk_rows_layout.removeWidget(row)
            row.deleteLater()

        for item in disks:
            drive = str(item["drive"])
            if drive not in self._disk_rows:
                row = DiskRow(item)
                self._disk_rows[drive] = row
                self.disk_rows_layout.addWidget(row)
            else:
                self._disk_rows[drive].update_data(item)
