from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from app_v2.registry import ACTION_LOOKUP, TOGGLE_LOOKUP, ToggleAction
from app_v2.services.action_safety import (
    UNDOABLE_TOGGLE_KEYS,
    build_undo_plan,
    execution_plan_for_action,
    execution_plan_for_toggle,
    impact_for_toggle,
)
from app_v2.services.audit_log import AuditLog
from app_v2.services.task_manager import TaskManager
from app_v2.services.undo_execution import PRECONDITION_MISMATCH_EXIT_CODE


class RecoveryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.history_path = self.root / "history.json"
        self.script_directory = self.root / "task-scripts"
        self.audit_log = AuditLog(
            self.root / "audit" / "operations.jsonl"
        )
        self.manager = TaskManager(
            history_path=self.history_path,
            script_directory=self.script_directory,
            audit_log=self.audit_log,
        )
        self._plan_sequence = 0

    def tearDown(self) -> None:
        self.manager.shutdown()
        self.app.processEvents()
        self.temporary.cleanup()

    def _plan_id(self) -> str:
        self._plan_sequence += 1
        return f"{self._plan_sequence:032x}"

    def _successful_parent(
        self,
        *,
        action_key: str = "toggle:hibernation:on",
        undo_key: str = "toggle:hibernation:off",
    ):
        task = self.manager.record_result(
            "Doğrulanmış üst işlem",
            "Üst işlem başarıyla tamamlandı.",
            success=True,
            category="Test",
            plan_id=self._plan_id(),
            action_key=action_key,
            risk="caution",
            admin=True,
            undo_key=undo_key,
        )
        self.assertEqual(task.undo_state, "available")
        return task

    def _start_mocked_undo(self, parent):
        plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        command_program = (
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        )
        arguments = ("-NoProfile", "-EncodedCommand", "fixed")
        with (
            patch(
                "app_v2.services.task_manager.get_toggle_status",
                return_value=(True, "Açık"),
            ),
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=True,
            ),
            patch(
                "app_v2.services.task_manager.undo_process",
                return_value=(command_program, arguments),
            ) as process_builder,
            patch(
                "app_v2.services.task_manager.create_command_script"
            ) as create_script,
            patch.object(self.manager, "_start_program_task") as start,
        ):
            task = self.manager.start_undo(plan)
        start.assert_called_once()
        process_builder.assert_called_once_with(
            parent.action_key,
            parent.undo_key,
            elevated=False,
        )
        create_script.assert_not_called()
        self.assertEqual(start.call_args.args[1], command_program)
        self.assertEqual(start.call_args.args[2], arguments)
        return task, plan

    def test_toggle_undo_requires_allowlist_and_known_previous_state(self) -> None:
        available_keys: set[str] = set()
        for key, toggle in TOGGLE_LOOKUP.items():
            with self.subTest(key=key):
                known = impact_for_toggle(
                    toggle,
                    True,
                    previous_enabled=False,
                )
                unknown = impact_for_toggle(
                    toggle,
                    True,
                    previous_enabled=None,
                )
                if known.recovery.undo_mode == "available":
                    available_keys.add(key)
                    self.assertEqual(
                        known.recovery.undo_key,
                        f"toggle:{key}:off",
                    )
                self.assertNotEqual(unknown.recovery.undo_mode, "available")
                self.assertEqual(unknown.recovery.undo_key, "")

        self.assertEqual(available_keys, set(UNDOABLE_TOGGLE_KEYS))

        unlisted = ToggleAction(
            "test_unlisted",
            "Liste dışı ayar",
            "Yalnız test için kullanılan sentetik ayar.",
            "echo on",
            "echo off",
        )
        impact = impact_for_toggle(
            unlisted,
            True,
            previous_enabled=False,
        )
        self.assertEqual(impact.recovery.undo_mode, "not_applicable")
        self.assertEqual(impact.recovery.undo_key, "")

    def test_toggle_no_op_plan_is_rejected(self) -> None:
        toggle = TOGGLE_LOOKUP["hibernation"]

        for enabled in (False, True):
            with self.subTest(enabled=enabled), self.assertRaises(ValueError):
                execution_plan_for_toggle(
                    toggle,
                    enabled,
                    previous_enabled=enabled,
                )

    def test_build_undo_plan_creates_fresh_child_bound_to_parent(self) -> None:
        parent_plan_id = "a" * 32
        first = build_undo_plan(
            action_key="toggle:hibernation:on",
            undo_key="toggle:hibernation:off",
            parent_plan_id=parent_plan_id,
        )
        second = build_undo_plan(
            action_key="toggle:hibernation:on",
            undo_key="toggle:hibernation:off",
            parent_plan_id=parent_plan_id,
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        assert first is not None and second is not None
        self.assertNotEqual(first.plan_id, second.plan_id)
        self.assertNotEqual(first.plan_id, parent_plan_id)
        self.assertEqual(first.parent_plan_id, parent_plan_id)
        self.assertEqual(first.action_key, "undo:toggle:hibernation:on")
        self.assertEqual(
            first.command,
            TOGGLE_LOOKUP["hibernation"].command_off,
        )
        self.assertEqual(first.impact.recovery.undo_mode, "unavailable")

    def test_build_undo_plan_rejects_non_allowlisted_or_mismatched_keys(self) -> None:
        parent_plan_id = "b" * 32

        invalid_pairs = (
            ("toggle:test_unlisted:on", "toggle:test_unlisted:off"),
            ("toggle:hibernation:on", "toggle:hibernation:on"),
            ("rdp", "shutdown_cancel"),
            ("unknown_action", "shutdown_cancel"),
        )
        for action_key, undo_key in invalid_pairs:
            with self.subTest(action_key=action_key, undo_key=undo_key):
                self.assertIsNone(
                    build_undo_plan(
                        action_key=action_key,
                        undo_key=undo_key,
                        parent_plan_id=parent_plan_id,
                    )
                )

        shutdown = build_undo_plan(
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
            parent_plan_id=parent_plan_id,
        )
        self.assertIsNotNone(shutdown)
        assert shutdown is not None
        self.assertEqual(shutdown.parent_plan_id, parent_plan_id)
        self.assertEqual(shutdown.command.casefold(), "shutdown -a")

    def test_successful_parent_and_child_follow_single_use_state_machine(
        self,
    ) -> None:
        parent = self._successful_parent()
        child, _plan = self._start_mocked_undo(parent)

        self.assertEqual(parent.undo_state, "running")
        self.assertEqual(child.status, "queued")

        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            0,
            QProcess.ExitStatus.NormalExit,
        )

        self.assertEqual(child.status, "succeeded")
        self.assertEqual(parent.undo_state, "completed")

    def test_elevated_undo_waits_for_a_verified_child_result(self) -> None:
        parent = self._successful_parent()
        plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(plan)
        assert plan is not None

        with (
            patch(
                "app_v2.services.task_manager.get_toggle_status",
                return_value=(True, "Açık"),
            ),
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=False,
            ),
            patch(
                "app_v2.services.task_manager.undo_process",
                return_value=(
                    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                    ("-EncodedCommand", "wrapper"),
                ),
            ) as process_builder,
            patch.object(self.manager, "_start_program_task") as start,
        ):
            child = self.manager.start_undo(plan)

        process_builder.assert_called_once_with(
            parent.action_key,
            parent.undo_key,
            elevated=True,
        )
        start.assert_called_once()
        self.assertEqual(child.status, "queued")
        self.assertFalse(child.cancellable)
        self.assertEqual(parent.undo_state, "running")

        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            0,
            QProcess.ExitStatus.NormalExit,
        )

        self.assertEqual(child.status, "succeeded")
        self.assertEqual(parent.undo_state, "completed")

    def test_started_failed_undo_never_marks_parent_completed(self) -> None:
        parent = self._successful_parent()
        child, _plan = self._start_mocked_undo(parent)

        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            7,
            QProcess.ExitStatus.NormalExit,
        )

        self.assertEqual(child.status, "failed")
        self.assertEqual(child.exit_code, 7)
        self.assertEqual(parent.undo_state, "unknown")
        self.assertNotEqual(parent.undo_state, "completed")

    def test_interrupted_undo_never_marks_parent_completed(self) -> None:
        parent = self._successful_parent()
        child, _plan = self._start_mocked_undo(parent)

        self.manager._on_started(child.id)
        child.status = "interrupted"
        child.finished_at = "2026-08-24T12:00:00+03:00"
        child.message = "Test oturumu kesildi."
        child.exit_code = None
        self.manager._cleanup_process(child.id)
        self.manager._commit_terminal(child)

        self.assertEqual(parent.undo_state, "unknown")
        self.assertNotEqual(parent.undo_state, "completed")

    def test_started_crashed_undo_becomes_unknown(self) -> None:
        parent = self._successful_parent()
        child, _plan = self._start_mocked_undo(parent)
        self.manager._on_started(child.id)
        process = MagicMock()
        process.state.return_value = QProcess.ProcessState.NotRunning
        process.errorString.return_value = "Test çökmesi"
        self.manager._processes[child.id] = process

        self.manager._on_error(
            child.id,
            QProcess.ProcessError.Crashed,
        )

        self.assertEqual(child.status, "failed")
        self.assertIsNone(child.exit_code)
        self.assertEqual(parent.undo_state, "unknown")

    def test_prestart_failure_allows_only_a_fresh_undo_plan(self) -> None:
        parent = self._successful_parent()
        child, used_plan = self._start_mocked_undo(parent)
        process = MagicMock()
        process.state.return_value = QProcess.ProcessState.NotRunning
        process.errorString.return_value = "Başlatılamadı"
        self.manager._processes[child.id] = process

        self.manager._on_error(
            child.id,
            QProcess.ProcessError.FailedToStart,
        )

        self.assertEqual(parent.undo_state, "available")
        with self.assertRaisesRegex(ValueError, "daha önce"):
            self.manager.start_undo(used_plan)

        fresh_plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(fresh_plan)
        assert fresh_plan is not None
        self.assertNotEqual(fresh_plan.plan_id, used_plan.plan_id)

    def test_second_undo_is_rejected_while_first_is_reserved(self) -> None:
        parent = self._successful_parent()
        first_child, first_plan = self._start_mocked_undo(parent)
        second_plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(second_plan)
        assert second_plan is not None

        with self.assertRaises(ValueError):
            self.manager.start_undo(second_plan)

        self.assertEqual(first_child.plan_id, first_plan.plan_id)
        self.assertEqual(parent.undo_state, "running")

    def test_generic_task_apis_reject_parent_bound_results(self) -> None:
        parent = self._successful_parent(
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
        )
        plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(plan)
        assert plan is not None

        with self.assertRaises(ValueError):
            self.manager.start_command(
                plan.title,
                plan.command,
                category=plan.category,
                admin=plan.admin_required,
                plan_id=plan.plan_id,
                action_key=plan.action_key,
                risk=plan.impact.risk,
                parent_plan_id=plan.parent_plan_id,
            )
        with self.assertRaises(ValueError):
            self.manager.record_result(
                plan.title,
                "Sahte sonuç",
                success=True,
                category=plan.category,
                plan_id=plan.plan_id,
                action_key=plan.action_key,
                risk=plan.impact.risk,
                parent_plan_id=plan.parent_plan_id,
            )

        self.assertEqual(parent.undo_state, "available")

    def test_undo_rejects_forged_action_and_modified_command(self) -> None:
        parent = self._successful_parent(
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
        )
        plan = build_undo_plan(
            action_key=parent.action_key,
            undo_key=parent.undo_key,
            parent_plan_id=parent.plan_id,
        )
        self.assertIsNotNone(plan)
        assert plan is not None

        for forged in (
            replace(plan, action_key="undo:toggle:smb1:on"),
            replace(plan, command="echo should-not-run"),
        ):
            with self.subTest(action_key=forged.action_key), self.assertRaises(
                ValueError
            ):
                self.manager.start_undo(forged)

        self.assertEqual(parent.undo_state, "available")

    def test_rdp_uses_dedicated_fileless_protected_process(self) -> None:
        plan = execution_plan_for_action(ACTION_LOOKUP["rdp"][1])
        program = (
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        )
        arguments = ("-EncodedCommand", "protected")
        with (
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=False,
            ),
            patch(
                "app_v2.services.task_manager.protected_action_process",
                return_value=(program, arguments),
            ) as process_builder,
            patch(
                "app_v2.services.task_manager.create_command_script"
            ) as create_script,
            patch.object(self.manager, "_start_program_task") as start,
        ):
            task = self.manager.start_protected_action(
                plan,
                restore_point_status="skipped",
            )

        process_builder.assert_called_once_with("rdp", elevated=True)
        create_script.assert_not_called()
        self.assertEqual(start.call_args.args[1], program)
        self.assertEqual(start.call_args.args[2], arguments)
        self.assertFalse(task.cancellable)
        self.assertEqual(task.command, plan.command)
        self.assertEqual(task.restore_point_status, "skipped")

    def test_protected_action_rejects_modified_plan_before_process(self) -> None:
        plan = execution_plan_for_action(ACTION_LOOKUP["rdp"][1])
        forged = replace(plan, command="echo should-not-run")

        with (
            patch(
                "app_v2.services.task_manager.protected_action_process"
            ) as process_builder,
            self.assertRaisesRegex(ValueError, "merkezi güvenli kayıt"),
        ):
            self.manager.start_protected_action(
                forged,
                restore_point_status="skipped",
            )

        process_builder.assert_not_called()

    def test_generic_apis_reject_protected_action_keys(self) -> None:
        for action_key in ("rdp", "toggle:smb1:on", "toggle:smb1:off"):
            with (
                self.subTest(action_key=action_key),
                self.assertRaisesRegex(ValueError, "Korumalı eylem"),
            ):
                self.manager.start_command(
                    "Korumalı eylem",
                    "echo should-not-run",
                    plan_id=self._plan_id(),
                    action_key=action_key,
                    risk="danger",
                )
            with (
                self.subTest(action_key=f"record:{action_key}"),
                self.assertRaisesRegex(ValueError, "Korumalı eylem"),
            ):
                self.manager.record_result(
                    "Sahte sonuç",
                    "Kaydedilmemeli",
                    success=True,
                    plan_id=self._plan_id(),
                    action_key=action_key,
                    risk="danger",
                )

    def test_execution_time_precondition_failure_marks_parent_unknown(self) -> None:
        parent = self._successful_parent()
        child, _plan = self._start_mocked_undo(parent)
        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            PRECONDITION_MISMATCH_EXIT_CODE,
            QProcess.ExitStatus.NormalExit,
        )

        self.assertEqual(child.status, "failed")
        self.assertIn("ayar durumu değişti", child.message)
        self.assertEqual(parent.undo_state, "unknown")

    def test_completed_undo_remains_single_use_after_restart(self) -> None:
        parent = self._successful_parent(
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
        )
        child, plan = self._start_mocked_undo(parent)
        self.manager._on_started(child.id)
        self.manager._on_finished(
            child.id,
            0,
            QProcess.ExitStatus.NormalExit,
        )
        self.assertEqual(child.status, "succeeded")
        self.assertEqual(parent.undo_state, "completed")

        restored = TaskManager(
            history_path=self.history_path,
            script_directory=self.script_directory,
            audit_log=self.audit_log,
        )
        try:
            restored_parent = restored.task(parent.id)
            self.assertIsNotNone(restored_parent)
            assert restored_parent is not None
            self.assertEqual(restored_parent.undo_state, "completed")
            with self.assertRaises(ValueError):
                restored.start_undo(replace(plan, plan_id="f" * 32))
        finally:
            restored.shutdown()

    def test_corrupt_recovery_metadata_is_stripped_and_cannot_be_reserved(
        self,
    ) -> None:
        history_path = self.root / "corrupt-history.json"
        audit_log = AuditLog(self.root / "corrupt-audit" / "operations.jsonl")
        parent_plan_id = "e" * 32
        history_path.write_text(
            json.dumps(
                [
                    {
                        "id": "c" * 32,
                        "title": "Bozuk kurtarma kaydı",
                        "command": "",
                        "category": "Test",
                        "status": "succeeded",
                        "created_at": "2026-08-24T12:00:00+03:00",
                        "plan_id": parent_plan_id,
                        "parent_plan_id": "f" * 32,
                        "action_key": "shutdown_schedule",
                        "risk": "caution",
                        "undo_key": "shutdown_cancel.extra",
                        "undo_state": "completed",
                        "restore_point_status": "tampered",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        restored = TaskManager(
            history_path=history_path,
            script_directory=self.root / "corrupt-scripts",
            audit_log=audit_log,
        )
        try:
            task = restored.tasks[0]
            self.assertEqual(task.parent_plan_id, "")
            self.assertEqual(task.undo_key, "")
            self.assertEqual(task.undo_state, "none")
            self.assertEqual(task.restore_point_status, "not_applicable")

            with self.assertRaises(ValueError):
                restored.start_command(
                    "Sahte geri alma",
                    "echo should-not-run",
                    plan_id="d" * 32,
                    action_key="undo:shutdown_schedule",
                    risk="caution",
                    parent_plan_id=parent_plan_id,
                )
        finally:
            restored.shutdown()

    def test_duplicate_root_plan_ids_are_quarantined(self) -> None:
        history_path = self.root / "duplicate-history.json"
        duplicate_plan_id = "7" * 32
        records = []
        for index, task_id in enumerate(("1" * 32, "2" * 32), start=1):
            records.append(
                {
                    "id": task_id,
                    "title": f"Yinelenen üst işlem {index}",
                    "command": "shutdown /s /t 600",
                    "category": "Test",
                    "status": "succeeded",
                    "created_at": "2026-08-24T12:00:00+03:00",
                    "finished_at": "2026-08-24T12:00:01+03:00",
                    "plan_id": duplicate_plan_id,
                    "action_key": "shutdown_schedule",
                    "risk": "caution",
                    "undo_key": "shutdown_cancel",
                    "undo_state": "available",
                }
            )
        history_path.write_text(
            json.dumps(records, ensure_ascii=False),
            encoding="utf-8",
        )
        restored = TaskManager(
            history_path=history_path,
            script_directory=self.root / "duplicate-scripts",
            audit_log=AuditLog(
                self.root / "duplicate-audit" / "operations.jsonl"
            ),
        )
        try:
            self.assertEqual(
                [task.undo_state for task in restored.tasks],
                ["unknown", "unknown"],
            )
            plan = build_undo_plan(
                action_key="shutdown_schedule",
                undo_key="shutdown_cancel",
                parent_plan_id=duplicate_plan_id,
            )
            self.assertIsNotNone(plan)
            assert plan is not None
            with self.assertRaisesRegex(ValueError, "üst işlem"):
                restored.start_undo(plan)
        finally:
            restored.shutdown()

    def test_mismatched_child_quarantines_recoverable_parent_after_restart(self) -> None:
        parent = self._successful_parent(
            action_key="shutdown_schedule",
            undo_key="shutdown_cancel",
        )
        records = json.loads(self.history_path.read_text(encoding="utf-8"))
        records.insert(
            0,
            {
                "id": "8" * 32,
                "title": "Değiştirilmiş geri alma",
                "command": "echo should-not-run",
                "category": "Test",
                "status": "failed",
                "created_at": "2026-08-24T12:00:00+03:00",
                "finished_at": "2026-08-24T12:00:01+03:00",
                "plan_id": "9" * 32,
                "parent_plan_id": parent.plan_id,
                "action_key": "undo:shutdown_schedule",
                "risk": "caution",
            },
        )
        for index, undo_state in enumerate(("available", "completed"), start=1):
            with self.subTest(undo_state=undo_state):
                history_path = self.root / f"mismatch-{index}-history.json"
                state_records = [dict(record) for record in records]
                next(
                    record
                    for record in state_records
                    if record["id"] == parent.id
                )["undo_state"] = undo_state
                history_path.write_text(
                    json.dumps(state_records, ensure_ascii=False),
                    encoding="utf-8",
                )
                restored = TaskManager(
                    history_path=history_path,
                    script_directory=self.root / f"mismatch-{index}-scripts",
                    audit_log=AuditLog(
                        self.root / f"mismatch-{index}-audit" / "operations.jsonl"
                    ),
                )
                try:
                    restored_parent = restored.task(parent.id)
                    self.assertIsNotNone(restored_parent)
                    assert restored_parent is not None
                    self.assertEqual(restored_parent.undo_state, "unknown")
                finally:
                    restored.shutdown()

    def test_audit_terminal_result_overrides_conflicting_history(self) -> None:
        for index, audited_status in enumerate(("delegated", "failed"), start=1):
            with self.subTest(audited_status=audited_status):
                history_path = self.root / f"conflict-{index}-history.json"
                audit_log = AuditLog(
                    self.root / f"conflict-{index}-audit" / "operations.jsonl"
                )
                task_id = f"{index + 2:032x}"
                plan_id = f"{index + 12:032x}"
                history_path.write_text(
                    json.dumps(
                        [
                            {
                                "id": task_id,
                                "title": "Çelişkili üst işlem",
                                "command": "",
                                "category": "Test",
                                "status": "succeeded",
                                "created_at": "2026-08-24T12:00:00+03:00",
                                "finished_at": "2026-08-24T12:00:01+03:00",
                                "plan_id": plan_id,
                                "action_key": "shutdown_schedule",
                                "risk": "caution",
                                "admin": True,
                                "undo_key": "shutdown_cancel",
                                "undo_state": "available",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                self.assertTrue(
                    audit_log.record(
                        "result",
                        plan_id=plan_id,
                        action_key="shutdown_schedule",
                        title="Çelişkili üst işlem",
                        category="Test",
                        risk="caution",
                        admin_required=True,
                        task_id=task_id,
                        status=audited_status,
                    )
                )

                restored = TaskManager(
                    history_path=history_path,
                    script_directory=self.root / f"conflict-{index}-scripts",
                    audit_log=audit_log,
                )
                try:
                    task = restored.tasks[0]
                    self.assertEqual(task.status, audited_status)
                    self.assertEqual(task.undo_state, "none")
                    self.assertTrue(task.audit_result_recorded)
                finally:
                    restored.shutdown()

    def test_restore_child_uses_parent_audit_and_only_verified_exit_succeeds(
        self,
    ) -> None:
        parent_plan_id = "9" * 32
        process = MagicMock()
        process.readAllStandardOutput.return_value = b""

        with (
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=True,
            ),
            patch(
                "app_v2.services.task_manager.QProcess",
                return_value=process,
            ) as process_class,
        ):
            child = self.manager.start_restore_point(
                "Uzak Masaüstü",
                parent_plan_id=parent_plan_id,
                parent_action_key="rdp",
                risk="danger",
            )
            process_class.assert_called_once_with(self.manager)
            process.start.assert_called_once()
            self.assertEqual(child.status, "queued")
            self.assertNotEqual(child.plan_id, parent_plan_id)
            self.assertEqual(child.parent_plan_id, parent_plan_id)

            self.manager._on_started(child.id)
            self.manager._on_finished(
                child.id,
                0,
                QProcess.ExitStatus.NormalExit,
            )

        self.assertEqual(child.status, "succeeded")
        self.assertEqual(child.exit_code, 0)
        self.assertEqual(
            child.message,
            "Geri yükleme noktası oluşturuldu ve doğrulandı.",
        )
        events = self.audit_log.read_events(limit=20)
        self.assertEqual(
            [event["event"] for event in events],
            ["prepared", "approved", "started", "result"],
        )
        self.assertTrue(
            all(
                event.get("parent_plan_id") == parent_plan_id
                for event in events
            )
        )
        result = events[-1]
        self.assertEqual(result["plan_id"], child.plan_id)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["exit_code"], 0)
        for event in events:
            self.assertNotIn("command", event)
            self.assertNotIn("output", event)
            self.assertNotIn("target", event)

        raw_audit = self.audit_log.path.read_text(encoding="utf-8").casefold()
        for forbidden in (
            "checkpoint-computer",
            "encodedcommand",
            "powershell.exe",
            "registered:restore_point",
        ):
            self.assertNotIn(forbidden, raw_audit)

    def test_restore_process_crash_with_zero_exit_never_succeeds(self) -> None:
        process = MagicMock()
        process.readAllStandardOutput.return_value = b""

        with (
            patch(
                "app_v2.services.task_manager.is_running_as_admin",
                return_value=True,
            ),
            patch(
                "app_v2.services.task_manager.QProcess",
                return_value=process,
            ),
        ):
            child = self.manager.start_restore_point(
                "Uzak Masaüstü",
                parent_plan_id="6" * 32,
                parent_action_key="rdp",
                risk="danger",
            )
            self.manager._on_started(child.id)
            self.manager._on_finished(
                child.id,
                0,
                QProcess.ExitStatus.CrashExit,
            )

        self.assertEqual(child.status, "failed")
        self.assertIn("beklenmedik", child.message.casefold())
        self.assertIn("henüz başlamadı", child.message.casefold())

    def test_restore_resolver_failure_finishes_without_orphan_task(self) -> None:
        with patch(
            "app_v2.services.task_manager.restore_point_process",
            side_effect=OSError("System32 çözülemedi"),
        ):
            child = self.manager.start_restore_point(
                "Uzak Masaüstü",
                parent_plan_id="5" * 32,
                parent_action_key="rdp",
                risk="danger",
            )
            manual = self.manager.start_manual_restore(
                "Geri yükleme noktası oluştur",
                plan_id="4" * 32,
                action_key="restore",
                risk="danger",
            )

        self.assertEqual(child.status, "failed")
        self.assertIn("henüz başlamadı", child.message.casefold())
        self.assertEqual(manual.status, "failed")
        self.assertEqual(self.manager._active_restore_task_id, "")
        self.assertTrue(child.audit_result_recorded)
        self.assertTrue(manual.audit_result_recorded)

    def test_recovery_override_has_strict_shape_and_parent_link(self) -> None:
        audit_log = AuditLog(
            self.root / "override-audit" / "operations.jsonl",
            personal_values=("MüşteriGizlisi",),
        )
        plan_id = "7" * 32
        parent_plan_id = "8" * 32

        recorded = audit_log.record(
            "recovery_override",
            plan_id=plan_id,
            parent_plan_id=parent_plan_id,
            action_key="restore_point",
            title="MüşteriGizlisi için açık kurtarma onayı",
            category="İşlem güvenliği",
            risk="danger",
            admin_required=True,
            approval_mode="user",
        )

        self.assertTrue(recorded)
        event = audit_log.read_events(limit=1)[0]
        self.assertEqual(event["event"], "recovery_override")
        self.assertEqual(event["parent_plan_id"], parent_plan_id)
        self.assertEqual(event["approval_mode"], "user")
        self.assertEqual(event["task_id"], "")
        self.assertEqual(event["status"], "")
        self.assertIsNone(event["exit_code"])
        self.assertEqual(
            set(event),
            {
                "schema_version",
                "event_id",
                "timestamp",
                "app_version",
                "event",
                "plan_id",
                "parent_plan_id",
                "action_key",
                "title",
                "category",
                "risk",
                "admin_required",
                "approval_mode",
                "task_id",
                "status",
                "exit_code",
            },
        )
        raw = audit_log.path.read_text(encoding="utf-8")
        self.assertNotIn("MüşteriGizlisi", raw)
        for forbidden in ("command", "output", "target", "powershell"):
            self.assertNotIn(forbidden, raw.casefold())

        for invalid in (
            {"approval_mode": "automatic"},
            {"approval_mode": "user", "task_id": "6" * 32},
            {"approval_mode": "user", "status": "running"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                audit_log.record(
                    "recovery_override",
                    plan_id="5" * 32,
                    parent_plan_id="4" * 32,
                    action_key="restore_point",
                    title="Geçersiz şekil",
                    category="İşlem güvenliği",
                    risk="danger",
                    admin_required=True,
                    **invalid,
                )

    def test_safe_mode_on_opens_one_time_advanced_startup(self) -> None:
        _page_key, action = ACTION_LOOKUP["safe_mode_on"]
        command = action.command.casefold().strip()

        self.assertEqual(command, "shutdown /r /o /t 0")
        self.assertNotIn("bcdedit", command)
        self.assertNotIn("safeboot", command)

    def test_shutdown_rejects_new_tasks(self) -> None:
        self.manager.shutdown()

        with self.assertRaises(RuntimeError):
            self.manager.start_command("Geç görev", "echo should-not-run")
        with self.assertRaises(RuntimeError):
            self.manager.start_manual_restore(
                "Geç nokta",
                plan_id="3" * 32,
                action_key="restore",
                risk="danger",
            )


if __name__ == "__main__":
    unittest.main()
