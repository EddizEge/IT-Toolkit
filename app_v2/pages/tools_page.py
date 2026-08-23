from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.action_confirmation import confirm_operation
from app_v2.registry import ToggleAction, ToolAction
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
    impact_for_action,
    impact_for_toggle,
)
from app_v2.services.preferences import ToolPreferences
from app_v2.services.settings_service import get_toggle_status
from app_v2.services.task_manager import TaskManager
from app_v2.widgets import ActionTile, ToggleRow


class ToolsPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(
        self,
        title: str,
        subtitle: str,
        actions: tuple[ToolAction, ...],
        toggles: tuple[ToggleAction, ...] = (),
        custom_handlers: dict[
            str,
            Callable[[ToolAction], ExecutionPlan | None],
        ]
        | None = None,
        ui_handlers: dict[str, Callable[[ToolAction], bool]] | None = None,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(parent)
        self.actions = actions
        self.page_title = title
        self.task_manager = task_manager or TaskManager(self)
        self.preferences = preferences
        self._plan_handlers = custom_handlers or {}
        self._ui_handlers = ui_handlers or {}
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
                tile = ActionTile(action, self.preferences)
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

    def execute_action(self, action: ToolAction) -> None:
        if action.handler:
            ui_handler = self._ui_handlers.get(action.handler)
            if ui_handler:
                if not confirm_operation(self, impact_for_action(action)):
                    return
                if ui_handler(action):
                    self.record_recent(action.key)
                return
            handler = self._plan_handlers.get(action.handler)
            if not handler:
                self.status_message.emit(
                    f"{action.title}: özel işlem tanımlı değil.",
                    False,
                )
                return
            plan = handler(action)
            if plan is not None:
                self._execute_plan(plan)
            return
        self._execute_plan(execution_plan_for_action(action))

    def _execute_plan(self, plan: ExecutionPlan) -> bool:
        if not confirm_operation(self, plan.impact):
            return False
        task = None
        if plan.command.strip():
            task = self.task_manager.start_command(
                plan.title,
                plan.command,
                category=plan.category,
                admin=plan.admin_required,
                keep_open=plan.keep_open,
                success_codes=plan.success_codes,
            )
        opened_urls = sum(
            bool(QDesktopServices.openUrl(QUrl(url))) for url in plan.urls
        )
        self.record_recent(plan.action_key)
        if task is None:
            ok = opened_urls == len(plan.urls)
            message = (
                f"{opened_urls} resmi bağlantı tarayıcıda açıldı."
                if ok
                else (
                    f"{opened_urls}/{len(plan.urls)} bağlantı açıldı. "
                    "Kalan bağlantıları daha sonra yeniden deneyin."
                )
            )
            self.task_manager.record_result(
                plan.title,
                message,
                success=ok,
                category=plan.category,
            )
            self.status_message.emit(f"{plan.title}: {message}", ok)
            return True
        ok = task.status not in {"failed", "cancelled", "interrupted"}
        message = (
            task.message
            if task.status in {"failed", "delegated"}
            else "Görev Merkezi'ne eklendi."
        )
        self.status_message.emit(f"{plan.title}: {message}", ok)
        return True

    def record_recent(self, action_key: str) -> None:
        if self.preferences:
            self.preferences.record_recent(action_key)

    def report(self, title: str, ok: bool, message: str) -> None:
        self.task_manager.record_result(
            title,
            message,
            success=ok,
            category=self.page_title,
        )
        self.status_message.emit(f"{title}: {message}", ok)

    def _change_toggle(self, toggle: ToggleAction, enabled: bool) -> None:
        if not confirm_operation(self, impact_for_toggle(toggle, enabled)):
            return
        task = self.task_manager.start_command(
            toggle.title,
            toggle.command_on if enabled else toggle.command_off,
            category="Temel ayarlar",
            admin=True,
            keep_open=False,
        )
        ok = task.status != "failed"
        message = (
            task.message
            if task.status in {"failed", "delegated"}
            else "Ayar görevi başlatıldı."
        )
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
