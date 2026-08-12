from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.services.health_service import (
    HealthFinding,
    HealthReport,
    collect_health_report,
    report_text,
)
from app_v2.services.system_monitor import FunctionWorker
from app_v2.services.task_manager import TaskManager
from app_v2.widgets import clear_layout


class HealthPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(
        self,
        task_manager: TaskManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.task_manager = task_manager
        self._pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self._report: HealthReport | None = None
        self._scanning = False

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
        layout.setSpacing(17)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(4)
        title = QLabel("Akıllı Tanılama")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Disk, bellek, pil ve Windows bakım durumunu salt okunur kontrollerle değerlendirin."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)

        self.copy_button = QPushButton("Raporu kopyala")
        self.copy_button.setObjectName("GhostButton")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_report)
        self.scan_button = QPushButton("Tanılamayı başlat")
        self.scan_button.setObjectName("PrimaryButton")
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self.start_scan)
        header.addWidget(self.copy_button)
        header.addWidget(self.scan_button)
        layout.addLayout(header)

        self.summary_panel = QFrame()
        self.summary_panel.setObjectName("HealthSummary")
        self.summary_panel.setProperty("tone", "info")
        summary_layout = QHBoxLayout(self.summary_panel)
        summary_layout.setContentsMargins(22, 19, 22, 19)
        summary_layout.setSpacing(24)

        score_column = QVBoxLayout()
        score_column.setSpacing(5)
        score_title = QLabel("SAĞLIK PUANI")
        score_title.setObjectName("Muted")
        self.score_label = QLabel("—")
        self.score_label.setObjectName("HealthScore")
        self.score_label.setProperty("tone", "info")
        self.score_progress = QProgressBar()
        self.score_progress.setObjectName("HealthProgress")
        self.score_progress.setRange(0, 100)
        self.score_progress.setValue(0)
        self.score_progress.setTextVisible(False)
        self.score_progress.setFixedWidth(210)
        self.score_label_text = QLabel("Henüz değerlendirilmedi")
        self.score_label_text.setObjectName("CardSubtitle")
        score_column.addWidget(score_title)
        score_column.addWidget(self.score_label)
        score_column.addWidget(self.score_progress)
        score_column.addWidget(self.score_label_text)
        summary_layout.addLayout(score_column)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("HealthDivider")
        summary_layout.addWidget(divider)

        summary_column = QVBoxLayout()
        summary_column.setSpacing(7)
        self.summary_title = QLabel("Tanılama bekleniyor")
        self.summary_title.setObjectName("SectionTitle")
        self.summary_text = QLabel(
            "Kontrol başladığında her sonucun kanıtı ve güvenli önerisi burada açıklanır."
        )
        self.summary_text.setObjectName("CardSubtitle")
        self.summary_text.setWordWrap(True)
        self.counts_label = QLabel("Kritik —  •  Uyarı —  •  İyi —")
        self.counts_label.setObjectName("HealthCounts")
        self.last_scan_label = QLabel("Son kontrol: —")
        self.last_scan_label.setObjectName("Muted")
        summary_column.addWidget(self.summary_title)
        summary_column.addWidget(self.summary_text)
        summary_column.addWidget(self.counts_label)
        summary_column.addStretch()
        summary_column.addWidget(self.last_scan_label)
        summary_layout.addLayout(summary_column, 1)
        layout.addWidget(self.summary_panel)

        method_panel = QFrame()
        method_panel.setObjectName("HealthMethod")
        method_layout = QHBoxLayout(method_panel)
        method_layout.setContentsMargins(16, 12, 16, 12)
        method_title = QLabel("Puan nasıl hesaplanır?")
        method_title.setObjectName("SectionTitle")
        method_text = QLabel(
            "100 puandan başlanır. Yalnızca eşikleri aşan uyarı ve kritik bulgular "
            "puan düşürür; bilgi amaçlı veya iyi sonuçlar puanı etkilemez."
        )
        method_text.setObjectName("CardSubtitle")
        method_text.setWordWrap(True)
        method_layout.addWidget(method_title)
        method_layout.addWidget(method_text, 1)
        layout.addWidget(method_panel)

        findings_header = QHBoxLayout()
        findings_title = QLabel("Tanılama bulguları")
        findings_title.setObjectName("SectionTitle")
        self.scan_state = QLabel("Başlatılmadı")
        self.scan_state.setObjectName("StatusBadge")
        self.scan_state.setProperty("status", "unknown")
        findings_header.addWidget(findings_title)
        findings_header.addStretch()
        findings_header.addWidget(self.scan_state)
        layout.addLayout(findings_header)

        self.findings_layout = QVBoxLayout()
        self.findings_layout.setSpacing(10)
        layout.addLayout(self.findings_layout)
        self._show_empty(
            "Tanılama başlatıldığında disk, bellek, Windows Update, yeniden başlatma ve pil sonuçları burada listelenecek."
        )
        layout.addStretch()

        QTimer.singleShot(0, self.start_scan)

    def start_scan(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.scan_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.scan_button.setText("Kontrol ediliyor…")
        self.scan_state.setText("Çalışıyor")
        self.scan_state.setProperty("status", "unknown")
        self._refresh_property(self.scan_state)
        self._show_empty(
            "Salt okunur Windows ve donanım verileri toplanıyor. Bu işlem sistem ayarlarını değiştirmez."
        )

        worker = FunctionWorker(collect_health_report)
        self._workers.add(worker)

        def completed(report: HealthReport) -> None:
            self._workers.discard(worker)
            self._finish_scan(report)

        def failed(message: str) -> None:
            self._workers.discard(worker)
            self._fail_scan(message)

        worker.signals.completed.connect(completed)
        worker.signals.failed.connect(failed)
        self._pool.start(worker)

    def _finish_scan(self, report: HealthReport) -> None:
        self._scanning = False
        self._report = report
        self.scan_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        self.scan_button.setText("Tekrar tara")
        tone = self._score_tone(report.score)
        self.summary_panel.setProperty("tone", tone)
        self.score_label.setProperty("tone", tone)
        self.score_progress.setProperty("tone", tone)
        for widget in (self.summary_panel, self.score_label, self.score_progress):
            self._refresh_property(widget)
        self.score_label.setText(f"{report.score}/100")
        self.score_progress.setValue(report.score)
        self.score_label_text.setText(report.label)
        self.summary_title.setText("Tanılama tamamlandı")
        self.summary_text.setText(report.summary)
        self.counts_label.setText(
            f"Kritik {report.critical_count}  •  Uyarı {report.warning_count}  •  "
            f"İyi {report.good_count}"
        )
        try:
            display_time = datetime.fromisoformat(report.generated_at).strftime(
                "%d.%m.%Y %H:%M"
            )
        except ValueError:
            display_time = report.generated_at.replace("T", " ")
        self.last_scan_label.setText(f"Son kontrol: {display_time}")
        self.scan_state.setText("Tamamlandı")
        self.scan_state.setProperty("status", "on")
        self._refresh_property(self.scan_state)

        clear_layout(self.findings_layout)
        for finding in report.findings:
            self.findings_layout.addWidget(self._finding_card(finding))

        self.task_manager.record_result(
            "Akıllı sistem tanılaması",
            f"Sağlık puanı {report.score}/100 — {report.label}",
            success=True,
            category="Akıllı Tanılama",
            output=report_text(report),
        )
        self.status_message.emit(
            f"Akıllı tanılama tamamlandı: {report.score}/100 ({report.label})",
            True,
        )

    def _fail_scan(self, message: str) -> None:
        self._scanning = False
        self.scan_button.setEnabled(True)
        self.scan_button.setText("Yeniden dene")
        self.scan_state.setText("Başarısız")
        self.scan_state.setProperty("status", "off")
        self._refresh_property(self.scan_state)
        self._show_empty(f"Tanılama tamamlanamadı: {message}")
        self.task_manager.record_result(
            "Akıllı sistem tanılaması",
            message,
            success=False,
            category="Akıllı Tanılama",
        )
        self.status_message.emit(f"Akıllı tanılama: {message}", False)

    def _finding_card(self, finding: HealthFinding) -> QFrame:
        card = QFrame()
        card.setObjectName("HealthFinding")
        card.setProperty("severity", finding.severity)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        marker = QLabel(
            {
                "critical": "!",
                "warning": "!",
                "info": "i",
                "good": "✓",
            }[finding.severity]
        )
        marker.setObjectName("HealthMarker")
        marker.setProperty("severity", finding.severity)
        marker.setFixedSize(34, 34)
        marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(4)
        title_row = QHBoxLayout()
        title = QLabel(finding.title)
        title.setObjectName("SectionTitle")
        category = QLabel(finding.category.upper())
        category.setObjectName("Badge")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(category)
        summary = QLabel(finding.summary)
        summary.setWordWrap(True)
        evidence = QLabel(f"Kanıt: {finding.evidence}")
        evidence.setObjectName("CardSubtitle")
        evidence.setWordWrap(True)
        recommendation = QLabel(f"Öneri: {finding.recommendation}")
        recommendation.setObjectName("HealthRecommendation")
        recommendation.setWordWrap(True)
        text.addLayout(title_row)
        text.addWidget(summary)
        text.addWidget(evidence)
        text.addWidget(recommendation)
        layout.addLayout(text, 1)

        if finding.deduction:
            impact = QLabel(f"−{finding.deduction}")
            impact.setObjectName("HealthImpact")
            impact.setProperty("severity", finding.severity)
            impact.setToolTip("Sağlık puanına etkisi")
            layout.addWidget(impact, 0, Qt.AlignmentFlag.AlignTop)
        return card

    def _show_empty(self, text: str) -> None:
        clear_layout(self.findings_layout)
        label = QLabel(text)
        label.setObjectName("EmptyState")
        label.setWordWrap(True)
        self.findings_layout.addWidget(label)

    def _copy_report(self) -> None:
        if not self._report:
            return
        QApplication.clipboard().setText(report_text(self._report))
        self.status_message.emit("Tanılama raporu panoya kopyalandı.", True)

    @staticmethod
    def _score_tone(score: int) -> str:
        if score >= 90:
            return "good"
        if score >= 75:
            return "info"
        if score >= 60:
            return "warning"
        return "critical"

    @staticmethod
    def _refresh_property(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
