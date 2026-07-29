from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(
            "Bu modül yeni arayüze taşınma sırasındadır.\n"
            "Tamamlanana kadar mevcut IT Toolkit sürümündeki işlevler korunacaktır."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addSpacing(10)
        layout.addWidget(subtitle)
