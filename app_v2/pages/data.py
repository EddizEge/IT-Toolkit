from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import DATA_ACTIONS, DATA_TOGGLES, ToolAction
from app_v2.services.task_manager import TaskManager


class DataPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
    ) -> None:
        super().__init__(
            "Veri Taşıma ve Yedekleme",
            "Kullanıcı verilerini güvenli biçimde kopyalama, envanter ve disk araçları",
            DATA_ACTIONS,
            DATA_TOGGLES,
            {
                "profile_backup": self._backup_profile,
                "take_ownership": self._take_ownership,
                "wipe_free_space": self._wipe_free_space,
            },
            parent=parent,
            task_manager=task_manager,
        )

    def _backup_profile(self, action: ToolAction) -> None:
        destination = QFileDialog.getExistingDirectory(
            self,
            "Profil yedeği için hedef klasörü seçin",
        )
        if not destination:
            return

        profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        commands: list[str] = []
        for folder in ("Desktop", "Documents", "Downloads", "Pictures"):
            source = profile / folder
            target = Path(destination) / "IT_Toolkit_Profil_Yedek" / folder
            commands.append(
                f'robocopy "{source}" "{target}" /E /COPY:DAT /DCOPY:T /R:1 /W:1 /MT:8'
            )
        self.start_command(
            action,
            " & ".join(commands),
            admin=False,
            keep_open=False,
            success_codes=tuple(range(8)),
        )

    def _take_ownership(self, action: ToolAction) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sahipliği alınacak klasörü seçin",
        )
        if not folder:
            return
        self.start_command(
            action,
            f'takeown /f "{folder}" /r /d y & icacls "{folder}" /grant administrators:F /t',
            admin=True,
            keep_open=True,
        )

    def _wipe_free_space(self, action: ToolAction) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Boş alanı temizlenecek sürücüden bir klasör seçin",
            "C:\\",
        )
        if not folder:
            return
        drive, _ = os.path.splitdrive(folder)
        if not drive:
            self.report(action.title, False, "Yerel bir Windows sürücüsü seçin.")
            return
        self.start_command(
            action,
            f"cipher /w:{drive}\\",
            admin=True,
            keep_open=True,
        )
