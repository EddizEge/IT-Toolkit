from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app_v2.pages.tasks import TaskCenterPage
from app_v2.services.action_safety import build_undo_plan
from app_v2.services.audit_log import AuditLog
from app_v2.services.task_manager import TaskManager


class TaskCenterPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.root = root
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

    def test_available_undo_emits_only_selected_task_id(self) -> None:
        task = self.manager.record_result(
            "Zamanlanmış kapatma",
            "Tamamlandı",
            success=True,
            category="Test",
            plan_id="b2" * 16,
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
            restore_point_status="created",
        )
        requested: list[str] = []
        self.page.undo_requested.connect(requested.append)

        self.page.show_task(task.id)

        self.assertTrue(self.page.undo_button.isEnabled())
        self.page.undo_button.click()
        self.assertEqual(requested, [task.id])
        self.assertFalse(self.page.undo_button.isEnabled())

    def test_undo_button_fails_closed_when_selected_state_changes(self) -> None:
        task = self.manager.record_result(
            "Zamanlanmış kapatma",
            "Tamamlandı",
            success=True,
            category="Test",
            plan_id="c3" * 16,
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
        )
        requested: list[str] = []
        self.page.undo_requested.connect(requested.append)
        self.page.show_task(task.id)
        self.assertTrue(self.page.undo_button.isEnabled())

        task.undo_state = "running"
        self.manager.task_updated.emit(task)

        self.assertFalse(self.page.undo_button.isEnabled())
        self.page.undo_button.click()
        self.assertEqual(requested, [])

    def test_recovery_metadata_and_exported_report_are_safe(self) -> None:
        parent_plan_id = "d4" * 16
        child_plan_id = "e5" * 16
        parent = self.manager.record_result(
            "Zamanlanmış kapatma",
            "Tamamlandı",
            success=True,
            category="Test",
            plan_id=parent_plan_id,
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
            restore_point_status="created",
        )
        plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent_plan_id,
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        plan = replace(plan, plan_id=child_plan_id)
        with (
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=True,
            ),
            patch(
                "app_v2.services.task_manager.undo_process",
                return_value=(
                    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                    ("-EncodedCommand", "fixed"),
                ),
            ),
            patch.object(self.manager, "_start_program_task"),
        ):
            child = self.manager.start_undo(plan)
        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            0,
            QProcess.ExitStatus.NormalExit,
        )

        self.page.show_task(parent.id)
        parent_meta = self.page.meta.text()
        self.assertIn(
            "Geri yükleme noktası durumu: Oluşturuldu",
            parent_meta,
        )
        self.assertIn("Geri alma durumu: Tamamlandı", parent_meta)

        self.page.show_task(child.id)

        meta = self.page.meta.text()
        self.assertIn("Geri yükleme noktası durumu: Uygulanmıyor", meta)
        self.assertIn("Geri alma durumu: Sunulmuyor", meta)
        self.assertIn(parent_plan_id[:12], meta)
        self.assertNotIn(parent_plan_id, meta)
        self.assertIn(parent_plan_id, self.page.meta.toolTip())

        report_path = self.root / "task-report.txt"
        with (
            patch.object(
                QFileDialog,
                "getSaveFileName",
                return_value=(str(report_path), "Metin Raporu (*.txt)"),
            ),
            patch.object(QMessageBox, "information"),
        ):
            self.page._export_report()

        report = report_path.read_text(encoding="utf-8-sig")
        self.assertIn(
            "Geri yükleme noktası durumu: Uygulanmıyor",
            report,
        )
        self.assertIn("Geri alma durumu: Sunulmuyor", report)
        self.assertIn(f"Üst işlem kimliği: {parent_plan_id}", report)
        self.assertNotIn("Komut:", report)
        self.assertNotIn("Hedef:", report)


if __name__ == "__main__":
    unittest.main()
