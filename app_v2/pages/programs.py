from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QWidget

from app_v2.dialogs import InstallerDialog
from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import (
    BASIC_PACKAGES,
    DRIVER_PACKAGES,
    PROGRAM_ACTIONS,
    PackageItem,
    ToolAction,
)
from app_v2.services.command_runner import run_command


class ProgramsPage(ToolsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Program Kurulumu",
            "Resmi Winget paketleri ve üretici kaynaklarından toplu uygulama kurulumu",
            PROGRAM_ACTIONS,
            custom_handlers={
                "basic_installer": self._open_basic_installer,
                "driver_installer": self._open_driver_installer,
            },
            parent=parent,
        )

    def _open_basic_installer(self, action: ToolAction) -> None:
        self._open_installer(
            action,
            "Temel Uygulamalar",
            "Kurulmasını istediğiniz uygulamaları seçin.",
            BASIC_PACKAGES,
        )

    def _open_driver_installer(self, action: ToolAction) -> None:
        self._open_installer(
            action,
            "Sürücü ve Üretici Araçları",
            "Resmi uygulamaları veya üretici destek bağlantılarını seçin.",
            DRIVER_PACKAGES,
        )

    def _open_installer(
        self,
        action: ToolAction,
        title: str,
        subtitle: str,
        packages: tuple[PackageItem, ...],
    ) -> None:
        dialog = InstallerDialog(title, subtitle, packages, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dialog.selected_packages()
        winget_packages = [item for item in selected if item.source == "winget"]
        urls = [item.package_id for item in selected if item.source == "url"]

        for url in urls:
            QDesktopServices.openUrl(QUrl(url))

        if winget_packages:
            command = " & ".join(
                "winget install -e "
                f"--id {item.package_id} "
                "--accept-package-agreements --accept-source-agreements"
                for item in winget_packages
            )
            ok, message = run_command(command, admin=True, keep_open=True)
            self.report(action.title, ok, message)
        elif urls:
            self.report(
                action.title,
                True,
                f"{len(urls)} resmi bağlantı tarayıcıda açıldı.",
            )
