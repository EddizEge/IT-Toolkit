from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.registry import PAGE_ACTIONS, ToolAction
from app_v2.services.preferences import ToolPreferences
from app_v2.widgets import ActionTile


class SearchPage(QWidget):
    action_requested = Signal(str, object)

    PAGE_NAMES: ClassVar[dict[str, str]] = {
        "system": "Sistem Yönetimi",
        "network": "Ağ ve İnternet",
        "quick": "Hızlı Başlat",
        "data": "Veri Taşıma",
        "programs": "Program Kurulumu",
        "office": "Microsoft Office",
        "mail": "E-Posta / Outlook",
        "iso": "Windows ISO / USB",
    }

    def __init__(
        self,
        preferences: ToolPreferences | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.preferences = preferences
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(30, 26, 30, 34)
        self.layout.setSpacing(14)

        self.title = QLabel("Arama")
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("Araç adı veya açıklamasına göre sonuçlar")
        self.subtitle.setObjectName("PageSubtitle")
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.subtitle)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.layout.addLayout(self.grid)

        self.empty = QLabel("Aramak için üst alana en az iki karakter yazın.")
        self.empty.setObjectName("Muted")
        self.layout.addWidget(self.empty)
        self.layout.addStretch()

    def set_query(self, query: str) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        normalized = query.casefold().strip()
        results: list[tuple[str, ToolAction]] = []
        if len(normalized) >= 2:
            for page_key, actions in PAGE_ACTIONS.items():
                page_name = self.PAGE_NAMES[page_key]
                for action in actions:
                    haystack = (
                        f"{action.title} {action.description} {action.category} {page_name}"
                    ).casefold()
                    if normalized in haystack:
                        results.append((page_key, action))

        self.title.setText(f"“{query.strip()}” araması" if query.strip() else "Arama")
        self.subtitle.setText(f"{len(results)} araç bulundu")
        self.empty.setVisible(not results)
        if not results:
            self.empty.setText(
                "Sonuç bulunamadı." if len(normalized) >= 2 else "En az iki karakter yazın."
            )

        for index, (page_key, action) in enumerate(results):
            tile = ActionTile(action, self.preferences)
            tile.setToolTip(f"Modül: {self.PAGE_NAMES[page_key]}")
            tile.run_requested.connect(
                lambda selected, key=page_key: self.action_requested.emit(key, selected)
            )
            self.grid.addWidget(tile, index // 2, index % 2)
