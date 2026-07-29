from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import MAIL_ACTIONS, ToolAction
from app_v2.services.command_runner import run_command


class MailPage(ToolsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "E-Posta ve Outlook",
            "Klasik Outlook profil yönetimi, sorun giderme ve yerel arşiv yedekleme",
            MAIL_ACTIONS,
            custom_handlers={"pst_backup": self._backup_pst},
            parent=parent,
        )

    def _backup_pst(self, action: ToolAction) -> None:
        destination = QFileDialog.getExistingDirectory(
            self,
            "Outlook yedeği için hedef klasörü seçin",
        )
        if not destination:
            return

        source = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "Microsoft"
            / "Outlook"
        )
        target = Path(destination) / "IT_Toolkit_Outlook_Yedek"
        command = (
            f'robocopy "{source}" "{target}" *.pst *.ost '
            "/S /COPY:DAT /DCOPY:T /R:1 /W:1 /MT:8"
        )
        ok, message = run_command(command, admin=False, keep_open=True)
        self.report(action.title, ok, message)
