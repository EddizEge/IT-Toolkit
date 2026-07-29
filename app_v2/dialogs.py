from __future__ import annotations

import io

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app_v2.registry import PackageItem


class InstallerDialog(QDialog):
    def __init__(
        self,
        title: str,
        subtitle: str,
        packages: tuple[PackageItem, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 650)
        self.setMinimumSize(500, 520)
        self._packages = packages
        self._checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(6)

        for package in packages:
            checkbox = QCheckBox(package.name)
            checkbox.setChecked(package.default)
            checkbox.setToolTip(
                "Winget paketi" if package.source == "winget" else "Resmi indirme bağlantısı"
            )
            self._checks[package.name] = checkbox
            scroll_layout.addWidget(checkbox)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        note = QLabel(
            "Winget paketleri yönetici yetkisiyle kurulur. Web bağlantıları varsayılan "
            "tarayıcıda açılır."
        )
        note.setObjectName("CardSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)

        button_row = QHBoxLayout()
        cancel = QPushButton("Vazgeç")
        cancel.setObjectName("GhostButton")
        cancel.clicked.connect(self.reject)
        install = QPushButton("Seçilenleri Başlat")
        install.setObjectName("PrimaryButton")
        install.clicked.connect(self._accept_if_selected)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(install)
        layout.addLayout(button_row)

    def selected_packages(self) -> list[PackageItem]:
        return [
            package
            for package in self._packages
            if self._checks[package.name].isChecked()
        ]

    def _accept_if_selected(self) -> None:
        if not self.selected_packages():
            QMessageBox.information(
                self,
                "Paket seçilmedi",
                "Devam etmek için en az bir paket seçin.",
            )
            return
        self.accept()


class WifiQrDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wi-Fi QR Kodu")
        self.setFixedSize(480, 610)
        self._png_data: bytes | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(11)

        title = QLabel("Wi-Fi QR kodu oluştur")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Ağ bilgileri yalnızca bu bilgisayarda işlenir; herhangi bir sunucuya gönderilmez."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        self.ssid = QLineEdit()
        self.ssid.setObjectName("DialogInput")
        self.ssid.setPlaceholderText("Wi-Fi ağ adı (SSID)")

        self.password = QLineEdit()
        self.password.setObjectName("DialogInput")
        self.password.setPlaceholderText("Wi-Fi parolası")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.security = QComboBox()
        self.security.addItem("WPA / WPA2 / WPA3", "WPA")
        self.security.addItem("WEP", "WEP")
        self.security.addItem("Parolasız ağ", "nopass")

        show_password = QCheckBox("Parolayı göster")
        show_password.toggled.connect(
            lambda checked: self.password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )

        generate = QPushButton("QR Kodunu Oluştur")
        generate.setObjectName("PrimaryButton")
        generate.clicked.connect(self._generate)

        self.preview = QLabel("QR kodu burada görüntülenecek")
        self.preview.setObjectName("Panel")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(285)

        button_row = QHBoxLayout()
        close = QPushButton("Kapat")
        close.setObjectName("GhostButton")
        close.clicked.connect(self.reject)
        self.save = QPushButton("PNG Olarak Kaydet")
        self.save.setObjectName("GhostButton")
        self.save.setEnabled(False)
        self.save.clicked.connect(self._save)
        button_row.addWidget(close)
        button_row.addStretch()
        button_row.addWidget(self.save)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.ssid)
        layout.addWidget(self.password)
        layout.addWidget(self.security)
        layout.addWidget(show_password)
        layout.addWidget(generate)
        layout.addWidget(self.preview)
        layout.addLayout(button_row)

    @staticmethod
    def _escape(value: str) -> str:
        result = value.replace("\\", "\\\\")
        for character in (";", ",", ":", '"'):
            result = result.replace(character, f"\\{character}")
        return result

    def _generate(self) -> None:
        ssid = self.ssid.text().strip()
        security = str(self.security.currentData())
        password = self.password.text()
        if not ssid:
            QMessageBox.information(self, "Eksik bilgi", "Wi-Fi ağ adını yazın.")
            return
        if security != "nopass" and not password:
            QMessageBox.information(self, "Eksik bilgi", "Wi-Fi parolasını yazın.")
            return

        try:
            import qrcode
        except ImportError:
            QMessageBox.critical(
                self,
                "Eksik bağımlılık",
                "QR kod bileşeni kurulu değil. requirements.txt bağımlılıklarını kurun.",
            )
            return

        payload = (
            f"WIFI:T:{security};S:{self._escape(ssid)};"
            f"P:{self._escape(password) if security != 'nopass' else ''};;"
        )
        image = qrcode.make(payload)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        self._png_data = buffer.getvalue()

        pixmap = QPixmap()
        pixmap.loadFromData(self._png_data, "PNG")
        self.preview.setPixmap(
            pixmap.scaled(
                260,
                260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.save.setEnabled(True)

    def _save(self) -> None:
        if not self._png_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "QR kodunu kaydet",
            "wifi_qr.png",
            "PNG Görseli (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            with open(path, "wb") as handle:
                handle.write(self._png_data)
        except OSError as exc:
            QMessageBox.critical(self, "Kaydetme hatası", str(exc))
