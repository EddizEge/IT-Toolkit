from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import SYSTEM_ACTIONS, SYSTEM_TOGGLES
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class SystemPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(
            "Sistem Yönetimi",
            (
                "Windows bakım, onarım ve tanılama araçları — yönetici "
                "işlemleri işaretlenmiştir"
            ),
            SYSTEM_ACTIONS,
            SYSTEM_TOGGLES,
            parent=parent,
            task_manager=task_manager,
            preferences=preferences,
        )
