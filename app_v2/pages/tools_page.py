from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.registry import ToolAction, ToggleAction
from app_v2.services.command_runner import run_action
from app_v2.services.settings_service import get_toggle_status, set_toggle
from app_v2.widgets import ActionTile, ToggleRow


class ToolsPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(
        self,
        title: str,
        subtitle: str,
        actions: tuple[ToolAction, ...],
        toggles: tuple[ToggleAction, ...] = (),
        custom_handlers: dict[str, Callable[[ToolAction], None]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.actions = actions
        self._handlers = custom_handlers or {}
        self._tiles: list[ActionTile] = []
        self._sections: list[tuple[QWidget, list[ActionTile]]] = []
        self._toggle_rows: dict[str, ToggleRow] = {}
        self._toggle_section: QWidget | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 34)
        layout.setSpacing(18)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        grouped: dict[str, list[ToolAction]] = defaultdict(list)
        for action in actions:
            grouped[action.category].append(action)

        for category, category_actions in grouped.items():
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(10)

            section_title = QLabel(category)
            section_title.setObjectName("SectionTitle")
            section_layout.addWidget(section_title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            section_tiles: list[ActionTile] = []
            for index, action in enumerate(category_actions):
                tile = ActionTile(action)
                tile.run_requested.connect(self.execute_action)
                self._tiles.append(tile)
                section_tiles.append(tile)
                grid.addWidget(tile, index // 2, index % 2)
            section_layout.addLayout(grid)
            layout.addWidget(section)
            self._sections.append((section, section_tiles))

        if toggles:
            toggle_section = QWidget()
            toggle_layout = QVBoxLayout(toggle_section)
            toggle_layout.setContentsMargins(0, 0, 0, 0)
            toggle_layout.setSpacing(10)
            toggle_title = QLabel("Temel ayarlar")
            toggle_title.setObjectName("SectionTitle")
            toggle_layout.addWidget(toggle_title)
            for toggle in toggles:
                row = ToggleRow(toggle)
                row.change_requested.connect(self._change_toggle)
                self._toggle_rows[toggle.key] = row
                toggle_layout.addWidget(row)
            layout.addWidget(toggle_section)
            self._toggle_section = toggle_section
            self.refresh_toggle_statuses()

        layout.addStretch()

    def filter_actions(self, query: str) -> None:
        normalized = query.casefold().strip()
        for section, tiles in self._sections:
            any_match = False
            for tile in tiles:
                haystack = (
                    f"{tile.action.title} {tile.action.description} {tile.action.category}"
                ).casefold()
                match = not normalized or normalized in haystack
                tile.setVisible(match)
                any_match = any_match or match
            section.setVisible(any_match)

        if self._toggle_section:
            toggle_match = not normalized
            for row in self._toggle_rows.values():
                haystack = f"{row.toggle.title} {row.toggle.description}".casefold()
                match = not normalized or normalized in haystack
                row.setVisible(match)
                toggle_match = toggle_match or match
            self._toggle_section.setVisible(toggle_match)

    def _confirm_action(self, action: ToolAction) -> bool:
        if action.risk not in {"caution", "danger"}:
            return True
        box = QMessageBox(self)
        box.setIcon(
            QMessageBox.Icon.Critical
            if action.risk == "danger"
            else QMessageBox.Icon.Warning
        )
        box.setWindowTitle("İşlemi onayla")
        box.setText(action.title)
        box.setInformativeText(
            f"{action.description}\n\nBu işlemi başlatmak istiyor musunuz?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def execute_action(self, action: ToolAction) -> None:
        if not self._confirm_action(action):
            return
        if action.handler:
            handler = self._handlers.get(action.handler)
            if not handler:
                self.status_message.emit(
                    f"{action.title}: özel işlem tanımlı değil.",
                    False,
                )
                return
            handler(action)
            return

        ok, message = run_action(action)
        self.status_message.emit(f"{action.title}: {message}", ok)

    def report(self, title: str, ok: bool, message: str) -> None:
        self.status_message.emit(f"{title}: {message}", ok)

    def _change_toggle(self, toggle: ToggleAction, enabled: bool) -> None:
        target = "açmak" if enabled else "kapatmak"
        warning = (
            "\n\nBu eski protokol güvenlik riski taşıyabilir."
            if toggle.risk == "danger" and enabled
            else ""
        )
        result = QMessageBox.question(
            self,
            "Ayar değişikliğini onayla",
            f"“{toggle.title}” ayarını {target} istiyor musunuz?{warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        ok, message = set_toggle(toggle, enabled)
        self.status_message.emit(f"{toggle.title}: {message}", ok)
        QTimer.singleShot(3_000, self.refresh_toggle_statuses)

    def refresh_toggle_statuses(self) -> None:
        for key, row in self._toggle_rows.items():
            enabled, text = get_toggle_status(key)
            row.set_status(enabled, text)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._toggle_rows:
            self.refresh_toggle_statuses()
