from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

from app_v2.action_confirmation import (
    CriticalConfirmationDialog,
    ImpactReviewDialog,
    confirm_operation,
)
from app_v2.registry import ACTION_LOOKUP
from app_v2.services.action_safety import impact_for_action


class ActionConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.parent = QWidget()
        self.critical_impact = impact_for_action(ACTION_LOOKUP["rdp"][1])

    def tearDown(self) -> None:
        self.parent.close()
        self.app.processEvents()

    def test_review_dialog_keeps_cancel_as_default(self) -> None:
        dialog = ImpactReviewDialog(self.critical_impact, self.parent)
        buttons = {
            button.text(): button
            for button in dialog.findChildren(QPushButton)
        }

        self.assertTrue(buttons["Vazgeç"].isDefault())
        self.assertFalse(buttons["Son onaya devam et"].autoDefault())
        dialog.close()

    def test_critical_start_requires_written_confirmation(self) -> None:
        dialog = CriticalConfirmationDialog(self.critical_impact, self.parent)

        self.assertFalse(dialog.start_button.isEnabled())
        dialog.confirmation_input.setText("yanlış")
        self.assertFalse(dialog.start_button.isEnabled())
        dialog.confirmation_input.setText(" onayla ")
        self.assertTrue(dialog.start_button.isEnabled())
        dialog.confirmation_input.clear()
        self.assertFalse(dialog.start_button.isEnabled())
        dialog.close()

    def test_danger_policy_runs_both_dialog_stages(self) -> None:
        with (
            patch(
                "app_v2.action_confirmation.ImpactReviewDialog"
            ) as review_dialog,
            patch(
                "app_v2.action_confirmation.CriticalConfirmationDialog"
            ) as critical_dialog,
        ):
            review_dialog.return_value.exec.return_value = (
                QDialog.DialogCode.Accepted
            )
            critical_dialog.return_value.exec.return_value = (
                QDialog.DialogCode.Accepted
            )

            accepted = confirm_operation(self.parent, self.critical_impact)

        self.assertTrue(accepted)
        review_dialog.assert_called_once()
        critical_dialog.assert_called_once()

    def test_rejected_review_never_opens_critical_stage(self) -> None:
        with (
            patch(
                "app_v2.action_confirmation.ImpactReviewDialog"
            ) as review_dialog,
            patch(
                "app_v2.action_confirmation.CriticalConfirmationDialog"
            ) as critical_dialog,
        ):
            review_dialog.return_value.exec.return_value = (
                QDialog.DialogCode.Rejected
            )

            accepted = confirm_operation(self.parent, self.critical_impact)

        self.assertFalse(accepted)
        critical_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
