from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from app_v2.presets import TECHNICIAN_PRESETS
from app_v2.registry import (
    ACTION_LOOKUP,
    DATA_TOGGLES,
    NETWORK_TOGGLES,
    PAGE_ACTIONS,
    SYSTEM_TOGGLES,
    ToolAction,
)
from app_v2.services.action_safety import (
    VALID_RISKS,
    OperationImpact,
    confirmation_stage_count,
    execution_plan_for_action,
    execution_plan_for_preset,
    execution_plan_for_toggle,
    impact_for_action,
    impact_for_preset,
    impact_for_toggle,
)


class ActionSafetyTests(unittest.TestCase):
    def test_normal_read_only_action_needs_no_confirmation(self) -> None:
        action = ToolAction(
            "read_only",
            "Salt okunur test",
            "Yalnızca bilgi toplar.",
            "Test",
            "echo test",
        )

        impact = impact_for_action(action)

        self.assertEqual(impact.confirmation_stages, 0)
        self.assertFalse(impact.admin_required)

    def test_normal_admin_action_gets_impact_review(self) -> None:
        action = ACTION_LOOKUP["sfc"][1]

        impact = impact_for_action(action)

        self.assertEqual(action.risk, "normal")
        self.assertEqual(impact.confirmation_stages, 1)
        self.assertTrue(impact.admin_required)

    def test_resolved_plan_uses_runtime_target_and_admin_requirement(self) -> None:
        action = ACTION_LOOKUP["basic_installer"][1]

        plan = execution_plan_for_action(
            action,
            command="winget install --id 7zip.7zip",
            target="7-Zip",
            admin_required=True,
        )

        self.assertEqual(plan.impact.target, "7-Zip")
        self.assertTrue(plan.impact.admin_required)
        self.assertEqual(plan.impact.confirmation_stages, 1)

    def test_empty_execution_plan_is_rejected(self) -> None:
        action = ACTION_LOOKUP["basic_installer"][1]

        with self.assertRaises(ValueError):
            execution_plan_for_action(action, command="")

    def test_execution_plan_is_immutable(self) -> None:
        action = ACTION_LOOKUP["sfc"][1]
        plan = execution_plan_for_action(action)

        with self.assertRaises(FrozenInstanceError):
            plan.title = "Başka başlık"  # type: ignore[misc]

    def test_registered_admin_requirement_cannot_be_downgraded(self) -> None:
        action = ACTION_LOOKUP["sfc"][1]

        with self.assertRaises(ValueError):
            execution_plan_for_action(action, admin_required=False)

    def test_danger_action_requires_two_stages_and_explicit_recovery(self) -> None:
        action = ACTION_LOOKUP["firewall_reset"][1]

        impact = impact_for_action(action, target="Windows Güvenlik Duvarı")

        self.assertEqual(impact.confirmation_stages, 2)
        self.assertEqual(impact.risk_label, "KRİTİK")
        self.assertEqual(impact.target, "Windows Güvenlik Duvarı")
        self.assertIn("dışa aktarılmış", impact.rollback)

    def test_danger_toggle_is_direction_sensitive(self) -> None:
        smb1 = next(toggle for toggle in NETWORK_TOGGLES if toggle.key == "smb1")

        enabling = impact_for_toggle(smb1, True)
        disabling = impact_for_toggle(smb1, False)

        self.assertEqual(enabling.confirmation_stages, 2)
        self.assertEqual(enabling.risk, "danger")
        self.assertEqual(disabling.confirmation_stages, 1)
        self.assertEqual(disabling.risk, "caution")

    def test_caution_preset_uses_same_policy(self) -> None:
        preset = next(
            item for item in TECHNICIAN_PRESETS if item.key == "network_repair"
        )

        impact = impact_for_preset(preset)

        self.assertEqual(impact.confirmation_stages, 1)
        self.assertTrue(impact.admin_required)

    def test_toggle_and_preset_plans_get_correlation_ids(self) -> None:
        smb1 = next(toggle for toggle in NETWORK_TOGGLES if toggle.key == "smb1")
        preset = next(
            item for item in TECHNICIAN_PRESETS if item.key == "network_repair"
        )

        toggle_plan = execution_plan_for_toggle(smb1, True)
        preset_plan = execution_plan_for_preset(preset)

        self.assertRegex(toggle_plan.plan_id, r"^[0-9a-f]{32}$")
        self.assertEqual(toggle_plan.action_key, "toggle:smb1:on")
        self.assertTrue(toggle_plan.admin_required)
        self.assertRegex(preset_plan.plan_id, r"^[0-9a-f]{32}$")
        self.assertEqual(preset_plan.action_key, "preset:network_repair")

    def test_unknown_risk_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            confirmation_stage_count("critical", admin_required=True)

    def test_inconsistent_operation_impact_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OperationImpact(
                key="unsafe",
                title="Tutarsız işlem",
                risk="danger",
                risk_label="KRİTİK",
                effect="Sistem değişecek.",
                target="Test hedefi",
                admin_required=True,
                interruption="Kesinti olabilir.",
                rollback="Geri alma yok.",
                confirmation_stages=0,
            )

    def test_registry_safety_metadata_is_complete(self) -> None:
        actions = [
            action
            for page_actions in PAGE_ACTIONS.values()
            for action in page_actions
        ]
        toggles = SYSTEM_TOGGLES + NETWORK_TOGGLES + DATA_TOGGLES

        for action in actions:
            self.assertIn(action.risk, VALID_RISKS, action.key)
            if action.risk == "danger":
                self.assertTrue(action.impact.strip(), action.key)
                self.assertTrue(action.interruption.strip(), action.key)
                self.assertTrue(action.rollback.strip(), action.key)
        for toggle in toggles:
            self.assertIn(toggle.risk, VALID_RISKS, toggle.key)
            if toggle.risk_on:
                self.assertIn(toggle.risk_on, VALID_RISKS, toggle.key)
            if toggle.risk_off:
                self.assertIn(toggle.risk_off, VALID_RISKS, toggle.key)
            if toggle.risk == "danger":
                self.assertTrue(toggle.risk_on.strip(), toggle.key)
                self.assertTrue(toggle.risk_off.strip(), toggle.key)
                self.assertTrue(toggle.impact_on.strip(), toggle.key)
                self.assertTrue(toggle.impact_off.strip(), toggle.key)
                self.assertTrue(toggle.interruption.strip(), toggle.key)
                self.assertTrue(toggle.rollback.strip(), toggle.key)
        for preset in TECHNICIAN_PRESETS:
            self.assertIn(preset.risk, VALID_RISKS, preset.key)
            if preset.risk == "danger":
                self.assertTrue(preset.impact.strip(), preset.key)
                self.assertTrue(preset.interruption.strip(), preset.key)
                self.assertTrue(preset.rollback.strip(), preset.key)


if __name__ == "__main__":
    unittest.main()
