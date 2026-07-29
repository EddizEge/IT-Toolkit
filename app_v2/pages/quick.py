from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import QUICK_ACTIONS, ToolAction
from app_v2.services.task_manager import TaskManager


class QuickPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
    ) -> None:
        super().__init__(
            "Hızlı Başlat",
            "Windows yönetim konsolları, tanılama ve kurtarma kısayolları",
            QUICK_ACTIONS,
            custom_handlers={"shutdown_schedule": self._schedule_shutdown},
            parent=parent,
            task_manager=task_manager,
        )

    def _schedule_shutdown(self, action: ToolAction) -> None:
        minutes, accepted = QInputDialog.getInt(
            self,
            "Zamanlı kapatma",
            "Bilgisayar kaç dakika sonra kapatılsın?",
            60,
            1,
            10_080,
            1,
        )
        if not accepted:
            return
        self.start_command(
            action,
            f"shutdown /s /t {minutes * 60}",
            admin=False,
            keep_open=False,
        )
