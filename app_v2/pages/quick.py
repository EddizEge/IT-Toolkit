from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import QUICK_ACTIONS, ToolAction
from app_v2.services.command_runner import run_command


class QuickPage(ToolsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Hızlı Başlat",
            "Windows yönetim konsolları, tanılama ve kurtarma kısayolları",
            QUICK_ACTIONS,
            custom_handlers={"shutdown_schedule": self._schedule_shutdown},
            parent=parent,
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
        ok, message = run_command(
            f"shutdown /s /t {minutes * 60}",
            admin=False,
            keep_open=False,
        )
        self.report(action.title, ok, f"{minutes} dakika için {message.lower()}")
