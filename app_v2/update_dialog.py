from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_v2 import __version__
from app_v2.services.error_logging import get_logger
from app_v2.services.update_service import (
    DownloadedUpdate,
    ReleaseInfo,
    UpdateError,
    can_self_update,
    check_for_update,
    download_update,
    schedule_self_update,
)


class UpdateWorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class UpdateWorker(QRunnable):
    def __init__(
        self,
        function: Callable[..., Any],
        *args: Any,
        with_progress: bool = False,
    ) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.with_progress = with_progress
        self.signals = UpdateWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.function(
                    *self.args,
                    progress_callback=self.signals.progress.emit,
                )
            else:
                result = self.function(*self.args)
        except Exception as exc:  # noqa: BLE001 - background worker boundary
            get_logger().exception("Güncelleme işlemi başarısız.")
            self.signals.failed.emit(str(exc))
            return
        self.signals.completed.emit(result)


class UpdateDialog(QDialog):
    def __init__(
        self,
        available_release: ReleaseInfo | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IT Toolkit Güncellemeleri")
        self.resize(650, 540)
        self.setMinimumSize(560, 470)
        self._pool = QThreadPool.globalInstance()
        self._workers: set[UpdateWorker] = set()
        self._release = available_release
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 23, 26, 23)
        layout.setSpacing(14)

        title = QLabel("Uygulama güncellemeleri")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Yeni sürümler doğrudan resmi IT Toolkit GitHub Releases "
            "sayfasından kontrol edilir."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.current_label = QLabel(f"Yüklü sürüm: v{__version__}")
        self.current_label.setObjectName("SectionTitle")
        self.status_label = QLabel("Güncelleme denetimi bekleniyor.")
        self.status_label.setObjectName("CardSubtitle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.current_label)
        layout.addWidget(self.status_label)

        self.notes = QPlainTextEdit()
        self.notes.setObjectName("FeedbackText")
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText(
            "Yeni bir sürüm bulunduğunda sürüm notları burada gösterilir."
        )
        layout.addWidget(self.notes, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.hide()
        layout.addWidget(self.progress)

        security_note = QLabel(
            "Kurulumdan önce EXE dosyasının SHA-256 özeti doğrulanır. "
            "Doğrulama başarısızsa güncelleme uygulanmaz."
        )
        security_note.setObjectName("CardSubtitle")
        security_note.setWordWrap(True)
        layout.addWidget(security_note)

        buttons = QHBoxLayout()
        close_button = QPushButton("Kapat")
        close_button.setObjectName("GhostButton")
        close_button.clicked.connect(self.reject)
        self.release_button = QPushButton("Sürüm sayfasını aç")
        self.release_button.setObjectName("GhostButton")
        self.release_button.setEnabled(False)
        self.release_button.clicked.connect(self._open_release_page)
        self.check_button = QPushButton("Güncellemeleri denetle")
        self.check_button.setObjectName("GhostButton")
        self.check_button.clicked.connect(self.check_now)
        self.install_button = QPushButton("İndir ve güncelle")
        self.install_button.setObjectName("PrimaryButton")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._download)
        buttons.addWidget(close_button)
        buttons.addStretch()
        buttons.addWidget(self.release_button)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)

        if self._release:
            self._show_release(self._release)
        else:
            QTimer.singleShot(0, self.check_now)

    def check_now(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "GitHub sürümleri kontrol ediliyor…")
        worker = UpdateWorker(check_for_update)
        self._workers.add(worker)

        def completed(result: ReleaseInfo | None) -> None:
            self._workers.discard(worker)
            self._set_busy(False)
            if result:
                self._show_release(result)
            else:
                self._release = None
                self.notes.clear()
                self.status_label.setText(
                    f"v{__version__} şu anda kullanılabilir en güncel sürüm."
                )
                self.install_button.setEnabled(False)
                self.release_button.setEnabled(False)

        def failed(message: str) -> None:
            self._workers.discard(worker)
            self._set_busy(False)
            self.status_label.setText(message)

        worker.signals.completed.connect(completed)
        worker.signals.failed.connect(failed)
        self._pool.start(worker)

    def _show_release(self, release: ReleaseInfo) -> None:
        self._release = release
        size_mb = release.asset_size / (1024 * 1024) if release.asset_size else 0
        size_text = f" • {size_mb:.1f} MB" if size_mb else ""
        self.status_label.setText(
            f"Yeni sürüm bulundu: {release.tag}{size_text}"
        )
        self.notes.setPlainText(
            release.notes.strip() or "Bu yayın için sürüm notu bulunmuyor."
        )
        self.install_button.setEnabled(True)
        self.release_button.setEnabled(bool(release.page_url))

    def _download(self) -> None:
        if self._busy or not self._release:
            return
        self._set_busy(True, f"{self._release.tag} indiriliyor ve doğrulanıyor…")
        self.progress.setRange(0, 0)
        self.progress.show()
        worker = UpdateWorker(
            download_update,
            self._release,
            with_progress=True,
        )
        self._workers.add(worker)

        def progress(received: int, total: int) -> None:
            if total <= 0:
                self.progress.setRange(0, 0)
                return
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, round(received / total * 100)))

        def completed(downloaded: DownloadedUpdate) -> None:
            self._workers.discard(worker)
            self._set_busy(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self._offer_restart(downloaded)

        def failed(message: str) -> None:
            self._workers.discard(worker)
            self._set_busy(False)
            self.progress.hide()
            QMessageBox.critical(self, "Güncelleme başarısız", message)

        worker.signals.progress.connect(progress)
        worker.signals.completed.connect(completed)
        worker.signals.failed.connect(failed)
        self._pool.start(worker)

    def _offer_restart(self, downloaded: DownloadedUpdate) -> None:
        if not can_self_update():
            self.status_label.setText(
                "Paket doğrulandı. Otomatik kurulum yalnızca taşınabilir EXE "
                "sürümünde kullanılabilir."
            )
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(downloaded.path.parent))
            )
            return
        answer = QMessageBox.question(
            self,
            "Güncelleme hazır",
            "Güncelleme doğrulandı. IT Toolkit kapatılıp yeni sürümle yeniden "
            "başlatılsın mı?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status_label.setText(
                "Güncelleme indirildi; uygulama yeniden başlatıldığında tekrar "
                "uygulanabilir."
            )
            return
        try:
            schedule_self_update(
                downloaded.path,
                expected_sha256=downloaded.sha256,
            )
        except UpdateError as exc:
            QMessageBox.critical(self, "Güncelleme başlatılamadı", str(exc))
            return
        QApplication.quit()

    def _open_release_page(self) -> None:
        if self._release and self._release.page_url:
            QDesktopServices.openUrl(QUrl(self._release.page_url))

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.check_button.setEnabled(not busy)
        self.install_button.setEnabled(not busy and self._release is not None)
        if message:
            self.status_label.setText(message)

    def reject(self) -> None:
        if self._busy:
            QMessageBox.information(
                self,
                "İşlem devam ediyor",
                "Güncelleme işlemi tamamlanana kadar bu pencereyi kapatmayın.",
            )
            return
        super().reject()
