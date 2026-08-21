from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.services.error_logging import (
    default_log_directory,
    shared_diagnostics,
)
from app_v2.services.feedback_service import (
    FeedbackDraft,
    feedback_report_text,
    github_issue_url,
)


class FeedbackPage(QWidget):
    status_message = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 26, 30, 34)
        layout.setSpacing(17)

        title = QLabel("Geri Bildirim ve Hata Günlüğü")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Karşılaştığınız hatayı veya önerinizi güvenli bir rapora dönüştürüp "
            "IT Toolkit GitHub sayfasından doğrudan iletin."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        privacy_panel = QFrame()
        privacy_panel.setObjectName("HealthMethod")
        privacy_layout = QVBoxLayout(privacy_panel)
        privacy_layout.setContentsMargins(18, 14, 18, 14)
        privacy_layout.setSpacing(5)
        privacy_title = QLabel("Gizlilik koruması etkin")
        privacy_title.setObjectName("SectionTitle")
        privacy_text = QLabel(
            "Paylaşılan günlükte kullanıcı yolu, e-posta, IP, MAC adresi, ürün "
            "anahtarı ve yaygın gizli anahtar alanları otomatik maskelenir. "
            "Yine de göndermeden önce önizlemeyi kontrol edin."
        )
        privacy_text.setObjectName("CardSubtitle")
        privacy_text.setWordWrap(True)
        privacy_layout.addWidget(privacy_title)
        privacy_layout.addWidget(privacy_text)
        layout.addWidget(privacy_panel)

        form_panel = QFrame()
        form_panel.setObjectName("Panel")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(20, 18, 20, 20)
        form_layout.setSpacing(11)

        form_title = QLabel("Geri bildirim ayrıntıları")
        form_title.setObjectName("SectionTitle")
        form_layout.addWidget(form_title)

        category_label = QLabel("Kategori")
        category_label.setObjectName("Muted")
        self.category = QComboBox()
        self.category.addItems(
            (
                "Uygulama hatası",
                "Arayüz ve kullanılabilirlik",
                "Araç veya komut sonucu",
                "Özellik önerisi",
                "Genel geri bildirim",
            )
        )
        form_layout.addWidget(category_label)
        form_layout.addWidget(self.category)

        title_label = QLabel("Kısa başlık")
        title_label.setObjectName("Muted")
        self.title_input = QLineEdit()
        self.title_input.setObjectName("DialogInput")
        self.title_input.setPlaceholderText(
            "Örn. Ağ onarımı tamamlandıktan sonra sonuç görünmüyor"
        )
        self.title_input.setMaxLength(100)
        form_layout.addWidget(title_label)
        form_layout.addWidget(self.title_input)

        details_label = QLabel("Ne oldu, ne olmasını bekliyordunuz?")
        details_label.setObjectName("Muted")
        self.details_input = QPlainTextEdit()
        self.details_input.setObjectName("FeedbackText")
        self.details_input.setPlaceholderText(
            "Sorunu veya öneriyi mümkün olduğunca açık anlatın."
        )
        self.details_input.setMinimumHeight(120)
        form_layout.addWidget(details_label)
        form_layout.addWidget(self.details_input)

        steps_label = QLabel("Yeniden üretme adımları (isteğe bağlı)")
        steps_label.setObjectName("Muted")
        self.steps_input = QPlainTextEdit()
        self.steps_input.setObjectName("FeedbackText")
        self.steps_input.setPlaceholderText(
            "1. Açtığınız sayfa\n2. Bastığınız düğme\n3. Gördüğünüz sonuç"
        )
        self.steps_input.setMinimumHeight(95)
        form_layout.addWidget(steps_label)
        form_layout.addWidget(self.steps_input)
        layout.addWidget(form_panel)

        diagnostic_panel = QFrame()
        diagnostic_panel.setObjectName("Panel")
        diagnostic_layout = QVBoxLayout(diagnostic_panel)
        diagnostic_layout.setContentsMargins(20, 18, 20, 20)
        diagnostic_layout.setSpacing(10)

        diagnostic_header = QHBoxLayout()
        diagnostic_title = QLabel("Maskelenmiş tanılama önizlemesi")
        diagnostic_title.setObjectName("SectionTitle")
        refresh_button = QPushButton("Günlüğü yenile")
        refresh_button.setObjectName("GhostButton")
        refresh_button.clicked.connect(self._refresh_diagnostics)
        folder_button = QPushButton("Günlük klasörünü aç")
        folder_button.setObjectName("GhostButton")
        folder_button.clicked.connect(self._open_log_directory)
        diagnostic_header.addWidget(diagnostic_title)
        diagnostic_header.addStretch()
        diagnostic_header.addWidget(refresh_button)
        diagnostic_header.addWidget(folder_button)
        diagnostic_layout.addLayout(diagnostic_header)

        self.include_diagnostics = QCheckBox(
            "Sürüm, Windows bilgisi ve maskelenmiş son uygulama günlüğünü ekle"
        )
        self.include_diagnostics.setChecked(True)
        diagnostic_layout.addWidget(self.include_diagnostics)

        self.diagnostics_preview = QPlainTextEdit()
        self.diagnostics_preview.setObjectName("FeedbackText")
        self.diagnostics_preview.setReadOnly(True)
        self.diagnostics_preview.setMinimumHeight(175)
        diagnostic_layout.addWidget(self.diagnostics_preview)
        layout.addWidget(diagnostic_panel)

        privacy_confirmation = QLabel(
            "Göndermeden önce yukarıdaki önizlemeyi kontrol edin. Parola, müşteri "
            "verisi veya başka hassas bir bilgi görürseniz rapordan çıkarın."
        )
        privacy_confirmation.setObjectName("CardSubtitle")
        privacy_confirmation.setWordWrap(True)
        layout.addWidget(privacy_confirmation)
        self.privacy_check = QCheckBox(
            "Önizlemeyi kontrol ettim ve hassas bilgi bulunmadığını onaylıyorum."
        )
        layout.addWidget(self.privacy_check)

        actions = QHBoxLayout()
        copy_button = QPushButton("Raporu panoya kopyala")
        copy_button.setObjectName("GhostButton")
        copy_button.clicked.connect(self._copy_report)
        send_button = QPushButton("GitHub’da gönder")
        send_button.setObjectName("PrimaryButton")
        send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        send_button.clicked.connect(self._send_to_github)
        actions.addStretch()
        actions.addWidget(copy_button)
        actions.addWidget(send_button)
        layout.addLayout(actions)
        layout.addStretch()

        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        self.diagnostics_preview.setPlainText(shared_diagnostics())
        self.status_message.emit("Maskelenmiş hata günlüğü yenilendi.", True)

    def _draft(self) -> FeedbackDraft:
        diagnostics = (
            self.diagnostics_preview.toPlainText()
            if self.include_diagnostics.isChecked()
            else ""
        )
        return FeedbackDraft(
            category=self.category.currentText(),
            title=self.title_input.text(),
            details=self.details_input.toPlainText(),
            steps=self.steps_input.toPlainText(),
            diagnostics=diagnostics,
        )

    def _validate(self, *, require_privacy_check: bool) -> bool:
        if not self.title_input.text().strip():
            QMessageBox.information(
                self,
                "Başlık gerekli",
                "Geri bildiriminiz için kısa bir başlık yazın.",
            )
            self.title_input.setFocus()
            return False
        if not self.details_input.toPlainText().strip():
            QMessageBox.information(
                self,
                "Açıklama gerekli",
                "Ne olduğunu veya önerinizi açıklayın.",
            )
            self.details_input.setFocus()
            return False
        if require_privacy_check and not self.privacy_check.isChecked():
            QMessageBox.information(
                self,
                "Gizlilik kontrolü gerekli",
                "Göndermeden önce önizlemeyi kontrol ettiğinizi onaylayın.",
            )
            self.privacy_check.setFocus()
            return False
        return True

    def _copy_report(self) -> None:
        if not self._validate(require_privacy_check=False):
            return
        QApplication.clipboard().setText(feedback_report_text(self._draft()))
        self.status_message.emit("Geri bildirim raporu panoya kopyalandı.", True)

    def _send_to_github(self) -> None:
        if not self._validate(require_privacy_check=True):
            return
        draft = self._draft()
        QApplication.clipboard().setText(feedback_report_text(draft))
        opened = QDesktopServices.openUrl(QUrl(github_issue_url(draft)))
        if not opened:
            self.status_message.emit(
                "GitHub sayfası açılamadı; rapor panoya kopyalandı.",
                False,
            )
            return
        QMessageBox.information(
            self,
            "GitHub sayfası açıldı",
            "Form alanları hazırlandı ve tam rapor panoya kopyalandı. "
            "GitHub hesabınızla giriş yapıp önizlemeyi kontrol ettikten sonra "
            "“Submit new issue” düğmesine basın.",
        )
        self.status_message.emit(
            "Geri bildirim GitHub’da gönderilmeye hazır.",
            True,
        )

    def _open_log_directory(self) -> None:
        directory = default_log_directory()
        directory.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            self.status_message.emit("Günlük klasörü açılamadı.", False)
