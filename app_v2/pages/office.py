from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QWidget

from app_v2.dialogs import InstallerDialog
from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import OFFICE_ACTIONS, OFFICE_PACKAGES, ToolAction
from app_v2.services.task_manager import TaskManager


class OfficePage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
    ) -> None:
        super().__init__(
            "Microsoft Office",
            "Resmi kurulum kaynakları, güvenli mod ve lisans tanılama araçları",
            OFFICE_ACTIONS,
            custom_handlers={"office_installer": self._open_installer},
            parent=parent,
            task_manager=task_manager,
        )

    def _open_installer(self, action: ToolAction) -> None:
        dialog = InstallerDialog(
            "Microsoft Office Sürümleri",
            "Yalnızca sahip olduğunuz lisansa uygun resmi Microsoft sürümünü seçin.",
            OFFICE_PACKAGES,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_packages()
        for package in selected:
            QDesktopServices.openUrl(QUrl(package.package_id))
        self.report(
            action.title,
            True,
            f"{len(selected)} resmi Microsoft indirme bağlantısı açıldı.",
        )
