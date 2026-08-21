from __future__ import annotations

import unittest

from app_v2.services.health_service import (
    customer_report_html,
    evaluate_health,
    report_text,
)


def healthy_data() -> dict[str, object]:
    return {
        "volumes": [{"drive": "C:", "percent": 40, "free_gb": 240}],
        "physical_disks": [
            {
                "name": "Test SSD",
                "health": "Healthy",
                "operational": "OK",
            }
        ],
        "memory_percent": 48,
        "uptime_days": 3,
        "reboot_required": False,
        "last_update_days": 8,
        "battery": {"wear_percent": 92},
    }


class HealthServiceTests(unittest.TestCase):
    def test_healthy_device_scores_one_hundred_with_explanations(self) -> None:
        report = evaluate_health(healthy_data())

        self.assertEqual(report.score, 100)
        self.assertEqual(report.label, "Çok iyi")
        self.assertEqual(report.critical_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.good_count, 7)
        self.assertEqual(report.device_type, "Dizüstü / taşınabilir cihaz")
        self.assertEqual(len(report.device_recommendations), 3)
        self.assertTrue(all(item.evidence for item in report.findings))
        self.assertTrue(all(item.recommendation for item in report.findings))

    def test_warning_deductions_are_visible_and_additive(self) -> None:
        data = healthy_data()
        data.update(
            {
                "volumes": [{"drive": "C:", "percent": 90, "free_gb": 12}],
                "memory_percent": 90,
                "uptime_days": 20,
                "reboot_required": True,
                "last_update_days": 40,
                "battery": {"wear_percent": 60},
            }
        )

        report = evaluate_health(data)

        self.assertEqual(report.score, 50)
        self.assertEqual(report.warning_count, 6)
        self.assertEqual(sum(item.deduction for item in report.findings), 50)
        self.assertEqual(report.findings[0].severity, "warning")

    def test_critical_findings_clamp_score_at_zero(self) -> None:
        data = healthy_data()
        data.update(
            {
                "volumes": [{"drive": "C:", "percent": 98, "free_gb": 2}],
                "physical_disks": [
                    {
                        "name": "Riskli disk",
                        "health": "Unhealthy",
                        "operational": "Degraded",
                    }
                ],
                "memory_percent": 98,
                "last_update_days": 90,
                "battery": {"wear_percent": 40},
            }
        )

        report = evaluate_health(data)

        self.assertEqual(report.score, 0)
        self.assertEqual(report.label, "Kritik")
        self.assertGreaterEqual(report.critical_count, 5)
        self.assertEqual(report.findings[0].severity, "critical")

    def test_missing_optional_data_is_neutral_information(self) -> None:
        report = evaluate_health(
            {
                "volumes": [],
                "physical_disks": [],
                "memory_percent": 35,
                "uptime_days": 2,
                "reboot_required": None,
                "last_update_days": None,
                "battery": None,
            }
        )

        self.assertEqual(report.score, 100)
        self.assertEqual(report.critical_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(sum(item.severity == "info" for item in report.findings), 5)

    def test_text_report_contains_score_evidence_and_recommendation(self) -> None:
        text = report_text(evaluate_health(healthy_data()))

        self.assertIn("Sağlık puanı: 100/100", text)
        self.assertIn("Kanıt:", text)
        self.assertIn("Öneri:", text)
        self.assertNotIn("Kullanıcı", text)
        self.assertNotIn("IPv4", text)

    def test_single_powershell_record_is_normalized(self) -> None:
        data = healthy_data()
        data["volumes"] = {"drive": "C:", "percent": 45, "free_gb": 100}
        data["physical_disks"] = {
            "name": "Tek disk",
            "health": "Healthy",
            "operational": "OK",
        }

        report = evaluate_health(data)

        self.assertEqual(report.score, 100)
        self.assertTrue(any(item.title == "C: disk alanı" for item in report.findings))
        self.assertTrue(any(item.title == "Tek disk" for item in report.findings))

    def test_device_profile_changes_recommendations(self) -> None:
        laptop = healthy_data()
        laptop["device_type"] = "Laptop"
        desktop = healthy_data()
        desktop["device_type"] = "Desktop"
        desktop["battery"] = None

        laptop_report = evaluate_health(laptop)
        desktop_report = evaluate_health(desktop)

        self.assertTrue(laptop_report.device_type.startswith("Dizüstü"))
        self.assertTrue(desktop_report.device_type.startswith("Masaüstü"))
        self.assertNotEqual(
            laptop_report.device_recommendations,
            desktop_report.device_recommendations,
        )

    def test_customer_html_masks_notes_and_escapes_markup(self) -> None:
        report = evaluate_health(healthy_data())

        html = customer_report_html(
            report,
            "Müşteri: user@example.com\n<script>alert('x')</script>",
        )

        self.assertIn("IT Toolkit Müşteri Teslim Raporu", html)
        self.assertIn("&lt;E-POSTA&gt;", html)
        self.assertNotIn("user@example.com", html)
        self.assertNotIn("<script>", html)
        self.assertIn("Teknisyen notları", html)
        self.assertIn("Cihaza özel güvenli öneriler", html)


if __name__ == "__main__":
    unittest.main()
