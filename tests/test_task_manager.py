from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

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
        self.manager = TaskManager(
            history_path=self.history_path,
            script_directory=self.script_directory,
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
        )
        self.assertTrue(self.wait_until(lambda: task.status == "running"))
        self.assertTrue(self.manager.cancel(task.id))
        self.assertTrue(
            self.wait_until(lambda: task.status == "cancelled"),
            task.output,
        )
        self.assertIn("iptal", task.message.casefold())

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
                        "id": "previous-task",
                        "title": "Önceki görev",
                        "command": "ping 127.0.0.1 -t",
                        "category": "Test",
                        "status": "running",
                        "created_at": "2026-07-29T10:00:00+03:00",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        restored = TaskManager(history_path=self.history_path)

        self.assertEqual(restored.tasks[0].status, "interrupted")
        self.assertIn("yarım kaldı", restored.tasks[0].message)

    def test_powershell_variables_are_executed_instead_of_echoed(self) -> None:
        task = self.manager.start_command(
            "PowerShell testi",
            powershell_command(
                "$value=42; Write-Output ('GERCEK_DEGER='+$value)"
            ),
            category="Test",
        )

        self.assertTrue(
            self.wait_until(lambda: task.status == "succeeded"),
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


if __name__ == "__main__":
    unittest.main()
