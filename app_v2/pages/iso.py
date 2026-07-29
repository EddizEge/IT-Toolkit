from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import ISO_ACTIONS
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class IsoPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(
            "Windows ISO ve USB",
            "Resmi Windows kurulum medyaları ve önyüklenebilir USB hazırlama araçları",
            ISO_ACTIONS,
            parent=parent,
            task_manager=task_manager,
            preferences=preferences,
        )
