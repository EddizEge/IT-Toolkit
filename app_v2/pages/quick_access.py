from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.action_confirmation import confirm_operation
from app_v2.presets import TECHNICIAN_PRESETS, TechnicianPreset
from app_v2.registry import ToolAction, find_action
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_preset,
)
from app_v2.services.audit_log import AuditLog
from app_v2.services.preferences import ToolPreferences
from app_v2.services.task_manager import TaskManager
from app_v2.widgets import clear_layout


class QuickAccessPage(QWidget):
    action_requested = Signal(str, object)
    status_message = Signal(str, bool)

    def __init__(
        self,
        preferences: ToolPreferences,
        task_manager: TaskManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.preferences = preferences
        self.task_manager = task_manager

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 34)
        layout.setSpacing(16)

        title = QLabel("Hızlı Erişim")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Sık kullandığınız araçları sabitleyin, son işlemlere dönün ve hazır teknisyen akışlarını başlatın."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        favorites_title = QLabel("Favoriler")
        favorites_title.setObjectName("SectionTitle")
        layout.addWidget(favorites_title)
        self.favorites_layout = QVBoxLayout()
        self.favorites_layout.setSpacing(9)
        layout.addLayout(self.favorites_layout)

        recent_row = QHBoxLayout()
        recent_title = QLabel("Son kullanılanlar")
        recent_title.setObjectName("SectionTitle")
        clear_button = QPushButton("Geçmişi temizle")
        clear_button.setObjectName("GhostButton")
        clear_button.clicked.connect(self.preferences.clear_recents)
        recent_row.addWidget(recent_title)
        recent_row.addStretch()
        recent_row.addWidget(clear_button)
        layout.addLayout(recent_row)
        self.recents_layout = QVBoxLayout()
        self.recents_layout.setSpacing(9)
        layout.addLayout(self.recents_layout)

        preset_title = QLabel("Teknisyen hazır akışları")
        preset_title.setObjectName("SectionTitle")
        layout.addWidget(preset_title)
        for preset in TECHNICIAN_PRESETS:
            layout.addWidget(self._preset_row(preset))
        layout.addStretch()

        self.preferences.favorites_changed.connect(self.refresh)
        self.preferences.recents_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.favorites_layout)
        clear_layout(self.recents_layout)
        if not self.preferences.favorites:
            self.favorites_layout.addWidget(
                self._empty_label(
                    "Henüz favori yok. Araç kartlarındaki yıldız düğmesiyle ekleyebilirsiniz."
                )
            )
        for action_key in self.preferences.favorites:
            found = find_action(action_key)
            if found:
                page_key, action = found
                self.favorites_layout.addWidget(
                    self._action_row(page_key, action, favorite=True)
                )

        if not self.preferences.recents:
            self.recents_layout.addWidget(
                self._empty_label("Çalıştırdığınız araçlar burada görünecek.")
            )
        for action_key in self.preferences.recents[:6]:
            found = find_action(action_key)
            if found:
                page_key, action = found
                self.recents_layout.addWidget(
                    self._action_row(page_key, action, favorite=False)
                )

    @staticmethod
    def _empty_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("EmptyState")
        label.setWordWrap(True)
        return label

    def _action_row(
        self,
        page_key: str,
        action: ToolAction,
        *,
        favorite: bool,
    ) -> QFrame:
        row = QFrame()
        row.setObjectName("QuickAccessRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 11, 13, 11)
        layout.setSpacing(9)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(action.title)
        title.setObjectName("SectionTitle")
        detail = QLabel(action.category)
        detail.setObjectName("CardSubtitle")
        text.addWidget(title)
        text.addWidget(detail)
        layout.addLayout(text, 1)

        if favorite:
            for label, offset in (("↑", -1), ("↓", 1)):
                button = QPushButton(label)
                button.setObjectName("IconButton")
                button.setToolTip("Favoriyi yukarı taşı" if offset < 0 else "Favoriyi aşağı taşı")
                button.clicked.connect(
                    lambda _checked=False, key=action.key, step=offset: (
                        self.preferences.move_favorite(key, step)
                    )
                )
                layout.addWidget(button)
            remove = QPushButton("★")
            remove.setObjectName("FavoriteButton")
            remove.setProperty("selected", True)
            remove.setToolTip("Favorilerden kaldır")
            remove.clicked.connect(
                lambda _checked=False, key=action.key: (
                    self.preferences.remove_favorite(key)
                )
            )
            layout.addWidget(remove)

        run = QPushButton("Çalıştır")
        run.setObjectName("RunButton")
        run.setProperty("risk", action.risk)
        run.clicked.connect(
            lambda _checked=False, key=page_key, selected=action: (
                self.action_requested.emit(key, selected)
            )
        )
        layout.addWidget(run)
        return row

    def _preset_row(self, preset: TechnicianPreset) -> QFrame:
        row = QFrame()
        row.setObjectName("QuickAccessRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 12, 13, 12)
        layout.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel(preset.title)
        title.setObjectName("SectionTitle")
        description = QLabel(preset.description)
        description.setObjectName("CardSubtitle")
        description.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(description)
        layout.addLayout(text, 1)
        run = QPushButton("Akışı başlat")
        run.setObjectName("RunButton")
        run.setProperty("risk", preset.risk)
        run.setCursor(Qt.CursorShape.PointingHandCursor)
        run.clicked.connect(
            lambda _checked=False, selected=preset: self._run_preset(selected)
        )
        layout.addWidget(run)
        return row

    def _run_preset(self, preset: TechnicianPreset) -> None:
        plan = execution_plan_for_preset(preset)
        if not self._record_plan_event("prepared", plan) and (
            plan.admin_required or plan.impact.risk != "normal"
        ):
            self._report_audit_block(plan)
            return
        if not confirm_operation(self, plan.impact):
            self._record_plan_event("cancelled", plan)
            return
        approved = self._record_plan_event(
            "approved",
            plan,
            approval_mode=(
                "automatic"
                if plan.impact.confirmation_stages == 0
                else "user"
            ),
        )
        if not approved and (
            plan.admin_required or plan.impact.risk != "normal"
        ):
            self._report_audit_block(plan)
            return
        task = self.task_manager.start_command(
            plan.title,
            plan.command,
            category=plan.category,
            admin=plan.admin_required,
            keep_open=plan.keep_open,
            success_codes=plan.success_codes,
            plan_id=plan.plan_id,
            action_key=plan.action_key,
            risk=plan.impact.risk,
        )
        ok = task.status not in {"failed", "cancelled", "interrupted"}
        message = (
            task.message
            if task.status in {"failed", "delegated"}
            else "Görev Merkezi'ne eklendi."
        )
        self.status_message.emit(f"{preset.title}: {message}", ok)

    def _record_plan_event(
        self,
        event: str,
        plan: ExecutionPlan,
        *,
        approval_mode: str = "",
    ) -> bool:
        audit_log = getattr(self.task_manager, "audit_log", None)
        if not isinstance(audit_log, AuditLog):
            return False
        try:
            return audit_log.record_plan(
                event,
                plan,
                approval_mode=approval_mode,
            )
        except ValueError:
            return False

    def _report_audit_block(self, plan: ExecutionPlan) -> None:
        self.status_message.emit(
            f"{plan.title}: denetim günlüğüne yazılamadığı için hazır akış "
            "başlatılmadı. Yerel depolama izinlerini ve boş alanı kontrol edin.",
            False,
        )
