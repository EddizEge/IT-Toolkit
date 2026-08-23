from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QDialog

from app_v2.pages.data import DataPage
from app_v2.pages.programs import ProgramsPage
from app_v2.pages.quick import QuickPage
from app_v2.registry import ACTION_LOOKUP, BASIC_PACKAGES
from app_v2.services.audit_log import AuditLog
from app_v2.services.preferences import ToolPreferences


class ExecutionPlanIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.preferences = ToolPreferences(
            path=Path(self.temp_dir.name) / "preferences.json"
        )
        self.task_manager = Mock()
        self.audit_log = AuditLog(
            Path(self.temp_dir.name) / "audit" / "operations.jsonl"
        )
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
        self.temp_dir.cleanup()

    def _data_page(self) -> DataPage:
        with patch(
            "app_v2.pages.tools_page.get_toggle_status",
            return_value=(False, "Kapalı"),
        ):
            page = DataPage(
                task_manager=self.task_manager,
                preferences=self.preferences,
            )
        self.widgets.append(page)
        return page

    def test_cancelled_picker_creates_no_confirmation_task_or_recent(self) -> None:
        page = self._data_page()
        action = ACTION_LOOKUP["take_ownership"][1]

        with (
            patch(
                "app_v2.pages.data.QFileDialog.getExistingDirectory",
                return_value="",
            ),
            patch(
                "app_v2.pages.tools_page.confirm_operation"
            ) as confirmation,
        ):
            page.execute_action(action)

        confirmation.assert_not_called()
        self.task_manager.start_command.assert_not_called()
        self.assertEqual(self.preferences.recents, ())
        self.assertEqual(self.audit_log.read_events(), ())

    def test_ownership_confirmation_contains_resolved_folder(self) -> None:
        page = self._data_page()
        action = ACTION_LOOKUP["take_ownership"][1]
        target = r"C:\Musteri\Arsiv"

        with (
            patch(
                "app_v2.pages.data.QFileDialog.getExistingDirectory",
                return_value=target,
            ),
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=False,
            ) as confirmation,
        ):
            page.execute_action(action)

        impact = confirmation.call_args.args[1]
        self.assertEqual(impact.target, target)
        self.assertEqual(impact.confirmation_stages, 2)
        self.task_manager.start_command.assert_not_called()
        self.assertEqual(self.preferences.recents, ())
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["prepared", "cancelled"],
        )
        raw = self.audit_log.path.read_text(encoding="utf-8")
        self.assertNotIn(target, raw)

    def test_wipe_confirmation_contains_resolved_drive(self) -> None:
        page = self._data_page()
        action = ACTION_LOOKUP["wipe_free_space"][1]

        with (
            patch(
                "app_v2.pages.data.QFileDialog.getExistingDirectory",
                return_value=r"D:\Musteri",
            ),
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=False,
            ) as confirmation,
        ):
            page.execute_action(action)

        self.assertEqual(
            confirmation.call_args.args[1].target,
            "D:\\ sürücüsünün boş alanı",
        )
        self.assertEqual(
            confirmation.call_args.args[1].confirmation_stages,
            2,
        )
        self.task_manager.start_command.assert_not_called()

    def test_shutdown_duration_is_selected_before_confirmation(self) -> None:
        page = QuickPage(
            task_manager=self.task_manager,
            preferences=self.preferences,
        )
        self.widgets.append(page)
        action = ACTION_LOOKUP["shutdown_schedule"][1]

        with (
            patch(
                "app_v2.pages.quick.QInputDialog.getInt",
                return_value=(30, True),
            ),
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=False,
            ) as confirmation,
        ):
            page.execute_action(action)

        self.assertIn("30 dakika", confirmation.call_args.args[1].target)
        self.task_manager.start_command.assert_not_called()

    def test_selected_winget_packages_require_resolved_admin_review(self) -> None:
        page = ProgramsPage(
            task_manager=self.task_manager,
            preferences=self.preferences,
        )
        self.widgets.append(page)
        action = ACTION_LOOKUP["basic_installer"][1]
        package = next(item for item in BASIC_PACKAGES if item.source == "winget")
        url_package = next(item for item in BASIC_PACKAGES if item.source == "url")

        with (
            patch("app_v2.pages.programs.InstallerDialog") as dialog_type,
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=False,
            ) as confirmation,
            patch(
                "app_v2.pages.tools_page.QDesktopServices.openUrl"
            ) as open_url,
        ):
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog_type.return_value.selected_packages.return_value = [
                package,
                url_package,
            ]
            page.execute_action(action)

        impact = confirmation.call_args.args[1]
        self.assertTrue(impact.admin_required)
        self.assertEqual(impact.confirmation_stages, 1)
        self.assertIn(package.name, impact.target)
        self.assertIn(url_package.name, impact.target)
        self.task_manager.start_command.assert_not_called()
        open_url.assert_not_called()
        self.assertEqual(self.preferences.recents, ())

    def test_accepted_winget_plan_starts_once_with_admin(self) -> None:
        page = ProgramsPage(
            task_manager=self.task_manager,
            preferences=self.preferences,
        )
        self.widgets.append(page)
        action = ACTION_LOOKUP["basic_installer"][1]
        package = next(item for item in BASIC_PACKAGES if item.source == "winget")

        with (
            patch("app_v2.pages.programs.InstallerDialog") as dialog_type,
            patch(
                "app_v2.pages.tools_page.confirm_operation",
                return_value=True,
            ),
        ):
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog_type.return_value.selected_packages.return_value = [package]
            page.execute_action(action)

        self.task_manager.start_command.assert_called_once()
        call = self.task_manager.start_command.call_args
        self.assertTrue(call.kwargs["admin"])
        self.assertIn(package.package_id, call.args[1])
        self.assertEqual(self.preferences.recents, (action.key,))
        events = self.audit_log.read_events(limit=10)
        self.assertEqual(
            [item["event"] for item in events],
            ["prepared", "approved"],
        )
        self.assertEqual(call.kwargs["plan_id"], events[-1]["plan_id"])
        self.assertNotIn(
            package.package_id,
            self.audit_log.path.read_text(encoding="utf-8"),
        )

    def test_page_subclasses_cannot_bypass_the_plan_gate(self) -> None:
        pages_dir = Path(__file__).parents[1] / "app_v2" / "pages"
        allowed_direct_callers = {"tools_page.py", "quick_access.py"}
        offenders: list[str] = []

        for source_path in pages_dir.glob("*.py"):
            if source_path.name in allowed_direct_callers:
                continue
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"start_action", "start_command"}
                ):
                    offenders.append(f"{source_path.name}:{node.lineno}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
