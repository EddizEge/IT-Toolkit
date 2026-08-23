from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import QUICK_ACTIONS, ToolAction
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
)
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class QuickPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(
            "Hızlı Başlat",
            "Windows yönetim konsolları, tanılama ve kurtarma kısayolları",
            QUICK_ACTIONS,
            custom_handlers={"shutdown_schedule": self._schedule_shutdown},
            parent=parent,
            task_manager=task_manager,
            preferences=preferences,
        )

    def _schedule_shutdown(self, action: ToolAction) -> ExecutionPlan | None:
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
            return None
        return execution_plan_for_action(
            action,
            command=f"shutdown /s /t {minutes * 60}",
            target=f"Bu bilgisayar • {minutes} dakika sonra",
            admin_required=False,
            keep_open=False,
            effect=(
                f"Windows {minutes} dakika sonra oturumu kapatıp "
                "bilgisayarı kapatacak."
            ),
            interruption="Açık uygulamalar ve kullanıcı oturumu kapatılacak.",
            rollback=(
                "Süre dolmadan “Zamanlı kapatmayı iptal et” işlemiyle "
                "zamanlayıcı kaldırılabilir."
            ),
        )
