from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_v2.services.action_safety import OperationImpact


@dataclass(frozen=True, slots=True)
class OperationConfirmation:
    approved: bool
    create_restore_point: bool = False

    def __bool__(self) -> bool:
        return self.approved


def _detail_block(title: str, text: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("SafetyDetail")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 11, 14, 11)
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setObjectName("Muted")
    value = QLabel(text)
    value.setObjectName("SafetyDetailText")
    value.setWordWrap(True)
    value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(heading)
    layout.addWidget(value)
    return frame


class ImpactReviewDialog(QDialog):
    def __init__(
        self,
        impact: OperationImpact,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.impact = impact
        self.setObjectName("SafetyDialog")
        self.setWindowTitle("İşlem güvenliği")
        self.resize(650, 620)
        self.setMinimumSize(580, 560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 23, 26, 23)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("İşlem etkisini inceleyin")
        title.setObjectName("PageTitle")
        header.addWidget(title, 1)
        risk = QLabel(impact.risk_label)
        risk.setObjectName("SafetyRiskBadge")
        risk.setProperty("risk", impact.risk)
        risk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(risk)
        layout.addLayout(header)

        stage_text = "1 / 2" if impact.confirmation_stages == 2 else "1 / 1"
        subtitle = QLabel(
            f"Onay aşaması {stage_text} • Devam etmeden önce bütün alanları okuyun."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        action_title = QLabel(impact.title)
        action_title.setObjectName("SectionTitle")
        action_title.setWordWrap(True)
        layout.addWidget(action_title)

        layout.addWidget(_detail_block("NE DEĞİŞECEK?", impact.effect))
        layout.addWidget(_detail_block("ETKİLENECEK HEDEF", impact.target))
        privilege = (
            "Yönetici yetkisi gereklidir; standart oturumda Windows UAC "
            "onayı açılır."
            if impact.admin_required
            else "Standart kullanıcı yetkisi yeterlidir."
        )
        layout.addWidget(_detail_block("YETKİ", privilege))
        layout.addWidget(_detail_block("OLASI KESİNTİ", impact.interruption))
        layout.addWidget(_detail_block("KORUMA VE GERİ ALMA", impact.rollback))
        self.restore_point_checkbox: QCheckBox | None = None
        if impact.recovery.restore_point_mode == "optional":
            protection = QFrame()
            protection.setObjectName("SafetyDetail")
            protection_layout = QVBoxLayout(protection)
            protection_layout.setContentsMargins(14, 11, 14, 11)
            protection_layout.setSpacing(5)
            self.restore_point_checkbox = QCheckBox(
                "İşlemden önce geri yükleme noktası oluştur (önerilir)"
            )
            self.restore_point_checkbox.setChecked(True)
            note = QLabel(
                "Windows yeni noktayı oluşturup doğrulayamazsa ana işlem "
                "başlamadan önce yeniden sorulur. Bu koruma kişisel dosyaları, "
                "silinmiş verileri veya kaydedilmemiş çalışmaları geri getirmez."
            )
            note.setObjectName("CardSubtitle")
            note.setWordWrap(True)
            protection_layout.addWidget(self.restore_point_checkbox)
            protection_layout.addWidget(note)
            layout.addWidget(protection)
        layout.addStretch()

        buttons = QHBoxLayout()
        cancel = QPushButton("Vazgeç")
        cancel.setObjectName("GhostButton")
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        proceed_text = (
            "Son onaya devam et"
            if impact.confirmation_stages == 2
            else "İşlemi başlat"
        )
        proceed = QPushButton(proceed_text)
        proceed.setObjectName(
            "DangerButton" if impact.is_critical else "PrimaryButton"
        )
        proceed.setAutoDefault(False)
        proceed.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(proceed)
        layout.addLayout(buttons)

    @property
    def restore_point_requested(self) -> bool:
        return bool(
            self.restore_point_checkbox
            and self.restore_point_checkbox.isChecked()
        )


class CriticalConfirmationDialog(QDialog):
    CONFIRMATION_TEXT = "ONAYLA"

    def __init__(
        self,
        impact: OperationImpact,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.impact = impact
        self.setObjectName("SafetyDialog")
        self.setWindowTitle("Kritik işlem — son onay")
        self.resize(610, 400)
        self.setMinimumSize(540, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        risk = QLabel("KRİTİK • SON ONAY 2 / 2")
        risk.setObjectName("SafetyRiskBadge")
        risk.setProperty("risk", "danger")
        risk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(risk, 0, Qt.AlignmentFlag.AlignLeft)

        title = QLabel(impact.title)
        title.setObjectName("PageTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        warning = QLabel(
            "Bu işlem sistem ayarlarını, çalışan uygulamaları veya verileri "
            "geri alınamayacak biçimde etkileyebilir. Gerekirse UAC yalnızca "
            "bu son onaydan sonra açılır."
        )
        warning.setObjectName("PageSubtitle")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addWidget(_detail_block("HEDEF", impact.target))

        prompt = QLabel(
            "İşlemi bilinçli olarak başlatmak için aşağıya ONAYLA yazın."
        )
        prompt.setObjectName("SectionTitle")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.confirmation_input = QLineEdit()
        self.confirmation_input.setObjectName("SafetyConfirmationInput")
        self.confirmation_input.setPlaceholderText("ONAYLA")
        self.confirmation_input.setClearButtonEnabled(True)
        layout.addWidget(self.confirmation_input)
        layout.addStretch()

        buttons = QHBoxLayout()
        cancel = QPushButton("Vazgeç")
        cancel.setObjectName("GhostButton")
        cancel.setDefault(True)
        cancel.clicked.connect(self.reject)
        self.start_button = QPushButton("Kritik işlemi başlat")
        self.start_button.setObjectName("DangerButton")
        self.start_button.setEnabled(False)
        self.start_button.setAutoDefault(False)
        self.start_button.clicked.connect(self.accept)
        self.confirmation_input.textChanged.connect(self._sync_start_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)

    def _sync_start_button(self, text: str) -> None:
        self.start_button.setEnabled(
            text.strip().upper() == self.CONFIRMATION_TEXT
        )


class RestorePointFailureDialog(QDialog):
    def __init__(
        self,
        action_title: str,
        reason: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SafetyDialog")
        self.setWindowTitle("Geri yükleme noktası oluşturulamadı")
        self.resize(620, 420)
        self.setMinimumSize(540, 370)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(14)

        risk = QLabel("KORUMA HAZIR DEĞİL")
        risk.setObjectName("SafetyRiskBadge")
        risk.setProperty("risk", "danger")
        risk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(risk, 0, Qt.AlignmentFlag.AlignLeft)

        title = QLabel("Ana işlem henüz başlamadı")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        explanation = QLabel(
            f"“{action_title}” için doğrulanmış bir geri yükleme noktası "
            "hazırlanamadı. Koruma olmadan devam etmek geri dönüşü "
            "zorlaştırabilir."
        )
        explanation.setObjectName("PageSubtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(_detail_block("AYRINTI", reason))
        layout.addStretch()

        buttons = QHBoxLayout()
        stop = QPushButton("İşlemi durdur")
        stop.setObjectName("GhostButton")
        stop.setDefault(True)
        stop.clicked.connect(self.reject)
        proceed = QPushButton("Geri yükleme noktası olmadan devam et")
        proceed.setObjectName("DangerButton")
        proceed.setAutoDefault(False)
        proceed.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(stop)
        buttons.addWidget(proceed)
        layout.addLayout(buttons)


def confirm_operation(
    parent: QWidget,
    impact: OperationImpact,
) -> OperationConfirmation:
    if impact.confirmation_stages == 0:
        return OperationConfirmation(True)
    review = ImpactReviewDialog(impact, parent)
    if review.exec() != QDialog.DialogCode.Accepted:
        return OperationConfirmation(False)
    create_restore_point = bool(review.restore_point_requested)
    if impact.confirmation_stages == 1:
        return OperationConfirmation(True, create_restore_point)
    critical = CriticalConfirmationDialog(impact, parent)
    return OperationConfirmation(
        critical.exec() == QDialog.DialogCode.Accepted,
        create_restore_point,
    )


def confirm_without_restore_point(
    parent: QWidget,
    action_title: str,
    reason: str,
) -> bool:
    dialog = RestorePointFailureDialog(action_title, reason, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
