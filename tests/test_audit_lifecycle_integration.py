from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app_v2.pages.tools_page import ToolsPage
from app_v2.registry import ToolAction
from app_v2.services.audit_log import AuditLog
from app_v2.services.task_manager import TaskManager


class AuditLifecycleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.audit_log = AuditLog(root / "audit" / "operations.jsonl")
        self.manager = TaskManager(
            history_path=root / "history.json",
            script_directory=root / "scripts",
            audit_log=self.audit_log,
        )
        self.action = ToolAction(
            "audit_lifecycle",
            "Denetim yaşam döngüsü",
            "Zararsız entegrasyon komutu.",
            "Test",
            "echo AUDIT_COMMAND_OUTPUT_SECRET",
            keep_open=False,
        )
        self.page = ToolsPage(
            "Test",
            "Denetim entegrasyonu",
            (self.action,),
            task_manager=self.manager,
        )

    def tearDown(self) -> None:
        self.page.close()
        self.manager.shutdown()
        self.app.processEvents()
        self.temporary.cleanup()

    def _wait_until(self, predicate, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        return False

    def test_full_plan_and_task_lifecycle_share_one_correlation_id(self) -> None:
        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=True,
        ):
            self.page.execute_action(self.action)

        self.assertTrue(
            self._wait_until(
                lambda: bool(self.manager.tasks)
                and self.manager.tasks[0].status == "succeeded"
            )
        )
        events = self.audit_log.read_events(limit=10)

        self.assertEqual(
            [event["event"] for event in events],
            ["prepared", "approved", "started", "result"],
        )
        self.assertEqual(len({event["plan_id"] for event in events}), 1)
        self.assertEqual(events[1]["approval_mode"], "automatic")
        self.assertEqual(events[-1]["status"], "succeeded")
        self.assertNotIn(
            "AUDIT_COMMAND_OUTPUT_SECRET",
            self.audit_log.path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
