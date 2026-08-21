from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app_v2.services.error_logging import (
    LOG_FILE_NAME,
    close_logging,
    configure_logging,
    read_recent_log,
    sanitize_text,
)


class ErrorLoggingTests(unittest.TestCase):
    def test_sensitive_values_are_masked_before_sharing(self) -> None:
        content = (
            r"C:\Users\TestUser\Desktop\report.txt "
            "test@example.com 192.168.1.25 AA:BB:CC:DD:EE:FF "
            "ABCDE-FGHIJ-KLMNO-PQRST-UVWXY token=very-secret"
        )

        sanitized = sanitize_text(
            content,
            personal_values=(r"C:\Users\TestUser", "TestUser"),
        )

        self.assertNotIn("TestUser", sanitized)
        self.assertNotIn("test@example.com", sanitized)
        self.assertNotIn("192.168.1.25", sanitized)
        self.assertNotIn("AA:BB:CC:DD:EE:FF", sanitized)
        self.assertNotIn("ABCDE-FGHIJ-KLMNO-PQRST-UVWXY", sanitized)
        self.assertNotIn("very-secret", sanitized)
        self.assertIn("<IP_ADRESI>", sanitized)

    def test_configured_logger_writes_and_reads_a_sanitized_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            logger = configure_logging(directory)
            try:
                logger.error("Bağlantı hatası: 10.0.0.8 user@example.com")
                for handler in logger.handlers:
                    handler.flush()

                self.assertTrue((directory / LOG_FILE_NAME).exists())
                shared = read_recent_log(directory)
                self.assertNotIn("10.0.0.8", shared)
                self.assertNotIn("user@example.com", shared)
                self.assertIn("<IP_ADRESI>", shared)
            finally:
                close_logging()


if __name__ == "__main__":
    unittest.main()
