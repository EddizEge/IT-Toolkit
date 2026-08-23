from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.action_confirmation import (
    confirm_operation,
    confirm_without_restore_point,
)
from app_v2.registry import ToggleAction, ToolAction
from app_v2.services.action_safety import (
    ExecutionPlan,
    execution_plan_for_action,
    execution_plan_for_toggle,
    impact_for_action,
)
from app_v2.services.audit_log import AuditLog
from app_v2.services.preferences import ToolPreferences
from app_v2.services.settings_service import get_toggle_status
from app_v2.services.task_manager import TaskManager
from app_v2.services.undo_execution import PROTECTED_ACTION_KEYS
from app_v2.widgets import ActionTile, ToggleRow


class ToolsPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(
        self,
        title: str,
        subtitle: str,
        actions: tuple[ToolAction, ...],
        toggles: tuple[ToggleAction, ...] = (),
        custom_handlers: dict[
            str,
            Callable[[ToolAction], ExecutionPlan | None],
        ]
        | None = None,
        ui_handlers: dict[str, Callable[[ToolAction], bool]] | None = None,
        parent: QWidget | None = None,
        task_manager: TaskManager | None = None,
        preferences: ToolPreferences | None = None,
    ) -> None:
        super().__init__(parent)
        self.actions = actions
        self.page_title = title
        self.task_manager = task_manager or TaskManager(self)
        self.preferences = preferences
        self._plan_handlers = custom_handlers or {}
        self._ui_handlers = ui_handlers or {}
        self._tiles: list[ActionTile] = []
        self._sections: list[tuple[QWidget, list[ActionTile]]] = []
        self._toggle_rows: dict[str, ToggleRow] = {}
        self._toggle_section: QWidget | None = None
        self._pending_restore_plans: dict[
            str,
            tuple[ExecutionPlan, bool, QWidget],
        ] = {}
        self._scheduled_restore_finishes: set[str] = set()
        self._shutting_down = False
        self.task_manager.task_updated.connect(
            self._on_restore_task_updated
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 34)
        layout.setSpacing(18)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        grouped: dict[str, list[ToolAction]] = defaultdict(list)
        for action in actions:
            grouped[action.category].append(action)

        for category, category_actions in grouped.items():
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(10)

            section_title = QLabel(category)
            section_title.setObjectName("SectionTitle")
            section_layout.addWidget(section_title)

            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            section_tiles: list[ActionTile] = []
            for index, action in enumerate(category_actions):
                tile = ActionTile(action, self.preferences)
                tile.run_requested.connect(self.execute_action)
                self._tiles.append(tile)
                section_tiles.append(tile)
                grid.addWidget(tile, index // 2, index % 2)
            section_layout.addLayout(grid)
            layout.addWidget(section)
            self._sections.append((section, section_tiles))

        if toggles:
            toggle_section = QWidget()
            toggle_layout = QVBoxLayout(toggle_section)
            toggle_layout.setContentsMargins(0, 0, 0, 0)
            toggle_layout.setSpacing(10)
            toggle_title = QLabel("Temel ayarlar")
            toggle_title.setObjectName("SectionTitle")
            toggle_layout.addWidget(toggle_title)
            for toggle in toggles:
                row = ToggleRow(toggle)
                row.change_requested.connect(self._change_toggle)
                self._toggle_rows[toggle.key] = row
                toggle_layout.addWidget(row)
            layout.addWidget(toggle_section)
            self._toggle_section = toggle_section
            self.refresh_toggle_statuses()

        layout.addStretch()

    def filter_actions(self, query: str) -> None:
        normalized = query.casefold().strip()
        for section, tiles in self._sections:
            any_match = False
            for tile in tiles:
                haystack = (
                    f"{tile.action.title} {tile.action.description} {tile.action.category}"
                ).casefold()
                match = not normalized or normalized in haystack
                tile.setVisible(match)
                any_match = any_match or match
            section.setVisible(any_match)

        if self._toggle_section:
            toggle_match = not normalized
            for row in self._toggle_rows.values():
                haystack = f"{row.toggle.title} {row.toggle.description}".casefold()
                match = not normalized or normalized in haystack
                row.setVisible(match)
                toggle_match = toggle_match or match
            self._toggle_section.setVisible(toggle_match)

    def execute_action(self, action: ToolAction) -> None:
        if action.handler:
            ui_handler = self._ui_handlers.get(action.handler)
            if ui_handler:
                if action.admin or action.risk != "normal":
                    self.status_message.emit(
                        f"{action.title}: güvenlik gerektiren arayüz işlemi "
                        "işlem planı olmadan başlatılamaz.",
                        False,
                    )
                    return
                if not confirm_operation(self, impact_for_action(action)):
                    return
                if ui_handler(action):
                    self.record_recent(action.key)
                return
            handler = self._plan_handlers.get(action.handler)
            if action.handler == "restore_point":
                self._execute_plan(
                    execution_plan_for_action(
                        action,
                        command="registered:restore_point",
                    )
                )
                return
            if not handler:
                self.status_message.emit(
                    f"{action.title}: özel işlem tanımlı değil.",
                    False,
                )
                return
            plan = handler(action)
            if plan is not None:
                self._execute_plan(plan)
            return
        self._execute_plan(execution_plan_for_action(action))

    def _execute_plan(
        self,
        plan: ExecutionPlan,
        *,
        record_recent: bool = True,
        dialog_parent: QWidget | None = None,
    ) -> bool:
        if self._shutting_down:
            return False
        parent = dialog_parent or self
        prepared = self._record_plan_event("prepared", plan)
        if not prepared and self._requires_audit(plan):
            self._report_audit_block(plan)
            return False
        confirmation = confirm_operation(parent, plan.impact)
        if not confirmation:
            self._record_plan_event("cancelled", plan)
            return False
        approved = self._record_plan_event(
            "approved",
            plan,
            approval_mode=(
                "automatic"
                if plan.impact.confirmation_stages == 0
                else "user"
            ),
        )
        if not approved and self._requires_audit(plan):
            self._report_audit_block(plan)
            return False
        if plan.action_key == "restore":
            return self._start_approved_plan(
                plan,
                record_recent=record_recent,
                restore_point_status="not_applicable",
            )
        create_restore_point = bool(
            getattr(confirmation, "create_restore_point", False)
        )
        if create_restore_point:
            try:
                task = self.task_manager.start_restore_point(
                    plan.title,
                    parent_plan_id=plan.plan_id,
                    parent_action_key=plan.action_key,
                    risk=plan.impact.risk,
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                self._record_plan_event("cancelled", plan)
                self.status_message.emit(
                    f"{plan.title}: koruma görevi başlatılamadı ({exc}).",
                    False,
                )
                return False
            self._pending_restore_plans[task.id] = (
                plan,
                record_recent,
                parent,
            )
            self.status_message.emit(
                f"{plan.title}: işlemden önce geri yükleme noktası "
                "hazırlanıyor.",
                True,
            )
            if task.status not in {"queued", "running"}:
                QTimer.singleShot(
                    0,
                    lambda current=task: self._on_restore_task_updated(current),
                )
            return True
        restore_point_status = (
            "skipped"
            if plan.impact.recovery.restore_point_mode == "optional"
            else "not_applicable"
        )
        return self._start_approved_plan(
            plan,
            record_recent=record_recent,
            restore_point_status=restore_point_status,
        )

    def execute_plan(
        self,
        plan: ExecutionPlan,
        *,
        record_recent: bool = False,
        dialog_parent: QWidget | None = None,
    ) -> bool:
        """Merkezi kapıdan önceden çözümlenmiş bir plan yürüt."""

        return self._execute_plan(
            plan,
            record_recent=record_recent,
            dialog_parent=dialog_parent,
        )

    def _start_approved_plan(
        self,
        plan: ExecutionPlan,
        *,
        record_recent: bool,
        restore_point_status: str,
    ) -> bool:
        if self._shutting_down:
            self._record_plan_event("cancelled", plan)
            return False
        if plan.action_key == "restore":
            try:
                task = self.task_manager.start_manual_restore(
                    plan.title,
                    plan_id=plan.plan_id,
                    action_key=plan.action_key,
                    risk=plan.impact.risk,
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                self._record_plan_event("cancelled", plan)
                self.status_message.emit(
                    f"{plan.title}: görev başlatılamadı ({exc}).",
                    False,
                )
                return False
            if record_recent:
                self.record_recent(plan.action_key)
            ok = task.status not in {"failed", "cancelled", "interrupted"}
            message = (
                task.message
                if task.status in {"failed", "delegated"}
                else "Doğrulama görevi Görev Merkezi'ne eklendi."
            )
            self.status_message.emit(f"{plan.title}: {message}", ok)
            return ok

        if plan.parent_plan_id:
            try:
                task = self.task_manager.start_undo(plan)
            except (RuntimeError, TypeError, ValueError) as exc:
                self._record_plan_event("cancelled", plan)
                self.status_message.emit(
                    f"{plan.title}: geri alma başlatılamadı ({exc}).",
                    False,
                )
                return False
            ok = task.status not in {
                "failed",
                "cancelled",
                "interrupted",
            }
            message = (
                task.message
                if task.status in {"failed", "delegated"}
                else "Geri alma görevi Görev Merkezi'ne eklendi."
            )
            self.status_message.emit(f"{plan.title}: {message}", ok)
            return ok

        if plan.action_key in PROTECTED_ACTION_KEYS:
            try:
                task = self.task_manager.start_protected_action(
                    plan,
                    restore_point_status=restore_point_status,
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                self._record_plan_event("cancelled", plan)
                self.status_message.emit(
                    f"{plan.title}: güvenli görev başlatılamadı ({exc}).",
                    False,
                )
                return False
            if record_recent:
                self.record_recent(plan.action_key)
            ok = task.status not in {
                "failed",
                "cancelled",
                "interrupted",
            }
            message = (
                task.message
                if task.status in {"failed", "delegated"}
                else "Güvenli görev Görev Merkezi'ne eklendi."
            )
            self.status_message.emit(f"{plan.title}: {message}", ok)
            return ok

        opened_urls = sum(
            bool(QDesktopServices.openUrl(QUrl(url))) for url in plan.urls
        )
        task = None
        if plan.command.strip():
            try:
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
                    parent_plan_id=plan.parent_plan_id,
                    undo_key=plan.impact.recovery.undo_key,
                    restore_point_status=restore_point_status,
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                self._record_plan_event("cancelled", plan)
                self.status_message.emit(
                    f"{plan.title}: görev başlatılamadı ({exc}).",
                    False,
                )
                return False
        if record_recent:
            self.record_recent(plan.action_key)
        if task is None:
            ok = opened_urls == len(plan.urls)
            message = (
                f"{opened_urls} resmi bağlantı tarayıcıda açıldı."
                if ok
                else (
                    f"{opened_urls}/{len(plan.urls)} bağlantı açıldı. "
                    "Kalan bağlantıları daha sonra yeniden deneyin."
                )
            )
            try:
                self.task_manager.record_result(
                    plan.title,
                    message,
                    success=ok,
                    category=plan.category,
                    plan_id=plan.plan_id,
                    action_key=plan.action_key,
                    risk=plan.impact.risk,
                    admin=plan.admin_required,
                    parent_plan_id=plan.parent_plan_id,
                    undo_key=plan.impact.recovery.undo_key,
                    restore_point_status=restore_point_status,
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                self.status_message.emit(
                    f"{plan.title}: sonuç kaydedilemedi ({exc}).",
                    False,
                )
                return False
            self.status_message.emit(f"{plan.title}: {message}", ok)
            return True
        ok = task.status not in {"failed", "cancelled", "interrupted"}
        message = (
            task.message
            if task.status in {"failed", "delegated"}
            else "Görev Merkezi'ne eklendi."
        )
        self.status_message.emit(f"{plan.title}: {message}", ok)
        return True

    def _on_restore_task_updated(self, task: object) -> None:
        if self._shutting_down:
            return
        task_id = str(getattr(task, "id", ""))
        pending = self._pending_restore_plans.get(task_id)
        status = str(getattr(task, "status", ""))
        if (
            pending is None
            or status in {"queued", "running"}
            or task_id in self._scheduled_restore_finishes
        ):
            return
        self._scheduled_restore_finishes.add(task_id)
        QTimer.singleShot(
            0,
            lambda current=task, current_id=task_id: self._finish_restore_preflight(
                current_id,
                current,
            ),
        )

    def _finish_restore_preflight(
        self,
        task_id: str,
        task: object,
    ) -> None:
        self._scheduled_restore_finishes.discard(task_id)
        if self._shutting_down:
            return
        pending = self._pending_restore_plans.pop(task_id, None)
        if pending is None:
            return
        plan, record_recent, parent = pending
        status = str(getattr(task, "status", ""))
        if status == "succeeded":
            self._start_approved_plan(
                plan,
                record_recent=record_recent,
                restore_point_status="created",
            )
            return
        reason = str(getattr(task, "message", "")).strip() or (
            "Geri yükleme noktası doğrulanamadı."
        )
        if not confirm_without_restore_point(parent, plan.title, reason):
            self._record_plan_event("cancelled", plan)
            self.status_message.emit(
                f"{plan.title}: ana işlem başlatılmadı.",
                False,
            )
            return
        recorded = self._record_plan_event(
            "recovery_override",
            plan,
            approval_mode="user",
        )
        if not recorded and self._requires_audit(plan):
            self._report_audit_block(plan)
            return
        self._start_approved_plan(
            plan,
            record_recent=record_recent,
            restore_point_status="failed_override",
        )

    def cancel_pending_recovery(self) -> None:
        """Kapanışta bekleyen ana işlemleri kesin olarak iptal et."""

        if self._shutting_down:
            return
        self._shutting_down = True
        pending = tuple(self._pending_restore_plans.values())
        self._pending_restore_plans.clear()
        self._scheduled_restore_finishes.clear()
        for plan, _record_recent, _parent in pending:
            self._record_plan_event("cancelled", plan)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.cancel_pending_recovery()
        super().closeEvent(event)

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
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _requires_audit(plan: ExecutionPlan) -> bool:
        return plan.admin_required or plan.impact.risk != "normal"

    def _report_audit_block(self, plan: ExecutionPlan) -> None:
        self.status_message.emit(
            f"{plan.title}: denetim günlüğüne yazılamadığı için işlem "
            "başlatılmadı. Yerel depolama izinlerini ve boş alanı kontrol edin.",
            False,
        )

    def record_recent(self, action_key: str) -> None:
        if self.preferences:
            self.preferences.record_recent(action_key)

    def report(self, title: str, ok: bool, message: str) -> None:
        self.task_manager.record_result(
            title,
            message,
            success=ok,
            category=self.page_title,
        )
        self.status_message.emit(f"{title}: {message}", ok)

    def _change_toggle(self, toggle: ToggleAction, enabled: bool) -> None:
        previous_enabled, status_text = get_toggle_status(toggle.key)
        if previous_enabled is not None and previous_enabled == enabled:
            self._toggle_rows[toggle.key].set_status(
                previous_enabled,
                status_text,
            )
            self.status_message.emit(
                f"{toggle.title}: ayar zaten istenen durumda.",
                True,
            )
            return
        plan = execution_plan_for_toggle(
            toggle,
            enabled,
            previous_enabled=previous_enabled,
        )
        if self._execute_plan(plan, record_recent=False):
            QTimer.singleShot(3_000, self.refresh_toggle_statuses)

    def refresh_toggle_statuses(self) -> None:
        for key, row in self._toggle_rows.items():
            enabled, text = get_toggle_status(key)
            row.set_status(enabled, text)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._toggle_rows:
            self.refresh_toggle_statuses()
