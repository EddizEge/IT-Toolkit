from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from app_v2.services.audit_log import AuditLog


class AuditLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "audit" / "operations.jsonl"
        self.audit = AuditLog(
            self.path,
            personal_values=("PrivateUser",),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _record(
        audit: AuditLog,
        index: int = 1,
        *,
        title: str = "Güvenli denetim testi",
        category: str = "Test",
    ) -> bool:
        return audit.record(
            "prepared",
            plan_id=f"{index:032x}",
            action_key="audit_test",
            title=title,
            category=category,
            risk="caution",
            admin_required=True,
        )

    def test_event_is_one_json_line_and_uses_allowlisted_fields(self) -> None:
        title = (
            "PrivateUser C:\\Users\\Other User\\Desktop test@example.com "
            "192.168.1.8 fe80::1 Bearer abc.def.ghi\nikinci satır"
        )

        self.assertTrue(self._record(self.audit, title=title))

        raw = self.path.read_text(encoding="utf-8")
        self.assertEqual(len(raw.splitlines()), 1)
        for secret in (
            "PrivateUser",
            "Other User",
            "test@example.com",
            "192.168.1.8",
            "fe80::1",
            "abc.def.ghi",
        ):
            self.assertNotIn(secret, raw)
        event = json.loads(raw)
        self.assertEqual(event["schema_version"], 1)
        self.assertRegex(event["event_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(event["plan_id"], "0" * 31 + "1")
        for forbidden in ("command", "output", "urls", "target"):
            self.assertNotIn(forbidden, event)

    def test_reader_skips_corrupt_partial_and_unknown_rows(self) -> None:
        self.assertTrue(self._record(self.audit, 1))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write("{bozuk json}\n")
            stream.write(json.dumps({"schema_version": 99}) + "\n")
            stream.write('{"schema_version":1')
        self.assertTrue(self._record(self.audit, 2))

        events = self.audit.read_events(limit=10)

        self.assertEqual([item["plan_id"] for item in events], [
            "0" * 31 + "1",
            "0" * 31 + "2",
        ])

    def test_reader_rebuilds_allowlist_and_masks_tampered_text(self) -> None:
        self.assertTrue(self._record(self.audit, 1))
        value = json.loads(self.path.read_text(encoding="utf-8"))
        value.update(
            {
                "event_id": "f" * 32,
                "title": "private@example.com",
                "command": "token=stolen-command",
                "target": r"C:\Users\Private\Desktop",
            }
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")

        restored = self.audit.read_events(limit=10)[-1]

        self.assertNotIn("command", restored)
        self.assertNotIn("target", restored)
        self.assertNotIn("private@example.com", str(restored))
        self.assertIn("<E-POSTA>", restored["title"])

    def test_size_rotation_keeps_bounded_valid_jsonl_files(self) -> None:
        audit = AuditLog(
            self.path,
            max_bytes=512,
            backup_count=2,
        )

        for index in range(1, 18):
            self.assertTrue(self._record(audit, index, title="X" * 140))

        files = sorted(self.path.parent.glob("operations.jsonl*"))
        self.assertLessEqual(len(files), 3)
        self.assertTrue((self.path.parent / "operations.jsonl.1").exists())
        for path in files:
            self.assertLessEqual(path.stat().st_size, 512)
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertIsInstance(json.loads(line), dict)

    def test_parallel_writes_keep_events_separate(self) -> None:
        threads = [
            threading.Thread(
                target=lambda start=index: [
                    self._record(self.audit, start * 20 + offset + 1)
                    for offset in range(20)
                ]
            )
            for index in range(5)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        events = self.audit.read_events(limit=200)
        self.assertEqual(len(events), 100)
        self.assertEqual(len({item["event_id"] for item in events}), 100)

    def test_two_instances_share_rotation_lock(self) -> None:
        first = AuditLog(self.path, max_bytes=2_048, backup_count=30)
        second = AuditLog(self.path, max_bytes=2_048, backup_count=30)
        results: list[bool] = []
        threads = [
            threading.Thread(
                target=lambda audit=first, start=0: results.extend(
                    self._record(audit, start + offset + 1)
                    for offset in range(50)
                )
            ),
            threading.Thread(
                target=lambda audit=second, start=50: results.extend(
                    self._record(audit, start + offset + 1)
                    for offset in range(50)
                )
            ),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results, [True] * 100)
        events = first.read_events(limit=200)
        self.assertEqual(len(events), 100)
        self.assertEqual(len({item["event_id"] for item in events}), 100)

    def test_oversized_tampered_line_is_skipped(self) -> None:
        self.assertTrue(self._record(self.audit, 1))
        with self.path.open("ab") as stream:
            stream.write(b'{"payload":"' + (b"X" * 100_000) + b'"}\n')
        self.assertTrue(self._record(self.audit, 2))

        events = self.audit.read_events(limit=10)

        self.assertEqual(
            [item["plan_id"] for item in events],
            ["0" * 31 + "1", "0" * 31 + "2"],
        )

    def test_invalid_event_and_identifiers_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.audit.record(
                "unknown",
                plan_id="not-valid",
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
            )
        with self.assertRaises(ValueError):
            self.audit.record(
                "result",
                plan_id="a" * 32,
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
                status="müşteriye ait serbest metin",
            )
        with self.assertRaises(ValueError):
            self.audit.record(
                "result",
                plan_id="a" * 32,
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
                status="failed",
                exit_code="gizli",  # type: ignore[arg-type]
            )
        with self.assertRaises(ValueError):
            self.audit.record(
                "result",
                plan_id="a" * 32,
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
                status="failed",
                exit_code=True,
            )
        with self.assertRaises(ValueError):
            self.audit.record(
                "result",
                plan_id="a" * 32,
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
                task_id="b" * 32,
                status="queued",
            )

    def test_identifiers_cannot_contain_known_personal_values(self) -> None:
        audit = AuditLog(
            self.path,
            personal_values=("PrivateUser",),
        )

        with self.assertRaises(ValueError):
            audit.record(
                "prepared",
                plan_id="a" * 32,
                action_key="PrivateUser",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
            )
        with self.assertRaises(ValueError):
            self.audit.record(
                "prepared",
                plan_id="not-valid",
                action_key="audit_test",
                title="Test",
                category="Test",
                risk="normal",
                admin_required=False,
            )

    def test_write_failure_is_reported_without_exception(self) -> None:
        blocker = Path(self.temporary.name) / "not-a-directory"
        blocker.write_text("dosya", encoding="utf-8")
        audit = AuditLog(blocker / "operations.jsonl")

        self.assertFalse(self._record(audit))


if __name__ == "__main__":
    unittest.main()
