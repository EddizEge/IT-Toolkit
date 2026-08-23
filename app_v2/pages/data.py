from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import DATA_ACTIONS, DATA_TOGGLES, ToolAction
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
)
from app_v2.services.command_builder import (
    aggregate_sequence,
    fail_fast_sequence,
)
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class DataPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
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
            preferences=preferences,
        )

    def _backup_profile(self, action: ToolAction) -> ExecutionPlan | None:
        destination = QFileDialog.getExistingDirectory(
            self,
            "Profil yedeği için hedef klasörü seçin",
        )
        if not destination:
            return None

        profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        commands: list[str] = []
        for folder in ("Desktop", "Documents", "Downloads", "Pictures"):
            source = profile / folder
            target = Path(destination) / "IT_Toolkit_Profil_Yedek" / folder
            commands.append(
                f'robocopy "{source}" "{target}" /E /COPY:DAT /DCOPY:T /R:1 /W:1 /MT:8'
            )
        return execution_plan_for_action(
            action,
            command=aggregate_sequence(commands, max_success_code=7),
            target=str(Path(destination) / "IT_Toolkit_Profil_Yedek"),
            admin_required=False,
            keep_open=False,
            success_codes=tuple(range(8)),
        )

    def _take_ownership(self, action: ToolAction) -> ExecutionPlan | None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sahipliği alınacak klasörü seçin",
        )
        if not folder:
            return None
        return execution_plan_for_action(
            action,
            command=fail_fast_sequence(
                (
                    f'takeown /f "{folder}" /r /d y',
                    f'icacls "{folder}" /grant administrators:F /t',
                )
            ),
            target=folder,
            admin_required=True,
            keep_open=True,
        )

    def _wipe_free_space(self, action: ToolAction) -> ExecutionPlan | None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Boş alanı temizlenecek sürücüden bir klasör seçin",
            "C:\\",
        )
        if not folder:
            return None
        drive, _ = os.path.splitdrive(folder)
        if not drive:
            self.report(action.title, False, "Yerel bir Windows sürücüsü seçin.")
            return None
        return execution_plan_for_action(
            action,
            command=f"cipher /w:{drive}\\",
            target=f"{drive}\\ sürücüsünün boş alanı",
            admin_required=True,
            keep_open=True,
        )
