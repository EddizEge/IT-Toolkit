from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app_v2 import __version__
from app_v2.main_window import MainWindow
from app_v2.services.error_logging import (
    close_logging,
    configure_logging,
    install_exception_logging,
)
from app_v2.theme import app_font, build_stylesheet


def main() -> int:
    logger = configure_logging()
    logger.info("IT Toolkit v%s başlatılıyor.", __version__)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("IT Toolkit")
    app.setOrganizationName("Ediz Ege Mercan")
    app.setStyle("Fusion")
    app.setFont(app_font())
    app.setStyleSheet(build_stylesheet())
    install_exception_logging(
        lambda _message: QMessageBox.critical(
            None,
            "Beklenmeyen uygulama hatası",
            "Beklenmeyen bir hata kaydedildi. Uygulama açık kalırsa üst "
            "çubuktaki “Geri Bildirim” ekranından maskelenmiş günlüğü "
            "inceleyip bize iletebilirsiniz.",
        )
    )

    window = MainWindow()
    window.show()
    result = app.exec()
    logger.info("IT Toolkit normal biçimde kapatıldı.")
    close_logging()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
