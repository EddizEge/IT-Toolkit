from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.registry import SYSTEM_ACTIONS, SYSTEM_TOGGLES, ToolAction, ToggleAction
from app_v2.services.command_runner import run_action
from app_v2.services.settings_service import get_toggle_status, set_toggle
from app_v2.widgets import ActionTile, ToggleRow


class SystemPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tiles: list[ActionTile] = []
        self._toggle_rows: dict[str, ToggleRow] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(30, 26, 30, 34)
        self.layout.setSpacing(18)

        title = QLabel("Sistem Yönetimi")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Windows bakım, onarım ve tanılama araçları — yönetici işlemleri işaretlenmiştir"
        )
        subtitle.setObjectName("PageSubtitle")
        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)

        grouped: dict[str, list[ToolAction]] = defaultdict(list)
        for action in SYSTEM_ACTIONS:
            grouped[action.category].append(action)

        for category, actions in grouped.items():
            section_title = QLabel(category)
            section_title.setObjectName("SectionTitle")
            self.layout.addWidget(section_title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            for index, action in enumerate(actions):
                tile = ActionTile(action)
                tile.run_requested.connect(self.execute_action)
                self._tiles.append(tile)
                grid.addWidget(tile, index // 2, index % 2)
            self.layout.addLayout(grid)

        toggle_title = QLabel("Windows temel ayarları")
        toggle_title.setObjectName("SectionTitle")
        self.layout.addWidget(toggle_title)

        for toggle in SYSTEM_TOGGLES:
            row = ToggleRow(toggle)
            row.change_requested.connect(self._change_toggle)
            self._toggle_rows[toggle.key] = row
            self.layout.addWidget(row)
        self.layout.addStretch()
        self.refresh_toggle_statuses()

    def filter_actions(self, query: str) -> None:
        normalized = query.casefold().strip()
        for tile in self._tiles:
            haystack = (
                f"{tile.action.title} {tile.action.description} {tile.action.category}"
            ).casefold()
            tile.setVisible(not normalized or normalized in haystack)

    def execute_action(self, action: ToolAction) -> None:
        if action.risk in {"caution", "danger"}:
            icon = (
                QMessageBox.Icon.Critical
                if action.risk == "danger"
                else QMessageBox.Icon.Warning
            )
            box = QMessageBox(self)
            box.setIcon(icon)
            box.setWindowTitle("İşlemi onayla")
            box.setText(action.title)
            box.setInformativeText(
                f"{action.description}\n\nBu işlemi başlatmak istiyor musunuz?"
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return

        ok, message = run_action(action)
        self.status_message.emit(f"{action.title}: {message}", ok)

    def _change_toggle(self, toggle: ToggleAction, enabled: bool) -> None:
        target = "açmak" if enabled else "kapatmak"
        result = QMessageBox.question(
            self,
            "Ayar değişikliğini onayla",
            f"“{toggle.title}” ayarını {target} istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        ok, message = set_toggle(toggle, enabled)
        self.status_message.emit(f"{toggle.title}: {message}", ok)
        QTimer.singleShot(2_500, self.refresh_toggle_statuses)

    def refresh_toggle_statuses(self) -> None:
        for key, row in self._toggle_rows.items():
            enabled, text = get_toggle_status(key)
            row.set_status(enabled, text)
