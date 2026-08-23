from __future__ import annotations

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
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
)
from app_v2.services.command_builder import fail_fast_sequence
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager


class ProgramsPage(ToolsPage):
    def __init__(
        self,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(
            "Program Kurulumu",
            "Resmi Winget paketleri ve üretici kaynaklarından toplu uygulama kurulumu",
            PROGRAM_ACTIONS,
            custom_handlers={
                "basic_installer": self._open_basic_installer,
                "driver_installer": self._open_driver_installer,
            },
            parent=parent,
            task_manager=task_manager,
            preferences=preferences,
        )

    def _open_basic_installer(
        self,
        action: ToolAction,
    ) -> ExecutionPlan | None:
        return self._open_installer(
            action,
            "Temel Uygulamalar",
            "Kurulmasını istediğiniz uygulamaları seçin.",
            BASIC_PACKAGES,
        )

    def _open_driver_installer(
        self,
        action: ToolAction,
    ) -> ExecutionPlan | None:
        return self._open_installer(
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
    ) -> ExecutionPlan | None:
        dialog = InstallerDialog(title, subtitle, packages, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        selected = dialog.selected_packages()
        winget_packages = [item for item in selected if item.source == "winget"]
        urls = tuple(
            item.package_id for item in selected if item.source == "url"
        )
        command = ""
        if winget_packages:
            command = fail_fast_sequence(
                "winget install -e "
                f"--id {item.package_id} "
                "--accept-package-agreements --accept-source-agreements"
                for item in winget_packages
            )
        selected_names = ", ".join(item.name for item in selected)
        effect_parts = []
        if winget_packages:
            effect_parts.append(
                f"{len(winget_packages)} paket Winget ile kurulacak"
            )
        if urls:
            effect_parts.append(
                f"{len(urls)} resmi üretici bağlantısı tarayıcıda açılacak"
            )
        return execution_plan_for_action(
            action,
            command=command,
            urls=urls,
            target=selected_names,
            admin_required=bool(winget_packages),
            keep_open=bool(winget_packages),
            effect="; ".join(effect_parts) + ".",
            interruption=(
                "Kurulumlar açık uygulamaların kapatılmasını veya daha sonra "
                "yeniden başlatmayı gerektirebilir."
                if winget_packages
                else "Sistem ayarlarında doğrudan değişiklik yapılmayacak."
            ),
            rollback=(
                "Kurulan paketler Windows uygulama kaldırma ekranından "
                "kaldırılabilir."
                if winget_packages
                else "Açılan bağlantılar kapatılarak işlem sonlandırılabilir."
            ),
        )
