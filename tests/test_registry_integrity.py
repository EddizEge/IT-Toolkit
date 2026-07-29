from __future__ import annotations

import unittest

from app_v2.registry import (
    ACTION_LOOKUP,
    BASIC_PACKAGES,
    DRIVER_PACKAGES,
    PAGE_ACTIONS,
)


class RegistryIntegrityTests(unittest.TestCase):
    def test_every_action_has_a_command_or_handler(self) -> None:
        for actions in PAGE_ACTIONS.values():
            for action in actions:
                self.assertTrue(
                    action.command.strip() or action.handler,
                    action.key,
                )

    def test_repaired_powershell_actions_use_encoded_commands(self) -> None:
        for key in ("smart", "ip_scan", "minidump", "debloat", "office_license"):
            command = ACTION_LOOKUP[key][1].command
            self.assertIn("-EncodedCommand", command, key)

    def test_current_winget_ids_replace_retired_ids(self) -> None:
        package_ids = {
            item.package_id
            for item in BASIC_PACKAGES + DRIVER_PACKAGES
            if item.source == "winget"
        }
        self.assertIn("AnyDesk.AnyDesk", package_ids)
        self.assertIn("Google.GoogleDrive", package_ids)
        self.assertIn("XP8CLZL93F5Z4P", package_ids)
        self.assertIn("9WZDNCRFHWLH", package_ids)
        self.assertNotIn("AnyDeskSoftwareGmbH.AnyDesk", package_ids)
        self.assertNotIn("Google.Drive", package_ids)
        self.assertNotIn("Nvidia.NVIDIAapp", package_ids)
        self.assertNotIn("9WZDNCRFHWL0", package_ids)

    def test_unavailable_packages_use_official_pages(self) -> None:
        url_packages = {
            item.name: item.package_id
            for item in BASIC_PACKAGES
            if item.source == "url"
        }
        self.assertEqual(url_packages["RustDesk resmi indirme sayfası"], "https://rustdesk.com/")
        self.assertIn(
            "filezilla-project.org",
            url_packages["FileZilla resmi indirme sayfası"],
        )

    def test_netstat_no_longer_requires_elevation(self) -> None:
        self.assertFalse(ACTION_LOOKUP["netstat"][1].admin)


if __name__ == "__main__":
    unittest.main()
