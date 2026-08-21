from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from app_v2.services.feedback_service import (
    FEEDBACK_TEMPLATE,
    MAX_ISSUE_URL_LENGTH,
    FeedbackDraft,
    feedback_report_text,
    github_issue_url,
)


class FeedbackServiceTests(unittest.TestCase):
    def test_report_masks_sensitive_values(self) -> None:
        draft = FeedbackDraft(
            category="Uygulama hatası",
            title="Ağ ekranında hata",
            details="192.168.1.20 adresinde user@example.com göründü.",
            diagnostics="token=secret-value",
        )

        report = feedback_report_text(draft)

        self.assertNotIn("192.168.1.20", report)
        self.assertNotIn("user@example.com", report)
        self.assertNotIn("secret-value", report)
        self.assertIn("<IP_ADRESI>", report)

    def test_github_url_prefills_feedback_form(self) -> None:
        draft = FeedbackDraft(
            category="Özellik önerisi",
            title="Yeni rapor görünümü",
            details="Teslim raporu daha kolay okunmalı.",
            steps="Akıllı Tanılama sayfasını aç.",
            diagnostics="Günlük temiz.",
        )

        url = github_issue_url(draft)
        query = parse_qs(urlparse(url).query)

        self.assertEqual(query["template"], [FEEDBACK_TEMPLATE])
        self.assertEqual(query["category"], ["Özellik önerisi"])
        self.assertEqual(query["details"], ["Teslim raporu daha kolay okunmalı."])
        self.assertTrue(query["version"][0].startswith("v0.6.0"))
        self.assertIn("[Uygulama Geri Bildirimi]", query["title"][0])

    def test_long_diagnostic_is_trimmed_to_safe_url_length(self) -> None:
        draft = FeedbackDraft(
            category="Uygulama hatası",
            title="Uzun günlük",
            details="Açıklama",
            diagnostics="x" * 30_000,
        )

        url = github_issue_url(draft)

        self.assertLessEqual(len(url), MAX_ISSUE_URL_LENGTH)
        self.assertIn("diagnostics=", url)

    def test_long_unicode_fields_do_not_exceed_url_limit(self) -> None:
        draft = FeedbackDraft(
            category="Uygulama hatası",
            title="Türkçe günlük",
            details="çalıştırılamadı " * 2_000,
            steps="düğmeye bastım " * 1_000,
            diagnostics="günlük satırı şçğıöü " * 2_000,
        )

        self.assertLessEqual(
            len(github_issue_url(draft)),
            MAX_ISSUE_URL_LENGTH,
        )


if __name__ == "__main__":
    unittest.main()
