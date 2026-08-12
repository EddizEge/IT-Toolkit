from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app_v2.theme import COLORS

SVG_PATHS = {
    "dashboard": """
        <rect x="3" y="3" width="7" height="7" rx="2"/>
        <rect x="14" y="3" width="7" height="7" rx="2"/>
        <rect x="3" y="14" width="7" height="7" rx="2"/>
        <rect x="14" y="14" width="7" height="7" rx="2"/>
    """,
    "health": """
        <path d="M3 12h4l2.2-5 3.3 10 2.2-5H21"/>
        <path d="M12 21C7 18.1 4 15.3 4 10.5A4.5 4.5 0 0 1 12 7.7a4.5 4.5 0 0 1 8 2.8c0 4.8-3 7.6-8 10.5z"/>
    """,
    "system": """
        <path d="M4 7h10M18 7h2M4 17h2M10 17h10"/>
        <circle cx="16" cy="7" r="2"/>
        <circle cx="8" cy="17" r="2"/>
    """,
    "network": """
        <circle cx="12" cy="12" r="9"/>
        <path d="M3.5 9h17M3.5 15h17M12 3c2.4 2.5 3.6 5.5 3.6 9s-1.2 6.5-3.6 9c-2.4-2.5-3.6-5.5-3.6-9S9.6 5.5 12 3z"/>
    """,
    "quick": """
        <path d="M13.3 2.8 5.8 13h5l-.9 8.2 7.8-11h-5.1l.7-7.4z"/>
    """,
    "data": """
        <ellipse cx="12" cy="5" rx="8" ry="3"/>
        <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>
    """,
    "programs": """
        <path d="M12 3v11M8 10l4 4 4-4"/>
        <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
    """,
    "office": """
        <path d="M6 3h8l4 4v14H6z"/>
        <path d="M14 3v5h5M9 12h6M9 16h6"/>
    """,
    "mail": """
        <rect x="3" y="5" width="18" height="14" rx="3"/>
        <path d="m4 7 8 6 8-6"/>
    """,
    "iso": """
        <circle cx="12" cy="12" r="9"/>
        <circle cx="12" cy="12" r="2.5"/>
        <path d="M12 3v3M21 12h-3M12 21v-3M3 12h3"/>
    """,
    "search": """
        <circle cx="10.5" cy="10.5" r="6.5"/>
        <path d="m15.5 15.5 5 5"/>
    """,
    "tasks": """
        <rect x="4" y="3" width="16" height="18" rx="3"/>
        <path d="m8 8 1.5 1.5L12 7M14 9h3M8 14l1.5 1.5L12 13M14 15h3"/>
    """,
    "access": """
        <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3z"/>
    """,
}


def _render_icon(name: str, color: str, size: int = 40) -> QPixmap:
    paths = SVG_PATHS[name]
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
         fill="none" stroke="{color}" stroke-width="1.8"
         stroke-linecap="round" stroke-linejoin="round">
        {paths}
    </svg>
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return pixmap


def navigation_icon(name: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(
        _render_icon(name, COLORS["muted"]),
        QIcon.Mode.Normal,
        QIcon.State.Off,
    )
    icon.addPixmap(
        _render_icon(name, COLORS["primary"]),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    icon.addPixmap(
        _render_icon(name, COLORS["text"]),
        QIcon.Mode.Active,
        QIcon.State.Off,
    )
    icon.addPixmap(
        _render_icon(name, "#77A8FF"),
        QIcon.Mode.Active,
        QIcon.State.On,
    )
    return icon


def monochrome_icon(name: str, color: str | None = None) -> QIcon:
    return QIcon(_render_icon(name, color or COLORS["muted"]))
