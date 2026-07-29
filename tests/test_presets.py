from __future__ import annotations

import unittest

from app_v2.presets import PRESET_LOOKUP, TECHNICIAN_PRESETS


class TechnicianPresetTests(unittest.TestCase):
    def test_preset_keys_are_unique(self) -> None:
        keys = [preset.key for preset in TECHNICIAN_PRESETS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), set(PRESET_LOOKUP))

    def test_only_network_repair_requires_admin(self) -> None:
        admin_presets = [
            preset.key for preset in TECHNICIAN_PRESETS if preset.admin
        ]
        self.assertEqual(admin_presets, ["network_repair"])
        self.assertEqual(PRESET_LOOKUP["network_repair"].risk, "caution")

    def test_presets_have_commands_and_turkish_descriptions(self) -> None:
        for preset in TECHNICIAN_PRESETS:
            self.assertTrue(preset.command.strip())
            self.assertGreater(len(preset.description), 20)


if __name__ == "__main__":
    unittest.main()
