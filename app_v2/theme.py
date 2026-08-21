from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

COLORS = {
    "window": "#0D1117",
    "sidebar": "#10151D",
    "surface": "#151B24",
    "surface_alt": "#1A222D",
    "surface_hover": "#202A37",
    "border": "#293445",
    "border_soft": "#202A37",
    "text": "#F4F7FB",
    "muted": "#98A4B5",
    "primary": "#4C8DFF",
    "primary_hover": "#397BE7",
    "success": "#35C78A",
    "warning": "#F2A93B",
    "danger": "#F05D68",
}


def app_font(size: int = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Segoe UI Variable", size)
    if not font.exactMatch():
        font = QFont("Segoe UI", size)
    font.setWeight(weight)
    return font


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[1]
    return base / relative_path


def create_app_icon() -> QIcon:
    icon_path = resource_path("assets/brand/it_toolkit.ico")
    if icon_path.exists():
        return QIcon(str(icon_path))

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(COLORS["primary"]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 15, 15)
    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(app_font(22, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "IT")
    painter.end()
    return QIcon(pixmap)


def build_stylesheet() -> str:
    return f"""
    * {{
        font-family: "Segoe UI Variable", "Segoe UI";
        color: {COLORS["text"]};
    }}

    QMainWindow, QWidget#AppRoot {{
        background: {COLORS["window"]};
    }}

    QFrame#Sidebar {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #111824,
            stop:0.58 #0F151E,
            stop:1 #0C1118
        );
        border-right: 1px solid {COLORS["border_soft"]};
    }}

    QLabel#BrandLogo {{
        background: transparent;
    }}

    QLabel#BrandTitle {{
        font-size: 19px;
        font-weight: 700;
        letter-spacing: 0.2px;
    }}

    QLabel#BrandSubtitle {{
        color: #6F9FEF;
        font-size: 10px;
        font-weight: 600;
    }}

    QLabel#Muted, QLabel#CardSubtitle, QLabel#PageSubtitle {{
        color: {COLORS["muted"]};
    }}

    QLabel#NavSection {{
        color: #5D6A7B;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1.2px;
        padding: 8px 10px 3px 10px;
    }}

    QLabel#PageTitle {{
        font-size: 26px;
        font-weight: 700;
    }}

    QLabel#SectionTitle {{
        font-size: 15px;
        font-weight: 700;
    }}

    QPushButton#NavButton {{
        background: transparent;
        border: 0;
        border-radius: 9px;
        color: {COLORS["muted"]};
        font-size: 13px;
        font-weight: 600;
        min-height: 39px;
        padding: 0 12px;
        text-align: left;
    }}

    QPushButton#NavButton:hover {{
        background: {COLORS["surface_hover"]};
        color: {COLORS["text"]};
    }}

    QPushButton#NavButton:checked {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #20324F,
            stop:1 #18263B
        );
        color: #8BB6FF;
        border-left: 3px solid {COLORS["primary"]};
        padding-left: 9px;
    }}

    QPushButton#NavButton:disabled {{
        color: #536070;
    }}

    QFrame#TopBar {{
        background: #0E141D;
        border-bottom: 1px solid {COLORS["border_soft"]};
    }}

    QLineEdit#GlobalSearch {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        min-height: 38px;
        padding: 0 14px;
        selection-background-color: {COLORS["primary"]};
    }}

    QLineEdit#GlobalSearch:focus {{
        border: 1px solid {COLORS["primary"]};
    }}

    QLineEdit#DialogInput, QComboBox {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        min-height: 36px;
        padding: 0 10px;
        selection-background-color: {COLORS["primary"]};
    }}

    QLineEdit#PaletteSearch {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 10px;
        min-height: 42px;
        padding: 0 13px;
        font-size: 14px;
        selection-background-color: {COLORS["primary"]};
    }}

    QLineEdit#PaletteSearch:focus {{
        border: 1px solid {COLORS["primary"]};
    }}

    QLineEdit#DialogInput:focus, QComboBox:focus {{
        border: 1px solid {COLORS["primary"]};
    }}

    QComboBox::drop-down {{
        border: 0;
        width: 28px;
    }}

    QComboBox QAbstractItemView {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border"]};
        selection-background-color: #1D2B42;
    }}

    QCheckBox {{
        spacing: 10px;
        color: {COLORS["text"]};
        min-height: 30px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1px solid {COLORS["border"]};
        border-radius: 5px;
        background: {COLORS["surface_alt"]};
    }}

    QCheckBox::indicator:checked {{
        background: {COLORS["primary"]};
        border: 1px solid {COLORS["primary"]};
    }}

    QDialog {{
        background: {COLORS["window"]};
    }}

    QLabel#AdminBadge {{
        background: #172D25;
        border: 1px solid #285A47;
        border-radius: 9px;
        color: {COLORS["success"]};
        font-size: 11px;
        font-weight: 700;
        padding: 5px 9px;
    }}

    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: 0;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 9px;
        margin: 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #354154;
        border-radius: 4px;
        min-height: 35px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #46546A;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QFrame#Card, QFrame#Panel, QFrame#ActionTile, QFrame#ToggleRow,
    QFrame#TaskSummaryCard, QFrame#QuickAccessRow, QFrame#HealthSummary,
    QFrame#HealthMethod, QFrame#HealthFinding {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border_soft"]};
        border-radius: 13px;
    }}

    QFrame#HealthSummary[tone="good"] {{ border: 1px solid #285A47; }}
    QFrame#HealthSummary[tone="info"] {{ border: 1px solid #31558A; }}
    QFrame#HealthSummary[tone="warning"] {{ border: 1px solid #66562D; }}
    QFrame#HealthSummary[tone="critical"] {{ border: 1px solid #6B323B; }}

    QFrame#HealthMethod {{
        background: #111923;
        border: 1px solid #253349;
    }}

    QFrame#HealthFinding[severity="good"] {{ border-left: 3px solid {COLORS["success"]}; }}
    QFrame#HealthFinding[severity="info"] {{ border-left: 3px solid {COLORS["primary"]}; }}
    QFrame#HealthFinding[severity="warning"] {{ border-left: 3px solid {COLORS["warning"]}; }}
    QFrame#HealthFinding[severity="critical"] {{ border-left: 3px solid {COLORS["danger"]}; }}

    QFrame#HealthDivider {{
        color: {COLORS["border"]};
        background: {COLORS["border"]};
        min-width: 1px;
        max-width: 1px;
    }}

    QLabel#HealthScore {{
        font-size: 32px;
        font-weight: 750;
    }}

    QLabel#HealthScore[tone="good"] {{ color: {COLORS["success"]}; }}
    QLabel#HealthScore[tone="info"] {{ color: #6EA4FF; }}
    QLabel#HealthScore[tone="warning"] {{ color: {COLORS["warning"]}; }}
    QLabel#HealthScore[tone="critical"] {{ color: {COLORS["danger"]}; }}

    QLabel#HealthCounts {{
        color: #B9C5D5;
        font-size: 12px;
        font-weight: 650;
    }}

    QLabel#HealthRecommendation {{ color: #C8D3E1; }}

    QLabel#HealthMarker {{
        border-radius: 17px;
        font-size: 16px;
        font-weight: 800;
    }}

    QLabel#HealthMarker[severity="good"] {{ background: #172D25; color: {COLORS["success"]}; }}
    QLabel#HealthMarker[severity="info"] {{ background: #17253A; color: #78A8F7; }}
    QLabel#HealthMarker[severity="warning"] {{ background: #2D2A20; color: {COLORS["warning"]}; }}
    QLabel#HealthMarker[severity="critical"] {{ background: #352226; color: {COLORS["danger"]}; }}

    QLabel#HealthImpact {{
        border-radius: 8px;
        font-size: 13px;
        font-weight: 750;
        padding: 5px 8px;
    }}

    QLabel#HealthImpact[severity="warning"] {{ background: #2D2A20; color: {COLORS["warning"]}; }}
    QLabel#HealthImpact[severity="critical"] {{ background: #352226; color: {COLORS["danger"]}; }}

    QFrame#ActionTile:hover {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border"]};
    }}

    QLabel#MetricValue {{
        font-size: 27px;
        font-weight: 700;
    }}

    QLabel#MetricValue[tone="blue"] {{ color: #6EA4FF; }}
    QLabel#MetricValue[tone="green"] {{ color: {COLORS["success"]}; }}
    QLabel#MetricValue[tone="amber"] {{ color: {COLORS["warning"]}; }}

    QLabel#TaskSummaryValue {{
        font-size: 24px;
        font-weight: 700;
    }}

    QLabel#TaskSummaryValue[tone="blue"] {{ color: #6EA4FF; }}
    QLabel#TaskSummaryValue[tone="green"] {{ color: {COLORS["success"]}; }}
    QLabel#TaskSummaryValue[tone="red"] {{ color: {COLORS["danger"]}; }}

    QProgressBar#MetricProgress, QProgressBar#DiskProgress {{
        background: #273140;
        border: 0;
        border-radius: 3px;
        max-height: 6px;
        min-height: 6px;
        text-align: center;
    }}

    QProgressBar#MetricProgress::chunk {{
        background: {COLORS["primary"]};
        border-radius: 3px;
    }}

    QProgressBar#MetricProgress[tone="green"]::chunk {{
        background: {COLORS["success"]};
    }}

    QProgressBar#DiskProgress::chunk {{
        background: {COLORS["primary"]};
        border-radius: 3px;
    }}

    QProgressBar#DiskProgress[usage="warning"]::chunk {{
        background: {COLORS["warning"]};
    }}

    QProgressBar#DiskProgress[usage="danger"]::chunk {{
        background: {COLORS["danger"]};
    }}

    QProgressBar#TaskProgress {{
        background: #273140;
        border: 0;
        border-radius: 5px;
        color: {COLORS["text"]};
        min-height: 10px;
        max-height: 10px;
        text-align: center;
    }}

    QProgressBar#HealthProgress {{
        background: #273140;
        border: 0;
        border-radius: 4px;
        min-height: 8px;
        max-height: 8px;
    }}

    QProgressBar#HealthProgress::chunk {{ background: {COLORS["primary"]}; border-radius: 4px; }}
    QProgressBar#HealthProgress[tone="good"]::chunk {{ background: {COLORS["success"]}; }}
    QProgressBar#HealthProgress[tone="warning"]::chunk {{ background: {COLORS["warning"]}; }}
    QProgressBar#HealthProgress[tone="critical"]::chunk {{ background: {COLORS["danger"]}; }}

    QProgressBar#TaskProgress::chunk {{
        background: {COLORS["primary"]};
        border-radius: 5px;
    }}

    QListWidget#TaskList {{
        background: transparent;
        border: 0;
        outline: 0;
    }}

    QListWidget#PaletteList {{
        background: transparent;
        border: 0;
        outline: 0;
    }}

    QListWidget#PaletteList::item {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border_soft"]};
        border-radius: 9px;
        color: {COLORS["muted"]};
        min-height: 50px;
        padding: 9px 12px;
        margin: 3px 0;
    }}

    QListWidget#PaletteList::item:selected {{
        background: #20324F;
        border: 1px solid #31558A;
        color: #B9D2FF;
    }}

    QListWidget#TaskList::item {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border_soft"]};
        border-radius: 9px;
        color: {COLORS["muted"]};
        min-height: 48px;
        padding: 8px 10px;
    }}

    QListWidget#TaskList::item:hover {{
        background: {COLORS["surface_hover"]};
        color: {COLORS["text"]};
    }}

    QListWidget#TaskList::item:selected {{
        background: #20324F;
        border: 1px solid #31558A;
        color: #A9C8FF;
    }}

    QPlainTextEdit#TaskOutput, QPlainTextEdit#FeedbackText {{
        background: #090D13;
        border: 1px solid {COLORS["border_soft"]};
        border-radius: 9px;
        color: #C8D2DF;
        padding: 10px;
        selection-background-color: #284B7E;
    }}

    QPlainTextEdit#FeedbackText:focus {{
        border: 1px solid {COLORS["primary"]};
    }}

    QSplitter::handle {{
        background: transparent;
        width: 10px;
    }}

    QPushButton#PrimaryButton, QPushButton#RunButton {{
        background: {COLORS["primary"]};
        border: 0;
        border-radius: 8px;
        color: white;
        font-weight: 700;
        min-height: 34px;
        padding: 0 14px;
    }}

    QPushButton#PrimaryButton:hover, QPushButton#RunButton:hover {{
        background: {COLORS["primary_hover"]};
    }}

    QPushButton#RunButton[risk="caution"] {{
        background: #56401D;
        color: #FFD98A;
    }}

    QPushButton#RunButton[risk="caution"]:hover {{
        background: #6A4E20;
    }}

    QPushButton#RunButton[risk="danger"] {{
        background: #51242A;
        color: #FFACB3;
    }}

    QPushButton#RunButton[risk="danger"]:hover {{
        background: #672B33;
    }}

    QPushButton#GhostButton {{
        background: transparent;
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        color: {COLORS["muted"]};
        min-height: 32px;
        padding: 0 12px;
    }}

    QPushButton#GhostButton:hover {{
        background: {COLORS["surface_hover"]};
        color: {COLORS["text"]};
    }}

    QPushButton#GhostButton:disabled {{
        background: transparent;
        border-color: #252D39;
        color: #536070;
    }}

    QPushButton#GhostButton[activeTasks="true"] {{
        background: #20324F;
        border: 1px solid #31558A;
        color: #8BB6FF;
    }}

    QPushButton#FavoriteButton, QPushButton#IconButton {{
        background: transparent;
        border: 1px solid {COLORS["border"]};
        border-radius: 8px;
        color: {COLORS["muted"]};
        min-width: 30px;
        min-height: 30px;
        max-width: 34px;
        max-height: 34px;
        font-size: 17px;
        font-weight: 700;
    }}

    QPushButton#FavoriteButton:hover, QPushButton#IconButton:hover {{
        background: {COLORS["surface_hover"]};
        color: {COLORS["text"]};
    }}

    QPushButton#FavoriteButton[selected="true"] {{
        background: #3B311C;
        border: 1px solid #6A5727;
        color: #FFD26A;
    }}

    QLabel#EmptyState {{
        background: #111720;
        border: 1px dashed {COLORS["border"]};
        border-radius: 10px;
        color: {COLORS["muted"]};
        padding: 14px;
    }}

    QPushButton#DangerButton {{
        background: #51242A;
        border: 0;
        border-radius: 8px;
        color: #FFACB3;
        font-weight: 700;
        min-height: 34px;
        padding: 0 14px;
    }}

    QPushButton#DangerButton:hover {{
        background: #672B33;
    }}

    QPushButton#DangerButton:disabled {{
        background: #2A2023;
        color: #73545A;
    }}

    QFrame#ToastNotification {{
        background: #15231F;
        border: 1px solid #2A604B;
        border-radius: 12px;
    }}

    QFrame#ToastNotification[tone="warning"] {{
        background: #282318;
        border: 1px solid #66562D;
    }}

    QFrame#ToastNotification[tone="danger"] {{
        background: #2B1C20;
        border: 1px solid #6B323B;
    }}

    QPushButton#ToastCloseButton {{
        background: transparent;
        border: 0;
        border-radius: 6px;
        color: {COLORS["muted"]};
        font-size: 18px;
        font-weight: 600;
    }}

    QPushButton#ToastCloseButton:hover {{
        background: {COLORS["surface_hover"]};
        color: {COLORS["text"]};
    }}

    QLabel#Badge {{
        background: #202A37;
        border: 1px solid {COLORS["border"]};
        border-radius: 7px;
        color: #B3BDCA;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 7px;
    }}

    QLabel#VersionPill, QPushButton#VersionPill {{
        background: #17253A;
        border: 1px solid #2A456B;
        border-radius: 8px;
        color: #78A8F7;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.8px;
        padding: 4px 8px;
    }}

    QPushButton#VersionPill:hover {{
        background: #203553;
        border-color: #3A6396;
    }}

    QPushButton#VersionPill[updateAvailable="true"] {{
        background: #193329;
        border-color: #2E6A50;
        color: #6EE0AD;
    }}

    QLabel#StatusBadge[status="on"] {{
        background: #172D25;
        border: 1px solid #285A47;
        border-radius: 8px;
        color: {COLORS["success"]};
        font-size: 11px;
        font-weight: 700;
        padding: 4px 8px;
    }}

    QLabel#StatusBadge[status="off"] {{
        background: #352226;
        border: 1px solid #66323A;
        border-radius: 8px;
        color: #FF9AA3;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 8px;
    }}

    QLabel#StatusBadge[status="unknown"] {{
        background: #2D2A20;
        border: 1px solid #5D5535;
        border-radius: 8px;
        color: #E9D68B;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 8px;
    }}

    QToolTip {{
        background: {COLORS["surface_alt"]};
        border: 1px solid {COLORS["border"]};
        color: {COLORS["text"]};
        padding: 6px;
    }}

    QMessageBox {{
        background: {COLORS["surface"]};
    }}
    """
