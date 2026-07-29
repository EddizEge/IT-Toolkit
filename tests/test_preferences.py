from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app_v2.services.preferences import RECENT_LIMIT, ToolPreferences


class ToolPreferencesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "preferences.json"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_favorites_persist_and_keep_order(self) -> None:
        preferences = ToolPreferences(path=self.path)
        self.assertTrue(preferences.toggle_favorite("sfc"))
        self.assertTrue(preferences.toggle_favorite("smart"))
        preferences.move_favorite("smart", -1)

        restored = ToolPreferences(path=self.path)
        self.assertEqual(restored.favorites, ("smart", "sfc"))

    def test_toggle_removes_favorite(self) -> None:
        preferences = ToolPreferences(path=self.path)
        preferences.toggle_favorite("sfc")
        self.assertFalse(preferences.toggle_favorite("sfc"))
        self.assertEqual(preferences.favorites, ())

    def test_recents_are_unique_and_bounded(self) -> None:
        preferences = ToolPreferences(path=self.path)
        valid_keys = [
            "sfc",
            "smart",
            "battery",
            "gpupdate",
            "network_reset",
            "ip_mac",
            "netstat",
            "ping",
            "device_manager",
            "regedit",
            "services",
            "event_viewer",
            "computer_management",
        ]
        for action_key in valid_keys:
            preferences.record_recent(action_key)
        preferences.record_recent("sfc")

        self.assertEqual(len(preferences.recents), RECENT_LIMIT)
        self.assertEqual(preferences.recents[0], "sfc")
        self.assertEqual(len(set(preferences.recents)), RECENT_LIMIT)

    def test_invalid_and_corrupt_values_are_ignored(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "favorites": ["sfc", "missing", "sfc", 42],
                    "recents": "not-a-list",
                }
            ),
            encoding="utf-8",
        )
        preferences = ToolPreferences(path=self.path)
        self.assertEqual(preferences.favorites, ("sfc",))
        self.assertEqual(preferences.recents, ())

        self.path.write_text("{broken", encoding="utf-8")
        corrupt = ToolPreferences(path=self.path)
        self.assertEqual(corrupt.favorites, ())


if __name__ == "__main__":
    unittest.main()
