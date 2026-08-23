from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app_v2.services.audit_log import AuditLog
from app_v2.services.command_builder import (
    aggregate_sequence,
    powershell_command,
)
from app_v2.services.task_manager import TaskManager


class TaskManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temporary.name) / "history.json"
        self.script_directory = Path(self.temporary.name) / "task scripts"
        self.audit_log = AuditLog(
            Path(self.temporary.name) / "audit" / "operations.jsonl"
        )
        self.manager = TaskManager(
            history_path=self.history_path,
            script_directory=self.script_directory,
            audit_log=self.audit_log,
        )

    def tearDown(self) -> None:
        self.manager.shutdown()
        self.app.processEvents()
        self.temporary.cleanup()

    def wait_until(self, predicate, timeout: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    def test_successful_task_captures_output_and_persists(self) -> None:
        task = self.manager.start_command(
            "Çıktı testi",
            "echo Gorev test ciktisi",
            category="Test",
        )

        self.assertTrue(
            self.wait_until(lambda: task.status == "succeeded"),
            task.output,
        )
        self.assertIn("Gorev test ciktisi", task.output)
        self.assertEqual(task.exit_code, 0)
        self.assertTrue(self.history_path.exists())

        restored = TaskManager(history_path=self.history_path)
        self.assertEqual(len(restored.tasks), 1)
        self.assertEqual(restored.tasks[0].status, "succeeded")
        self.assertIn("Çıktı testi", restored.report_text(task.id))
        self.assertEqual(list(self.script_directory.glob("*.cmd")), [])

    def test_failed_task_keeps_exit_code(self) -> None:
        task = self.manager.start_command(
            "Hata testi",
            "exit /b 7",
            category="Test",
        )

        self.assertTrue(self.wait_until(lambda: task.status == "failed"))
        self.assertEqual(task.exit_code, 7)
        self.assertIn("7 çıkış koduyla", task.message)

    def test_running_task_can_be_cancelled(self) -> None:
        task = self.manager.start_command(
            "İptal testi",
            "ping 127.0.0.1 -t",
            category="Test",
            plan_id="c" * 32,
            action_key="cancel_test",
            risk="caution",
        )
        self.assertTrue(self.wait_until(lambda: task.status == "running"))
        self.assertTrue(self.manager.cancel(task.id))
        self.assertTrue(
            self.wait_until(lambda: task.status == "cancelled"),
            task.output,
        )
        self.assertIn("iptal", task.message.casefold())
        events = self.audit_log.read_events(limit=20)
        self.assertEqual(
            [item["event"] for item in events],
            ["started", "cancel_requested", "result"],
        )
        self.assertEqual(
            sum(item["event"] == "result" for item in events),
            1,
        )

    def test_clear_finished_preserves_running_tasks(self) -> None:
        running = self.manager.start_command(
            "Çalışan görev",
            "ping 127.0.0.1 -t",
            category="Test",
        )
        self.assertTrue(self.wait_until(lambda: running.status == "running"))
        self.manager.record_result(
            "Tamamlanan görev",
            "Bitti",
            success=True,
            category="Test",
        )

        self.manager.clear_finished()

        self.assertEqual([task.id for task in self.manager.tasks], [running.id])
        self.manager.cancel(running.id)
        self.assertTrue(
            self.wait_until(lambda: running.status == "cancelled")
        )

    def test_previous_running_task_is_marked_interrupted(self) -> None:
        self.history_path.write_text(
            json.dumps(
                [
                    {
                        "id": "9" * 32,
                        "title": "Önceki görev",
                        "command": "ping 127.0.0.1 -t",
                        "category": "Test",
                        "status": "running",
                        "created_at": "2026-07-29T10:00:00+03:00",
                        "plan_id": "d" * 32,
                        "action_key": "previous_task",
                        "risk": "caution",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        restored = TaskManager(
            history_path=self.history_path,
            audit_log=self.audit_log,
        )

        self.assertEqual(restored.tasks[0].status, "interrupted")
        self.assertIn("yarım kaldı", restored.tasks[0].message)
        events = self.audit_log.read_events(limit=10)
        self.assertEqual([item["event"] for item in events], ["result"])
        self.assertEqual(events[0]["status"], "interrupted")

    def test_powershell_variables_are_executed_instead_of_echoed(self) -> None:
        task = self.manager.start_command(
            "PowerShell testi",
            powershell_command(
                "$value=42; Write-Output ('GERCEK_DEGER='+$value)"
            ),
            category="Test",
        )

        self.assertTrue(
            self.wait_until(
                lambda: task.status == "succeeded",
                timeout=20.0,
            ),
            task.output,
        )
        self.assertIn("GERCEK_DEGER=42", task.output)
        self.assertNotIn("$value=42", task.output)

    def test_aggregate_sequence_does_not_hide_an_earlier_failure(self) -> None:
        task = self.manager.start_command(
            "Birleşik komut testi",
            aggregate_sequence(
                (
                    "cmd /d /c exit 7",
                    "echo IKINCI_KOMUT_CALISTI",
                )
            ),
            category="Test",
        )

        self.assertTrue(
            self.wait_until(lambda: task.status == "failed"),
            task.output,
        )
        self.assertIn("IKINCI_KOMUT_CALISTI", task.output)
        self.assertEqual(task.exit_code, 1)
        self.assertEqual(list(self.script_directory.glob("*.cmd")), [])

    def test_audited_task_persists_plan_id_and_single_result(self) -> None:
        plan_id = "a" * 32
        task = self.manager.start_command(
            "Denetlenen görev",
            "echo AUDIT_SECRET_OUTPUT",
            category="Test",
            plan_id=plan_id,
            action_key="audited_task",
            risk="normal",
        )

        self.assertTrue(self.wait_until(lambda: task.status == "succeeded"))
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["started", "result"],
        )
        self.assertEqual({item["plan_id"] for item in events}, {plan_id})
        self.assertEqual(events[-1]["status"], "succeeded")
        self.assertNotIn(
            "AUDIT_SECRET_OUTPUT",
            self.audit_log.path.read_text(encoding="utf-8"),
        )
        self.assertIn(plan_id, self.manager.report_text(task.id))

        restored = TaskManager(
            history_path=self.history_path,
            audit_log=self.audit_log,
        )
        self.assertEqual(restored.tasks[0].plan_id, plan_id)
        self.assertEqual(restored.tasks[0].action_key, "audited_task")

    def test_delegated_admin_task_has_no_false_local_success(self) -> None:
        with (
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=False,
            ),
            patch(
                "app_v2.services.task_manager.run_command",
                return_value=(True, "Yönetici penceresi açıldı."),
            ),
        ):
            task = self.manager.start_command(
                "Yetkili görev",
                "echo admin",
                category="Test",
                admin=True,
                plan_id="b" * 32,
                action_key="admin_test",
                risk="caution",
            )

        self.assertEqual(task.status, "delegated")
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["delegated", "result"],
        )
        self.assertEqual(events[-1]["status"], "delegated")

    def test_corrupt_history_item_does_not_hide_valid_task(self) -> None:
        self.history_path.write_text(
            json.dumps(
                [
                    {"title": "Eksik görev"},
                    {
                        "id": "valid-task",
                        "title": "Geçerli görev",
                        "command": "echo ok",
                        "category": "Test",
                        "status": "succeeded",
                        "created_at": "2026-08-23T10:00:00+03:00",
                        "plan_id": "bozuk",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        restored = TaskManager(
            history_path=self.history_path,
            audit_log=self.audit_log,
        )

        self.assertEqual(len(restored.tasks), 1)
        self.assertEqual(restored.tasks[0].id, "valid-task")
        self.assertEqual(restored.tasks[0].plan_id, "")

    def test_invalid_active_history_types_do_not_break_recovery(self) -> None:
        self.history_path.write_text(
            json.dumps(
                [
                    {
                        "id": 123,
                        "title": "Bozuk etkin görev",
                        "command": "echo broken",
                        "category": "Test",
                        "status": "running",
                        "created_at": "2026-08-23T10:00:00+03:00",
                        "plan_id": "e" * 32,
                        "action_key": "broken_active",
                    },
                    {
                        "id": "valid-history-task",
                        "title": "Geçerli geçmiş görevi",
                        "command": "echo ok",
                        "category": "Test",
                        "status": "succeeded",
                        "created_at": "2026-08-23T10:01:00+03:00",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        restored = TaskManager(
            history_path=self.history_path,
            audit_log=self.audit_log,
        )

        self.assertEqual(
            [task.id for task in restored.tasks],
            ["valid-history-task"],
        )
        self.assertEqual(self.audit_log.read_events(), ())

    def test_failed_terminal_audit_can_be_retried(self) -> None:
        with patch.object(
            self.audit_log,
            "record",
            side_effect=(False, False, True),
        ) as record:
            task = self.manager.record_result(
                "Yeniden denenen sonuç",
                "Tamamlandı",
                success=True,
                category="Test",
                plan_id="f" * 32,
                action_key="retry_result",
            )

            self.assertFalse(task.audit_result_recorded)
            self.manager._retry_terminal_audit(task.id)
            self.assertFalse(task.audit_result_recorded)
            self.assertIn(task.id, self.manager._audit_retry_timers)
            self.manager._retry_terminal_audit(task.id)
            self.assertTrue(task.audit_result_recorded)
            self.assertFalse(self.manager._record_terminal_audit(task))

        self.assertEqual(record.call_count, 3)

    def test_clear_finished_preserves_pending_terminal_audit(self) -> None:
        with patch.object(self.audit_log, "record", return_value=False):
            task = self.manager.record_result(
                "Temizlemede korunan sonuç",
                "Tamamlandı",
                success=True,
                category="Test",
                plan_id="4" * 32,
                action_key="clear_pending_result",
            )
            self.manager.clear_finished()

        self.assertIn(task, self.manager.tasks)
        self.assertFalse(task.audit_result_recorded)

        self.manager.shutdown()

        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["result"],
        )
        self.assertTrue(task.audit_result_recorded)

    def test_shutdown_retries_a_temporarily_failed_terminal_audit(self) -> None:
        with patch.object(self.audit_log, "record", return_value=False):
            task = self.manager.record_result(
                "Kapanışta yeniden denenen sonuç",
                "Tamamlandı",
                success=True,
                category="Test",
                plan_id="1" * 32,
                action_key="shutdown_retry",
            )

        self.assertFalse(task.audit_result_recorded)
        self.assertEqual(self.audit_log.read_events(), ())

        self.manager.shutdown()

        events = self.audit_log.read_events(limit=10)
        self.assertEqual([item["event"] for item in events], ["result"])
        self.assertTrue(task.audit_result_recorded)

    def test_existing_terminal_audit_repairs_stale_running_history(self) -> None:
        task_id = "2" * 32
        plan_id = "3" * 32
        self.assertTrue(
            self.audit_log.record(
                "result",
                plan_id=plan_id,
                action_key="recovered_result",
                title="Kurtarılan görev",
                category="Test",
                risk="normal",
                admin_required=False,
                task_id=task_id,
                status="succeeded",
                exit_code=0,
            )
        )
        self.history_path.write_text(
            json.dumps(
                [
                    {
                        "id": task_id,
                        "title": "Kurtarılan görev",
                        "command": "echo ok",
                        "category": "Test",
                        "status": "running",
                        "created_at": "2026-08-23T10:00:00+03:00",
                        "plan_id": plan_id,
                        "action_key": "recovered_result",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        restored = TaskManager(
            history_path=self.history_path,
            audit_log=self.audit_log,
        )

        self.assertEqual(restored.tasks[0].status, "succeeded")
        self.assertEqual(restored.tasks[0].exit_code, 0)
        self.assertTrue(restored.tasks[0].audit_result_recorded)
        self.assertIn("denetim günlüğünden", restored.tasks[0].message)
        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["result"],
        )

    def test_recovered_interrupted_task_schedules_audit_retry(self) -> None:
        task_id = "5" * 32
        self.history_path.write_text(
            json.dumps(
                [
                    {
                        "id": task_id,
                        "title": "Kurtarmada yeniden denenen görev",
                        "command": "echo pending",
                        "category": "Test",
                        "status": "running",
                        "created_at": "2026-08-23T10:00:00+03:00",
                        "plan_id": "6" * 32,
                        "action_key": "recovery_retry",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with patch.object(self.audit_log, "record", return_value=False):
            restored = TaskManager(
                history_path=self.history_path,
                audit_log=self.audit_log,
            )

        self.assertIn(task_id, restored._audit_retry_timers)
        restored._retry_terminal_audit(task_id)

        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["result"],
        )
        self.assertTrue(restored.tasks[0].audit_result_recorded)
        restored.shutdown()


if __name__ == "__main__":
    unittest.main()
