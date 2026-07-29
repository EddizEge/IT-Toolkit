from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app_v2.dialogs import WifiQrDialog
from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import NETWORK_ACTIONS, NETWORK_TOGGLES, ToolAction


class NetworkPage(ToolsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Ağ ve İnternet",
            "Bağlantı tanılama, ağ onarımı ve yerel paylaşım araçları",
            NETWORK_ACTIONS,
            NETWORK_TOGGLES,
            {"wifi_qr": self._open_wifi_qr},
            parent,
        )

    def _open_wifi_qr(self, action: ToolAction) -> None:
        dialog = WifiQrDialog(self)
        dialog.exec()
