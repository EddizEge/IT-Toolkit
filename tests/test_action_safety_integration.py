from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from app_v2.pages.quick_access import QuickAccessPage
from app_v2.pages.tools_page import ToolsPage
from app_v2.presets import TECHNICIAN_PRESETS
from app_v2.registry import ACTION_LOOKUP, NETWORK_TOGGLES, ToolAction
from app_v2.services.action_safety import execution_plan_for_action
from app_v2.services.audit_log import AuditLog
from app_v2.services.preferences import ToolPreferences


class ActionSafetyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.audit_log = AuditLog(
            Path(self.temporary.name) / "audit" / "operations.jsonl"
        )
        self.task_manager = Mock()
        self.task_manager.audit_log = self.audit_log
        self.task_manager.start_command.return_value = SimpleNamespace(
            status="queued",
            message="",
        )
        self.widgets = []

    def tearDown(self) -> None:
        for widget in self.widgets:
            widget.close()
        self.app.processEvents()
        self.temporary.cleanup()

    def _tools_page(
        self,
        action_key: str,
        preferences: ToolPreferences | None = None,
    ) -> ToolsPage:
        action = ACTION_LOOKUP[action_key][1]
        page = ToolsPage(
            "Test",
            "Güvenlik entegrasyonu",
            (action,),
            task_manager=self.task_manager,
            preferences=preferences,
        )
        self.widgets.append(page)
        return page

    def test_cancelled_action_never_reaches_task_manager(self) -> None:
        action = ACTION_LOOKUP["sfc"][1]
        with tempfile.TemporaryDirectory() as temp_dir:
            preferences = ToolPreferences(
                path=Path(temp_dir) / "preferences.json"
            )
            page = self._tools_page(action.key, preferences)

            with patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=False,
            ) as confirmation:
                page.execute_action(action)

        confirmation.assert_called_once()
        self.assertTrue(confirmation.call_args.args[1].admin_required)
        self.task_manager.start_command.assert_not_called()
        self.assertEqual(preferences.recents, ())
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["prepared", "cancelled"],
        )
        self.assertEqual(len({item["plan_id"] for item in events}), 1)

    def test_accepted_action_starts_only_after_central_confirmation(self) -> None:
        action = ACTION_LOOKUP["rdp"][1]
        page = self._tools_page(action.key)

        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=True,
        ) as confirmation:
            page.execute_action(action)

        self.assertEqual(
            confirmation.call_args.args[1].confirmation_stages,
            2,
        )
        self.task_manager.start_command.assert_called_once()
        self.assertTrue(
            self.task_manager.start_command.call_args.kwargs["admin"]
        )
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["prepared", "approved"],
        )
        self.assertEqual(events[-1]["approval_mode"], "user")
        self.assertEqual(
            self.task_manager.start_command.call_args.kwargs["plan_id"],
            events[-1]["plan_id"],
        )

    def test_cancelled_toggle_never_starts_command(self) -> None:
        smb1 = next(
            toggle for toggle in NETWORK_TOGGLES if toggle.key == "smb1"
        )
        page = self._tools_page("sfc")

        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=False,
        ) as confirmation:
            page._change_toggle(smb1, True)

        self.assertEqual(confirmation.call_args.args[1].risk, "danger")
        self.task_manager.start_command.assert_not_called()
        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["prepared", "cancelled"],
        )

    def test_cancelled_preset_never_starts_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            preferences = ToolPreferences(
                path=Path(temp_dir) / "preferences.json"
            )
            page = QuickAccessPage(preferences, self.task_manager)
            self.widgets.append(page)
            preset = next(
                item
                for item in TECHNICIAN_PRESETS
                if item.key == "network_repair"
            )

            with patch(
                "app_v2.pages.quick_access.confirm_operation",
                return_value=False,
            ) as confirmation:
                page._run_preset(preset)

        self.assertEqual(
            confirmation.call_args.args[1].confirmation_stages,
            1,
        )
        self.task_manager.start_command.assert_not_called()
        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["prepared", "cancelled"],
        )

    def test_risky_action_fails_closed_when_audit_cannot_be_written(self) -> None:
        blocker = Path(self.temporary.name) / "audit-blocker"
        blocker.write_text("dosya", encoding="utf-8")
        self.task_manager.audit_log = AuditLog(
            blocker / "operations.jsonl"
        )
        action = ACTION_LOOKUP["sfc"][1]
        page = self._tools_page(action.key)
        statuses: list[tuple[str, bool]] = []
        page.status_message.connect(
            lambda message, ok: statuses.append((message, ok))
        )

        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=True,
        ) as confirmation:
            page.execute_action(action)

        confirmation.assert_not_called()
        self.task_manager.start_command.assert_not_called()
        self.assertTrue(statuses)
        self.assertFalse(statuses[-1][1])
        self.assertIn("denetim günlüğüne", statuses[-1][0])

    def test_risky_action_fails_closed_without_audit_service(self) -> None:
        self.task_manager.audit_log = None
        action = ACTION_LOOKUP["sfc"][1]
        page = self._tools_page(action.key)

        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=True,
        ) as confirmation:
            page.execute_action(action)

        confirmation.assert_not_called()
        self.task_manager.start_command.assert_not_called()

    def test_mixed_plan_attempts_urls_before_delegated_result(self) -> None:
        action = ToolAction(
            "mixed_plan",
            "Karma plan",
            "Komut ve resmî bağlantı içerir.",
            "Test",
            "echo test",
            admin=True,
            keep_open=False,
            risk="caution",
        )
        page = ToolsPage(
            "Test",
            "Karma plan sırası",
            (action,),
            task_manager=self.task_manager,
        )
        self.widgets.append(page)
        plan = execution_plan_for_action(
            action,
            urls=("https://example.test/official",),
        )
        order: list[str] = []

        def open_url(_url: object) -> bool:
            order.append("url")
            self.assertEqual(
                [
                    item["event"]
                    for item in self.audit_log.read_events(limit=10)
                ],
                ["prepared", "approved"],
            )
            return True

        def start_command(*_args: object, **_kwargs: object) -> SimpleNamespace:
            order.append("task")
            for event in ("delegated", "result"):
                self.audit_log.record_plan(
                    event,
                    plan,
                    task_id="b" * 32,
                    status="delegated",
                )
            return SimpleNamespace(status="delegated", message="Devredildi")

        self.task_manager.start_command.side_effect = start_command
        with (
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=True,
            ),
            patch(
                "app_v2.pages.tools_page.QDesktopServices.openUrl",
                side_effect=open_url,
            ),
        ):
            page._execute_plan(plan)

        self.assertEqual(order, ["url", "task"])
        self.assertEqual(
            [
                item["event"]
                for item in self.audit_log.read_events(limit=10)
            ],
            ["prepared", "approved", "delegated", "result"],
        )

    def test_risky_ui_handler_is_rejected_without_callback(self) -> None:
        action = ToolAction(
            "ui_test",
            "Riskli arayüz işlemi",
            "Test işlemi.",
            "Test",
            "",
            admin=True,
            risk="caution",
            handler="ui_test",
        )
        handler = Mock(return_value=True)
        page = ToolsPage(
            "Test",
            "Arayüz güvenlik entegrasyonu",
            (action,),
            ui_handlers={"ui_test": handler},
            task_manager=self.task_manager,
        )
        self.widgets.append(page)

        with patch(
            "app_v2.pages.tools_page.confirm_operation",
            return_value=False,
        ) as confirmation:
            page.execute_action(action)

        confirmation.assert_not_called()
        handler.assert_not_called()
        self.task_manager.start_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
