from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app_v2.pages.tasks import TaskCenterPage
from app_v2.services.audit_log import AuditLog
from app_v2.services.task_manager import TaskManager


class TaskCenterPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.manager = TaskManager(
            history_path=root / "history.json",
            audit_log=AuditLog(root / "audit" / "operations.jsonl"),
        )
        self.page = TaskCenterPage(self.manager)

    def tearDown(self) -> None:
        self.page.close()
        self.manager.shutdown()
        self.app.processEvents()
        self.temporary.cleanup()

    def test_selected_task_shows_short_id_and_report_keeps_full_id(self) -> None:
        plan_id = "a1" * 16
        task = self.manager.record_result(
            "Denetimli ekran görevi",
            "Tamamlandı",
            success=True,
            category="Test",
            plan_id=plan_id,
            action_key="task_center_audit",
        )

        self.page.show_task(task.id)

        self.assertIn(plan_id[:12], self.page.meta.text())
        self.assertNotIn(plan_id, self.page.meta.text())
        self.assertIn(plan_id, self.page.meta.toolTip())
        self.assertIn(plan_id, self.manager.report_text(task.id))

    def test_legacy_task_explains_missing_audit_id(self) -> None:
        task = self.manager.record_result(
            "Eski görev",
            "Tamamlandı",
            success=True,
            category="Test",
        )

        self.page.show_task(task.id)

        self.assertIn("Denetim kimliği: —", self.page.meta.text())
        self.assertIn("eski görev", self.page.meta.toolTip().casefold())


if __name__ == "__main__":
    unittest.main()
