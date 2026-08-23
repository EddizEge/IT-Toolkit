from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_v2 import __version__
from app_v2.command_palette import CommandPalette
from app_v2.icons import monochrome_icon, navigation_icon
from app_v2.pages.dashboard import DashboardPage
from app_v2.pages.data import DataPage
from app_v2.pages.feedback import FeedbackPage
from app_v2.pages.health import HealthPage
from app_v2.pages.iso import IsoPage
from app_v2.pages.mail import MailPage
from app_v2.pages.network import NetworkPage
from app_v2.pages.office import OfficePage
from app_v2.pages.programs import ProgramsPage
from app_v2.pages.quick import QuickPage
from app_v2.pages.quick_access import QuickAccessPage
from app_v2.pages.search import SearchPage
from app_v2.pages.system import SystemPage
from app_v2.pages.tasks import TaskCenterPage
from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import TOGGLE_LOOKUP, ToolAction
from app_v2.services.action_safety import build_undo_plan
from app_v2.services.command_runner import is_running_as_admin
from app_v2.services.error_logging import get_logger
from app_v2.services.preferences import ToolPreferences
from app_v2.services.settings_service import get_toggle_status
from app_v2.services.system_monitor import FunctionWorker
from app_v2.services.task_manager import ACTIVE_STATUSES, TaskManager
from app_v2.services.update_service import ReleaseInfo, check_for_update
from app_v2.theme import create_app_icon
from app_v2.update_dialog import UpdateDialog
from app_v2.widgets import ToastNotification


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IT Toolkit — Windows Yönetim Merkezi")
        self.setWindowIcon(create_app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)

        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._current_page = "dashboard"
        self._page_before_search = "dashboard"
        self.task_manager = TaskManager(self)
        self.preferences = ToolPreferences(self)
        self.command_palette = CommandPalette(self.preferences, self)
        self.command_palette.action_requested.connect(self._run_search_result)
        self._update_pool = QThreadPool.globalInstance()
        self._update_workers: set[FunctionWorker] = set()
        self._available_update: ReleaseInfo | None = None

        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)
        root_layout.addWidget(right, 1)

        self._page_factories: dict[str, Callable[[], QWidget]] = {
            "dashboard": DashboardPage,
            "health": lambda: HealthPage(self.task_manager),
            "access": lambda: QuickAccessPage(
                self.preferences,
                self.task_manager,
            ),
            "tasks": lambda: TaskCenterPage(self.task_manager),
            "system": lambda: SystemPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "network": lambda: NetworkPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "quick": lambda: QuickPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "data": lambda: DataPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "programs": lambda: ProgramsPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "office": lambda: OfficePage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "mail": lambda: MailPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "iso": lambda: IsoPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            ),
            "feedback": FeedbackPage,
            "search": lambda: SearchPage(self.preferences),
        }

        self._shortcuts: list[QShortcut] = []
        self._add_shortcut("Ctrl+K", self.command_palette.open_for_search)
        self._add_shortcut("Alt+1", lambda: self._navigate_from_sidebar("dashboard"))
        self._add_shortcut("Alt+2", lambda: self._navigate_from_sidebar("access"))
        self._add_shortcut("Alt+3", lambda: self._navigate_from_sidebar("tasks"))
        self._add_shortcut("Alt+4", lambda: self._navigate_from_sidebar("health"))

        self.toast = ToastNotification(root)
        self.task_manager.notification.connect(self._show_task_notification)
        self.task_manager.counts_changed.connect(self._update_task_counts)
        self._update_task_counts(
            sum(
                task.status in ACTIVE_STATUSES
                for task in self.task_manager.tasks
            ),
            0,
            0,
        )
        self.show_page("dashboard")
        QTimer.singleShot(3_500, self._check_updates_silently)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(238)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(5)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        mark = QLabel()
        mark.setObjectName("BrandLogo")
        mark.setFixedSize(48, 48)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(self.windowIcon().pixmap(46, 46))
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand = QLabel("IT Toolkit")
        brand.setObjectName("BrandTitle")
        subtitle = QLabel("YÖNET • TANILA • ÇÖZ")
        subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(brand)
        brand_text.addWidget(subtitle)
        brand_row.addWidget(mark)
        brand_row.addLayout(brand_text)
        layout.addLayout(brand_row)
        layout.addSpacing(14)

        navigation = (
            ("dashboard", "Sistem Özeti", "dashboard", "GENEL"),
            ("health", "Akıllı Tanılama", "health", None),
            ("access", "Hızlı Erişim", "access", None),
            ("tasks", "Görev Merkezi", "tasks", None),
            ("system", "Sistem Yönetimi", "system", None),
            ("network", "Ağ ve İnternet", "network", "ARAÇLAR"),
            ("quick", "Hızlı Başlat", "quick", None),
            ("data", "Veri Taşıma", "data", None),
            ("programs", "Program Kurulumu", "programs", None),
            ("office", "Microsoft Office", "office", None),
            ("mail", "E-Posta / Outlook", "mail", None),
            ("iso", "Windows ISO / USB", "iso", None),
        )
        for key, text, icon_name, section_name in navigation:
            if section_name:
                section = QLabel(section_name)
                section.setObjectName("NavSection")
                layout.addWidget(section)
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(navigation_icon(icon_name))
            button.setIconSize(QSize(20, 20))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, page=key: self._navigate_from_sidebar(page)
            )
            self._nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch()
        self.update_button = QPushButton("GÜNCELLEMELER • V0.6 BETA 2")
        self.update_button.setObjectName("VersionPill")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.setToolTip("GitHub üzerinden güncellemeleri denetle")
        self.update_button.clicked.connect(self._open_update_dialog)
        layout.addWidget(self.update_button)
        version = QLabel(f"Beta {__version__}\nEdiz Ege Mercan")
        version.setObjectName("BrandSubtitle")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(68)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(25, 12, 25, 12)
        layout.setSpacing(16)

        self.context_label = QLabel("Sistem Özeti")
        self.context_label.setObjectName("SectionTitle")

        self.search = QLineEdit()
        self.search.setObjectName("GlobalSearch")
        self.search.setPlaceholderText("Araç ara…  Örn. SFC, disk, güncelleme")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            monochrome_icon("search"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.setMaximumWidth(440)
        self.search.textChanged.connect(self._on_search)

        admin = QLabel("YÖNETİCİ" if is_running_as_admin() else "STANDART OTURUM")
        admin.setObjectName("AdminBadge")
        if not is_running_as_admin():
            admin.setStyleSheet(
                "color:#F2A93B; background:#2D2A20; border:1px solid #5D5535;"
                "border-radius:9px; padding:5px 9px; font-size:11px; font-weight:700;"
            )

        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("Muted")
        self.status_label.setMaximumWidth(280)

        self.task_button = QPushButton("Görevler")
        self.task_button.setObjectName("GhostButton")
        self.task_button.setIcon(monochrome_icon("tasks"))
        self.task_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.task_button.clicked.connect(self._open_task_center)

        feedback_button = QPushButton("Geri Bildirim")
        feedback_button.setObjectName("GhostButton")
        feedback_button.setIcon(monochrome_icon("feedback"))
        feedback_button.setCursor(Qt.CursorShape.PointingHandCursor)
        feedback_button.clicked.connect(self._open_feedback)

        palette_button = QPushButton("Komutlar  Ctrl+K")
        palette_button.setObjectName("GhostButton")
        palette_button.setIcon(monochrome_icon("search"))
        palette_button.setToolTip("Komut paletini aç (Ctrl+K)")
        palette_button.setCursor(Qt.CursorShape.PointingHandCursor)
        palette_button.clicked.connect(self.command_palette.open_for_search)

        layout.addWidget(self.context_label)
        layout.addStretch()
        layout.addWidget(self.search, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(palette_button)
        layout.addWidget(self.task_button)
        layout.addWidget(feedback_button)
        layout.addWidget(admin)
        return topbar

    def _ensure_page(self, key: str) -> QWidget:
        if key not in self._pages:
            page = self._page_factories[key]()
            if isinstance(page, (SystemPage, ToolsPage)):
                page.status_message.connect(self.show_status)
            if isinstance(page, HealthPage):
                page.status_message.connect(self.show_status)
            if isinstance(page, QuickAccessPage):
                page.status_message.connect(self.show_status)
                page.action_requested.connect(self._run_search_result)
            if isinstance(page, TaskCenterPage):
                page.undo_requested.connect(self._run_undo)
            if isinstance(page, FeedbackPage):
                page.status_message.connect(self.show_status)
            if isinstance(page, SearchPage):
                page.action_requested.connect(self._run_search_result)
            self._pages[key] = page
            self.stack.addWidget(page)
        return self._pages[key]

    def show_page(self, key: str) -> None:
        page = self._ensure_page(key)
        self._current_page = key
        self.stack.setCurrentWidget(page)
        for nav_key, button in self._nav_buttons.items():
            button.setChecked(nav_key == key)

        titles = {
            "dashboard": "Sistem Özeti",
            "health": "Akıllı Tanılama",
            "access": "Hızlı Erişim",
            "tasks": "Görev Merkezi",
            "system": "Sistem Yönetimi",
            "network": "Ağ ve İnternet",
            "quick": "Hızlı Başlat",
            "data": "Veri Taşıma",
            "programs": "Program Kurulumu",
            "office": "Microsoft Office",
            "mail": "E-Posta / Outlook",
            "iso": "Windows ISO / USB",
            "feedback": "Geri Bildirim",
            "search": "Araç Arama",
        }
        self.context_label.setText(titles[key])

    def _add_shortcut(
        self,
        sequence: str,
        callback: Callable[[], None],
    ) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _on_search(self, query: str) -> None:
        if query.strip():
            if self._current_page != "search":
                self._page_before_search = self._current_page
            search_page = self._ensure_page("search")
            if isinstance(search_page, SearchPage):
                search_page.set_query(query)
            self._current_page = "search"
            self.stack.setCurrentWidget(search_page)
            self.context_label.setText("Araç Arama")
            for button in self._nav_buttons.values():
                button.setChecked(False)
        elif self._current_page == "search":
            self.show_page(self._page_before_search)

    def _navigate_from_sidebar(self, key: str) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        page = self._ensure_page(key)
        if isinstance(page, (SystemPage, ToolsPage)):
            page.filter_actions("")
        self.show_page(key)

    def _run_search_result(self, page_key: str, action: ToolAction) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        page = self._ensure_page(page_key)
        if isinstance(page, (SystemPage, ToolsPage)):
            page.filter_actions("")
        self.show_page(page_key)
        QTimer.singleShot(0, lambda: page.execute_action(action))

    def _open_task_center(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.show_page("tasks")

    def _run_undo(self, task_id: str) -> None:
        task = self.task_manager.task(task_id)
        if (
            task is None
            or task.status != "succeeded"
            or task.undo_state != "available"
            or not task.undo_key
            or not task.plan_id
        ):
            self.show_status(
                "Geri alma artık kullanılamıyor; görev durumu değişmiş olabilir.",
                False,
            )
            return

        if task.action_key.startswith("toggle:"):
            parts = task.action_key.split(":")
            toggle = TOGGLE_LOOKUP.get(parts[1]) if len(parts) == 3 else None
            current, status = (
                get_toggle_status(toggle.key)
                if toggle is not None
                else (None, "Ayar kaydı bulunamadı")
            )
            expected = len(parts) == 3 and parts[2] == "on"
            if current is None or current != expected:
                self.task_manager.invalidate_undo(task.id)
                self.show_status(
                    f"{task.title}: ayarın mevcut durumu değişti ({status}); "
                    "otomatik geri alma güvenlik için kapatıldı.",
                    False,
                )
                return

        plan = build_undo_plan(
            action_key=task.action_key,
            undo_key=task.undo_key,
            parent_plan_id=task.plan_id,
        )
        if plan is None:
            self.task_manager.invalidate_undo(task.id)
            self.show_status(
                f"{task.title}: kayıtlı geri alma planı doğrulanamadı.",
                False,
            )
            return
        system_page = self._ensure_page("system")
        task_center = self._ensure_page("tasks")
        if not isinstance(system_page, SystemPage):
            self.show_status("Geri alma ekranı hazırlanamadı.", False)
            return
        system_page.execute_plan(
            plan,
            record_recent=False,
            dialog_parent=task_center,
        )
        if isinstance(task_center, TaskCenterPage):
            task_center.show_task(task.id)

    def _open_feedback(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.show_page("feedback")

    def _open_update_dialog(self) -> None:
        dialog = UpdateDialog(self._available_update, self)
        dialog.exec()

    def _check_updates_silently(self) -> None:
        worker = FunctionWorker(check_for_update)
        self._update_workers.add(worker)

        def completed(release: ReleaseInfo | None) -> None:
            self._update_workers.discard(worker)
            if not release:
                return
            self._available_update = release
            self.update_button.setText(f"YENİ SÜRÜM • {release.tag}")
            self.update_button.setProperty("updateAvailable", True)
            self.update_button.style().unpolish(self.update_button)
            self.update_button.style().polish(self.update_button)
            self.toast.show_message(
                "Güncelleme hazır",
                f"{release.tag} indirilebilir.",
                "success",
            )
            self._position_toast()

        def failed(message: str) -> None:
            self._update_workers.discard(worker)
            get_logger().warning("Otomatik güncelleme denetimi: %s", message)

        worker.signals.completed.connect(completed)
        worker.signals.failed.connect(failed)
        self._update_pool.start(worker)

    def _update_task_counts(
        self,
        running: int,
        _succeeded: int,
        _failed: int,
    ) -> None:
        self.task_button.setText(
            f"Görevler • {running}" if running else "Görevler"
        )
        self.task_button.setProperty("activeTasks", running > 0)
        self.task_button.style().unpolish(self.task_button)
        self.task_button.style().polish(self.task_button)

    def _show_task_notification(
        self,
        title: str,
        message: str,
        tone: str,
    ) -> None:
        if tone == "danger":
            get_logger().error("Görev hatası | %s | %s", title, message)
        self.toast.show_message(title, message, tone)
        self._position_toast()

    def _position_toast(self) -> None:
        if not hasattr(self, "toast"):
            return
        margin = 22
        x = self.centralWidget().width() - self.toast.width() - margin
        y = self.centralWidget().height() - self.toast.height() - margin
        self.toast.move(max(margin, x), max(74, y))

    def show_status(self, message: str, success: bool) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"color: {'#35C78A' if success else '#F05D68'};"
        )
        QTimer.singleShot(5_000, self._clear_status)

    def _clear_status(self) -> None:
        self.status_label.setText("Hazır")
        self.status_label.setStyleSheet("")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_toast()

    def closeEvent(self, event: QCloseEvent) -> None:
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.monitor.stop()
        for page in tuple(self._pages.values()):
            if isinstance(page, ToolsPage):
                page.cancel_pending_recovery()
        self.task_manager.shutdown()
        super().closeEvent(event)
