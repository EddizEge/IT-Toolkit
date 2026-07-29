from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import ISO_ACTIONS


class IsoPage(ToolsPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Windows ISO ve USB",
            "Resmi Windows kurulum medyaları ve önyüklenebilir USB hazırlama araçları",
            ISO_ACTIONS,
            parent=parent,
        )
