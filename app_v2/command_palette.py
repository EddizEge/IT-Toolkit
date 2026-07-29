from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_v2.icons import monochrome_icon
from app_v2.registry import PAGE_ACTIONS, ToolAction
from app_v2.services.preferences import ToolPreferences


@dataclass(frozen=True)
class PaletteResult:
    page_key: str
    action: ToolAction
    score: int


def rank_actions(
    query: str,
    favorite_keys: tuple[str, ...] = (),
) -> list[PaletteResult]:
    normalized = query.casefold().strip()
    results: list[PaletteResult] = []
    for page_key, actions in PAGE_ACTIONS.items():
        for action in actions:
            title = action.title.casefold()
            category = action.category.casefold()
            description = action.description.casefold()
            if not normalized:
                score = 100 if action.key in favorite_keys else 10
            elif title.startswith(normalized):
                score = 500
            elif normalized in title:
                score = 350
            elif normalized in category:
                score = 220
            elif normalized in description:
                score = 140
            else:
                continue
            if action.key in favorite_keys:
                score += 35
            results.append(PaletteResult(page_key, action, score))
    return sorted(
        results,
        key=lambda item: (-item.score, item.action.title.casefold()),
    )


class CommandPalette(QDialog):
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
        preferences: ToolPreferences,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.preferences = preferences
        self._results: list[PaletteResult] = []
        self.setWindowTitle("Komut Paleti")
        self.setModal(True)
        self.resize(660, 510)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("Aracı çalıştır")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Yazarak filtreleyin • ↑↓ seçin • Enter çalıştırır • Esc kapatır"
        )
        subtitle.setObjectName("PageSubtitle")

        self.search = QLineEdit()
        self.search.setObjectName("PaletteSearch")
        self.search.setPlaceholderText("SFC, disk, ağ sıfırlama…")
        self.search.addAction(
            monochrome_icon("search"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._activate_current)
        self.search.installEventFilter(self)

        self.results = QListWidget()
        self.results.setObjectName("PaletteList")
        self.results.itemActivated.connect(lambda _item: self._activate_current())

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.search)
        layout.addWidget(self.results, 1)
        self._refresh("")

    def open_for_search(self) -> None:
        self.search.clear()
        self._refresh("")
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def _refresh(self, query: str) -> None:
        self._results = rank_actions(query, self.preferences.favorites)[:25]
        self.results.clear()
        for result in self._results:
            favorite = "★  " if self.preferences.is_favorite(result.action.key) else ""
            item = QListWidgetItem(
                f"{favorite}{result.action.title}\n"
                f"{self.PAGE_NAMES[result.page_key]}  •  {result.action.category}"
            )
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _activate_current(self) -> None:
        item = self.results.currentItem()
        if not item:
            return
        result = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(result, PaletteResult):
            return
        self.accept()
        self.action_requested.emit(result.page_key, result.action)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate_current()
            return
        if event.key() == Qt.Key.Key_Down:
            row = min(self.results.count() - 1, self.results.currentRow() + 1)
            self.results.setCurrentRow(row)
            return
        if event.key() == Qt.Key.Key_Up:
            self.results.setCurrentRow(max(0, self.results.currentRow() - 1))
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.search and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent):
                if key_event.key() == Qt.Key.Key_Down:
                    row = min(
                        self.results.count() - 1,
                        self.results.currentRow() + 1,
                    )
                    self.results.setCurrentRow(row)
                    return True
                if key_event.key() == Qt.Key.Key_Up:
                    self.results.setCurrentRow(
                        max(0, self.results.currentRow() - 1)
                    )
                    return True
        return super().eventFilter(watched, event)
