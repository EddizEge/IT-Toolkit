from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app_v2.services.task_manager import (
    ACTIVE_STATUSES,
    TaskManager,
    TaskRecord,
    status_text,
)


class SummaryCard(QFrame):
    def __init__(
        self,
        title: str,
        tone: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TaskSummaryCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        self.value = QLabel("0")
        self.value.setObjectName("TaskSummaryValue")
        self.value.setProperty("tone", tone)
        layout.addWidget(title_label)
        layout.addWidget(self.value)


class TaskCenterPage(QWidget):
    def __init__(
        self,
        manager: TaskManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self._selected_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 28)
        layout.setSpacing(15)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        title = QLabel("Görev Merkezi")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Çalışan işlemleri, canlı çıktıyı ve son görev sonuçlarını tek yerde izleyin"
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        clear_button = QPushButton("Tamamlananları Temizle")
        clear_button.setObjectName("GhostButton")
        clear_button.clicked.connect(self._clear_finished)
        header.addLayout(header_text, 1)
        header.addWidget(clear_button)
        layout.addLayout(header)

        summaries = QHBoxLayout()
        summaries.setSpacing(12)
        self.running_card = SummaryCard("ÇALIŞAN", "blue")
        self.success_card = SummaryCard("BAŞARILI", "green")
        self.failed_card = SummaryCard("SORUNLU", "red")
        summaries.addWidget(self.running_card)
        summaries.addWidget(self.success_card)
        summaries.addWidget(self.failed_card)
        summaries.addStretch(2)
        layout.addLayout(summaries)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_task_list())
        splitter.addWidget(self._build_details())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([390, 690])
        layout.addWidget(splitter, 1)

        privacy = QLabel(
            "Görev geçmişi yalnızca bu bilgisayarda tutulur ve en fazla 100 "
            "kayıt saklanır. Denetim izi komut, çıktı, URL veya gerçek hedef "
            "içermez."
        )
        privacy.setObjectName("Muted")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)

        self.manager.task_added.connect(self._on_task_added)
        self.manager.task_updated.connect(self._on_task_updated)
        self.manager.output_added.connect(self._on_output)
        self.manager.counts_changed.connect(self._update_counts)
        self.manager.history_cleared.connect(self._refresh_list)

        self._refresh_list()
        self._recount()

    def _build_task_list(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Görevler")
        title.setObjectName("SectionTitle")
        self.filter = QComboBox()
        self.filter.addItem("Tümü", "all")
        self.filter.addItem("Çalışanlar", "active")
        self.filter.addItem("Başarılı", "succeeded")
        self.filter.addItem("Sorunlu", "problem")
        self.filter.setFixedWidth(135)
        self.filter.currentIndexChanged.connect(self._refresh_list)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.filter)

        self.task_list = QListWidget()
        self.task_list.setObjectName("TaskList")
        self.task_list.setSpacing(3)
        self.task_list.currentItemChanged.connect(self._select_item)

        self.empty = QLabel("Henüz görev yok")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(title_row)
        layout.addWidget(self.task_list, 1)
        layout.addWidget(self.empty)
        return panel

    def _build_details(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        self.detail_title = QLabel("Bir görev seçin")
        self.detail_title.setObjectName("SectionTitle")
        self.status = QLabel("—")
        self.status.setObjectName("StatusBadge")
        self.status.setProperty("status", "unknown")
        title_row.addWidget(self.detail_title, 1)
        title_row.addWidget(self.status)

        self.meta = QLabel("Görev ayrıntıları burada görüntülenecek.")
        self.meta.setObjectName("CardSubtitle")
        self.meta.setWordWrap(True)
        self.meta.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.progress = QProgressBar()
        self.progress.setObjectName("TaskProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        output_title = QLabel("Canlı çıktı")
        output_title.setObjectName("SectionTitle")
        self.output = QPlainTextEdit()
        self.output.setObjectName("TaskOutput")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Görev çıktısı burada görünecek.")
        console_font = QFont("Cascadia Mono", 9)
        if not console_font.exactMatch():
            console_font = QFont("Consolas", 9)
        self.output.setFont(console_font)

        button_row = QHBoxLayout()
        self.cancel_button = QPushButton("Görevi İptal Et")
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.clicked.connect(self._cancel_selected)
        self.copy_button = QPushButton("Çıktıyı Kopyala")
        self.copy_button.setObjectName("GhostButton")
        self.copy_button.clicked.connect(self._copy_output)
        self.export_button = QPushButton("Raporu Dışa Aktar")
        self.export_button.setObjectName("GhostButton")
        self.export_button.clicked.connect(self._export_report)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch()
        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.export_button)

        layout.addLayout(title_row)
        layout.addWidget(self.meta)
        layout.addWidget(self.progress)
        layout.addWidget(output_title)
        layout.addWidget(self.output, 1)
        layout.addLayout(button_row)
        self._set_detail_buttons(False, False)
        return panel

    def show_task(self, task_id: str) -> None:
        self._selected_id = task_id
        self._refresh_list()
        for index in range(self.task_list.count()):
            item = self.task_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                self.task_list.setCurrentItem(item)
                break
        self._render_task(self.manager.task(task_id))

    def _refresh_list(self) -> None:
        selected = self._selected_id
        filter_key = str(self.filter.currentData()) if hasattr(self, "filter") else "all"
        self.task_list.blockSignals(True)
        self.task_list.clear()
        for task in self.manager.tasks:
            if not self._matches_filter(task, filter_key):
                continue
            item = QListWidgetItem(self._item_text(task))
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            item.setToolTip(task.message or task.title)
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                self._status_sort_key(task.status),
            )
            self.task_list.addItem(item)
            if task.id == selected:
                self.task_list.setCurrentItem(item)
        self.task_list.blockSignals(False)
        self.empty.setVisible(self.task_list.count() == 0)

        if self.task_list.currentItem():
            self._select_item(self.task_list.currentItem(), None)
        elif self.task_list.count() and not selected:
            self.task_list.setCurrentRow(0)
        elif not self.task_list.count():
            self._render_task(None)

    def _on_task_added(self, task: TaskRecord) -> None:
        self._selected_id = task.id
        self._refresh_list()
        self.show_task(task.id)

    def _on_task_updated(self, task: TaskRecord) -> None:
        if self._selected_id == task.id:
            self._render_task(task)
        filter_key = str(self.filter.currentData())
        matching = self._matches_filter(task, filter_key)
        item = self._find_item(task.id)
        if item and matching:
            item.setText(self._item_text(task))
            item.setToolTip(task.message or task.title)
        elif item or matching:
            self._refresh_list()

    def _on_output(self, task_id: str, _chunk: str) -> None:
        if task_id != self._selected_id:
            return
        task = self.manager.task(task_id)
        if task:
            self.output.setPlainText(task.output)
            self.output.verticalScrollBar().setValue(
                self.output.verticalScrollBar().maximum()
            )

    def _select_item(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if not current:
            return
        self._selected_id = str(current.data(Qt.ItemDataRole.UserRole))
        self._render_task(self.manager.task(self._selected_id))

    def _render_task(self, task: TaskRecord | None) -> None:
        if not task:
            self._selected_id = None
            self.detail_title.setText("Bir görev seçin")
            self.status.setText("—")
            self._set_status_property("unknown")
            self.meta.setText("Görev ayrıntıları burada görüntülenecek.")
            self.meta.setToolTip("")
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.output.clear()
            self._set_detail_buttons(False, False)
            return

        self.detail_title.setText(task.title)
        self.status.setText(status_text(task.status))
        self._set_status_property(self._status_property(task.status))
        short_plan_id = task.plan_id[:12] if task.plan_id else "—"
        self.meta.setText(
            f"{task.category}  •  Başlangıç: {task.started_at or task.created_at}"
            f"  •  Çıkış kodu: {task.exit_code if task.exit_code is not None else '—'}"
            f"\nDenetim kimliği: {short_plan_id}"
            f"\n{task.message or 'Görev sıraya alındı.'}"
        )
        self.meta.setToolTip(
            f"Tam denetim kimliği: {task.plan_id}"
            if task.plan_id
            else "Bu eski görev için denetim kimliği bulunmuyor."
        )
        if task.status in ACTIVE_STATUSES and task.progress is None:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(
                task.progress
                if task.progress is not None
                else 100
                if task.status in {"succeeded", "delegated"}
                else 0
            )
        self.output.setPlainText(task.output)
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum()
        )
        self._set_detail_buttons(
            task.status in ACTIVE_STATUSES and task.cancellable,
            True,
        )

    def _cancel_selected(self) -> None:
        if not self._selected_id:
            return
        task = self.manager.task(self._selected_id)
        if not task:
            return
        result = QMessageBox.question(
            self,
            "Görevi iptal et",
            f"“{task.title}” görevini iptal etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.manager.cancel(task.id)

    def _copy_output(self) -> None:
        if not self._selected_id:
            return
        task = self.manager.task(self._selected_id)
        if task:
            QApplication.clipboard().setText(task.output or task.message)

    def _export_report(self) -> None:
        if not self._selected_id:
            return
        task = self.manager.task(self._selected_id)
        if not task:
            return
        safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", task.title).strip("_")
        stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M")
        default_name = f"IT_Toolkit_{safe_title or 'Gorev'}_{stamp}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Görev raporunu kaydet",
            default_name,
            "Metin Raporu (*.txt)",
        )
        if not path:
            return
        if not path.lower().endswith(".txt"):
            path += ".txt"
        try:
            Path(path).write_text(
                self.manager.report_text(task.id),
                encoding="utf-8-sig",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Rapor kaydedilemedi", str(exc))
            return
        QMessageBox.information(
            self,
            "Rapor kaydedildi",
            "Görev raporu başarıyla dışa aktarıldı.",
        )

    def _clear_finished(self) -> None:
        if not any(
            task.status not in ACTIVE_STATUSES for task in self.manager.tasks
        ):
            return
        result = QMessageBox.question(
            self,
            "Görev geçmişini temizle",
            "Çalışmayan görev kayıtları ve çıktıları silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._selected_id = None
            self.manager.clear_finished()

    def _update_counts(
        self,
        running: int,
        succeeded: int,
        failed: int,
    ) -> None:
        self.running_card.value.setText(str(running))
        self.success_card.value.setText(str(succeeded))
        self.failed_card.value.setText(str(failed))

    def _recount(self) -> None:
        running = sum(
            task.status in ACTIVE_STATUSES for task in self.manager.tasks
        )
        succeeded = sum(
            task.status == "succeeded" for task in self.manager.tasks
        )
        failed = sum(
            task.status in {"failed", "interrupted"}
            for task in self.manager.tasks
        )
        self._update_counts(running, succeeded, failed)

    def _set_detail_buttons(self, cancellable: bool, available: bool) -> None:
        self.cancel_button.setEnabled(cancellable)
        self.copy_button.setEnabled(available)
        self.export_button.setEnabled(available)

    def _set_status_property(self, value: str) -> None:
        self.status.setProperty("status", value)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _find_item(self, task_id: str) -> QListWidgetItem | None:
        for index in range(self.task_list.count()):
            item = self.task_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                return item
        return None

    @staticmethod
    def _item_text(task: TaskRecord) -> str:
        time_text = task.started_at or task.created_at
        if "T" in time_text:
            time_text = time_text.split("T", 1)[1][:5]
        return f"{task.title}\n{status_text(task.status)}  •  {time_text}"

    @staticmethod
    def _matches_filter(task: TaskRecord, filter_key: str) -> bool:
        if filter_key == "active":
            return task.status in ACTIVE_STATUSES
        if filter_key == "succeeded":
            return task.status == "succeeded"
        if filter_key == "problem":
            return task.status in {"failed", "cancelled", "interrupted"}
        return True

    @staticmethod
    def _status_property(status: str) -> str:
        if status == "succeeded":
            return "on"
        if status in {"failed", "interrupted"}:
            return "off"
        return "unknown"

    @staticmethod
    def _status_sort_key(status: str) -> int:
        return 0 if status in ACTIVE_STATUSES else 1
