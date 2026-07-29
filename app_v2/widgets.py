from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app_v2.registry import ToolAction, ToggleAction


def clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())  # type: ignore[arg-type]


class MetricCard(QFrame):
    def __init__(self, title: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(132)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        title_label = QLabel(title)
        title_label.setObjectName("Muted")

        self.value_label = QLabel("—")
        self.value_label.setObjectName("MetricValue")
        self.value_label.setProperty("tone", tone)

        self.progress = QProgressBar()
        self.progress.setObjectName("MetricProgress")
        self.progress.setProperty("tone", tone)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setValue(0)

        self.detail_label = QLabel("Veri bekleniyor")
        self.detail_label.setObjectName("CardSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.detail_label)

    def set_metric(self, value: int, detail: str) -> None:
        self.value_label.setText(f"%{value}")
        self.progress.setValue(value)
        self.detail_label.setText(detail)


class UptimeCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(132)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(8)

        title = QLabel("ÇALIŞMA SÜRESİ")
        title.setObjectName("Muted")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("MetricValue")
        self.value_label.setProperty("tone", "amber")
        self.detail_label = QLabel("Sistem başlangıcı hesaplanıyor")
        self.detail_label.setObjectName("CardSubtitle")

        layout.addWidget(title)
        layout.addWidget(self.value_label)
        layout.addStretch()
        layout.addWidget(self.detail_label)


class DiskRow(QFrame):
    def __init__(self, data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToggleRow")
        self.setMinimumHeight(82)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(14)

        self.drive_label = QLabel()
        self.drive_label.setFixedWidth(42)
        self.drive_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drive_label.setObjectName("BrandMark")

        middle = QVBoxLayout()
        middle.setSpacing(6)
        self.model_label = QLabel()
        self.model_label.setObjectName("SectionTitle")
        self.progress = QProgressBar()
        self.progress.setObjectName("DiskProgress")
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)

        middle.addWidget(self.model_label)
        middle.addWidget(self.progress)

        self.usage_label = QLabel()
        self.usage_label.setObjectName("CardSubtitle")
        self.usage_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.usage_label.setMinimumWidth(145)

        layout.addWidget(self.drive_label)
        layout.addLayout(middle, 1)
        layout.addWidget(self.usage_label)
        self.update_data(data)

    def update_data(self, data: dict[str, Any]) -> None:
        drive = str(data["drive"]).replace(":", "")
        percent = int(data["percent"])
        self.drive_label.setText(drive)
        self.model_label.setText(str(data["model"]))
        self.progress.setValue(percent)
        usage = "danger" if percent >= 90 else "warning" if percent >= 75 else "normal"
        self.progress.setProperty("usage", usage)
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)
        self.usage_label.setText(
            f"%{percent}\n{data['used_gb']:.0f} / {data['total_gb']:.0f} GB"
        )


class InfoRow(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(14)
        key_label = QLabel(label)
        key_label.setObjectName("Muted")
        key_label.setFixedWidth(112)
        self.value_label = QLabel("Yükleniyor…")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(key_label)
        layout.addWidget(self.value_label, 1)


class ActionTile(QFrame):
    run_requested = Signal(object)

    def __init__(self, action: ToolAction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action = action
        self.setObjectName("ActionTile")
        self.setMinimumHeight(142)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)

        title_row = QHBoxLayout()
        title = QLabel(action.title)
        title.setObjectName("SectionTitle")
        title.setWordWrap(True)
        title_row.addWidget(title, 1)

        if action.admin:
            badge = QLabel("YÖNETİCİ")
            badge.setObjectName("Badge")
            title_row.addWidget(badge)

        description = QLabel(action.description)
        description.setObjectName("CardSubtitle")
        description.setWordWrap(True)

        button = QPushButton("Çalıştır")
        button.setObjectName("RunButton")
        button.setProperty("risk", action.risk)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedWidth(105)
        button.clicked.connect(lambda: self.run_requested.emit(self.action))

        action_row = QHBoxLayout()
        action_row.addStretch()
        action_row.addWidget(button)

        layout.addLayout(title_row)
        layout.addWidget(description, 1)
        layout.addLayout(action_row)


class ToggleRow(QFrame):
    change_requested = Signal(object, bool)

    def __init__(self, toggle: ToggleAction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggle = toggle
        self.setObjectName("ToggleRow")
        self.setMinimumHeight(86)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 12, 17, 12)
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        title = QLabel(toggle.title)
        title.setObjectName("SectionTitle")
        description = QLabel(toggle.description)
        description.setObjectName("CardSubtitle")
        description.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(description)

        self.status = QLabel("Bilinmiyor")
        self.status.setObjectName("StatusBadge")
        self.status.setProperty("status", "unknown")

        on_button = QPushButton("Aç")
        on_button.setObjectName("GhostButton")
        on_button.setFixedWidth(62)
        on_button.clicked.connect(lambda: self.change_requested.emit(self.toggle, True))

        off_button = QPushButton("Kapat")
        off_button.setObjectName("GhostButton")
        off_button.setFixedWidth(70)
        off_button.clicked.connect(lambda: self.change_requested.emit(self.toggle, False))

        layout.addLayout(text_layout, 1)
        layout.addWidget(self.status)
        layout.addWidget(on_button)
        layout.addWidget(off_button)

    def set_status(self, enabled: bool | None, text: str) -> None:
        status = "unknown" if enabled is None else "on" if enabled else "off"
        self.status.setText(text)
        self.status.setProperty("status", status)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
