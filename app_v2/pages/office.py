from __future__ import annotations

from PySide6.QtWidgets import QDialog, QWidget

from app_v2.dialogs import InstallerDialog
from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import OFFICE_ACTIONS, OFFICE_PACKAGES, ToolAction
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
)
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class OfficePage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(
            "Microsoft Office",
            "Resmi kurulum kaynakları, güvenli mod ve lisans tanılama araçları",
            OFFICE_ACTIONS,
            custom_handlers={"office_installer": self._open_installer},
            parent=parent,
            task_manager=task_manager,
            preferences=preferences,
        )

    def _open_installer(self, action: ToolAction) -> ExecutionPlan | None:
        dialog = InstallerDialog(
            "Microsoft Office Sürümleri",
            "Yalnızca sahip olduğunuz lisansa uygun resmi Microsoft sürümünü seçin.",
            OFFICE_PACKAGES,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        selected = dialog.selected_packages()
        return execution_plan_for_action(
            action,
            command="",
            urls=(package.package_id for package in selected),
            target=", ".join(package.name for package in selected),
            admin_required=False,
            keep_open=False,
            effect=(
                f"{len(selected)} resmi Microsoft indirme bağlantısı "
                "tarayıcıda açılacak."
            ),
            interruption="Sistem ayarlarında doğrudan değişiklik yapılmayacak.",
            rollback="Açılan bağlantılar kapatılarak işlem sonlandırılabilir.",
        )
