from __future__ import annotations

import base64
import ntpath
import re
import unittest
from unittest.mock import patch

from app_v2.services import recovery
from app_v2.services.recovery import (
    ELEVATED_RESULT_MISSING_EXIT_CODE,
    ELEVATION_FAILED_EXIT_CODE,
    INITIAL_QUERY_FAILED_EXIT_CODE,
    restore_point_process,
)


def _decode_script(arguments: tuple[str, ...]) -> str:
    index = arguments.index("-EncodedCommand")
    encoded = arguments[index + 1]
    return base64.b64decode(encoded).decode("utf-16-le")


def _inner_command_from_wrapper(wrapper: str) -> str:
    match = re.search(r"\$innerCommand='([A-Za-z0-9+/=]+)'", wrapper)
    if not match:
        raise AssertionError("Yükseltme sarmalayıcısında iç komut bulunamadı.")
    return match.group(1)


class RestorePointServiceTests(unittest.TestCase):
    def test_admin_process_verifies_new_exact_restore_point(self) -> None:
        program, arguments = restore_point_process(
            "a" * 32,
            "rdp",
            elevated=False,
        )

        self.assertTrue(ntpath.isabs(program))
        self.assertTrue(
            program.lower().endswith(
                r"\system32\windowspowershell\v1.0\powershell.exe"
            )
        )
        self.assertNotEqual(program.lower(), "powershell.exe")
        self.assertNotIn("-ExecutionPolicy", arguments)
        script = _decode_script(arguments)
        self.assertIn("Get-ComputerRestorePoint", script)
        self.assertIn("Checkpoint-Computer", script)
        self.assertIn(
            "[long]$point.SequenceNumber -gt $beforeSequence",
            script,
        )
        self.assertIn("$point.Description -ceq $description", script)
        self.assertIn("[DateTime]::UtcNow.AddSeconds(30)", script)
        self.assertIn("[System.Threading.Thread]::Sleep(500)", script)
        self.assertIn("exit 0", script)
        self.assertIn("exit 21", script)
        self.assertIn(
            f"catch {{ exit {INITIAL_QUERY_FAILED_EXIT_CODE} }}",
            script,
        )

    def test_old_matching_point_cannot_be_a_false_positive(self) -> None:
        _, arguments = restore_point_process(
            "b" * 32,
            "toggle:smb1:on",
            elevated=False,
        )

        script = _decode_script(arguments)
        before_index = script.index("$beforeSequence=[long]-1")
        checkpoint_index = script.index(
            "Microsoft.PowerShell.Management\\Checkpoint-Computer "
            "-Description"
        )
        verification_index = script.index(
            "[long]$point.SequenceNumber -gt $beforeSequence"
        )
        self.assertLess(before_index, checkpoint_index)
        self.assertLess(checkpoint_index, verification_index)
        self.assertIn("$point.Description -ceq $description", script)

    def test_restore_cmdlets_load_only_from_trusted_pshome_module(self) -> None:
        _, arguments = restore_point_process(
            "3" * 32,
            "rdp",
            elevated=False,
        )

        script = _decode_script(arguments)
        self.assertIn("$PSModuleAutoLoadingPreference='None'", script)
        self.assertIn("$env:PSModulePath=$trustedModuleRoot", script)
        self.assertIn(
            "Microsoft.PowerShell.Management.psd1",
            script,
        )
        self.assertIn(
            "Microsoft.PowerShell.Core\\Import-Module -Name "
            "$managementManifest",
            script,
        )
        self.assertIn(
            "Microsoft.PowerShell.Management\\Get-ComputerRestorePoint",
            script,
        )
        self.assertIn(
            "Microsoft.PowerShell.Management\\Checkpoint-Computer",
            script,
        )
        self.assertIn("Loaded module path mismatch", script)

    def test_standard_process_waits_and_returns_elevated_exit_code(self) -> None:
        program, arguments = restore_point_process(
            "c" * 32,
            "rdp",
            elevated=True,
        )

        self.assertTrue(ntpath.isabs(program))
        wrapper = _decode_script(arguments)
        for fragment in (
            "$processInfo.FileName='" + program.replace("'", "''") + "'",
            "$processInfo.UseShellExecute=$true",
            "$processInfo.Verb='runas'",
            "[System.Diagnostics.ProcessWindowStyle]::Hidden",
            "$process.WaitForExit()",
            "exit ([int]$process.ExitCode)",
        ):
            self.assertIn(fragment, wrapper)
        self.assertIn(
            f"catch {{ exit {ELEVATION_FAILED_EXIT_CODE} }}",
            wrapper,
        )
        self.assertIn(
            f"exit {ELEVATED_RESULT_MISSING_EXIT_CODE}",
            wrapper,
        )
        self.assertNotIn("Start-Process", wrapper)

    def test_program_path_uses_only_resolved_system_directory(self) -> None:
        system_directory = r"D:\TrustedWindows\System32"
        with patch.object(
            recovery,
            "_get_system_directory_windows",
            return_value=system_directory,
        ) as resolver:
            program, _ = restore_point_process(
                "7" * 32,
                "rdp",
                elevated=False,
            )

        resolver.assert_called_once_with()
        self.assertEqual(
            program,
            (
                r"D:\TrustedWindows\System32\WindowsPowerShell"
                r"\v1.0\powershell.exe"
            ),
        )

    def test_elevation_wrapper_safely_quotes_absolute_program_path(self) -> None:
        system_directory = r"C:\Win'dows\System32"
        with patch.object(
            recovery,
            "_get_system_directory_windows",
            return_value=system_directory,
        ):
            program, arguments = restore_point_process(
                "6" * 32,
                "rdp",
                elevated=True,
            )

        wrapper = _decode_script(arguments)
        self.assertEqual(
            program,
            r"C:\Win'dows\System32\WindowsPowerShell\v1.0\powershell.exe",
        )
        self.assertIn(
            (
                "$processInfo.FileName="
                r"'C:\Win''dows\System32\WindowsPowerShell"
                r"\v1.0\powershell.exe'"
            ),
            wrapper,
        )

    def test_non_windows_environment_fails_closed_without_fallback(self) -> None:
        with patch.object(
            recovery.os,
            "name",
            "posix",
        ), self.assertRaisesRegex(OSError, "yalnız Windows"):
            restore_point_process(
                "5" * 32,
                "rdp",
                elevated=False,
            )

    def test_relative_system_directory_is_rejected(self) -> None:
        with patch.object(
            recovery,
            "_get_system_directory_windows",
            return_value=r"relative\System32",
        ), self.assertRaisesRegex(OSError, "mutlak yerel yol"):
            restore_point_process(
                "4" * 32,
                "rdp",
                elevated=False,
            )

    def test_standard_wrapper_contains_the_same_fixed_inner_script(self) -> None:
        plan_id = "d" * 32
        _, admin_arguments = restore_point_process(
            plan_id,
            "rdp",
            elevated=False,
        )
        _, standard_arguments = restore_point_process(
            plan_id,
            "rdp",
            elevated=True,
        )

        wrapper = _decode_script(standard_arguments)
        inner_command = _inner_command_from_wrapper(wrapper)
        self.assertEqual(
            inner_command,
            admin_arguments[admin_arguments.index("-EncodedCommand") + 1],
        )
        inner_script = base64.b64decode(inner_command).decode("utf-16-le")
        self.assertIn("Checkpoint-Computer", inner_script)

    def test_description_is_unique_and_contains_no_action_or_user_data(self) -> None:
        _, first_arguments = restore_point_process(
            "1" * 32,
            "rdp",
            elevated=False,
        )
        _, second_arguments = restore_point_process(
            "2" * 32,
            "toggle:smb1:on",
            elevated=False,
        )

        first = _decode_script(first_arguments)
        second = _decode_script(second_arguments)
        self.assertIn("IT Toolkit Restore " + "1" * 32, first)
        self.assertIn("IT Toolkit Restore " + "2" * 32, second)
        self.assertNotEqual(first, second)
        for forbidden in (
            "rdp",
            "toggle:smb1:on",
            r"C:\Users\PrivateUser",
            "Müşteri klasörü",
            "S-1-5-21",
        ):
            self.assertNotIn(forbidden, first)
            self.assertNotIn(forbidden, second)

    def test_script_does_not_change_system_restore_policy(self) -> None:
        _, arguments = restore_point_process(
            "e" * 32,
            "rdp",
            elevated=False,
        )

        script = _decode_script(arguments)
        self.assertNotIn("SystemRestorePointCreationFrequency", script)
        self.assertNotIn("Enable-ComputerRestore", script)
        self.assertNotIn("Set-ItemProperty", script)

    def test_invalid_plan_ids_are_rejected(self) -> None:
        invalid_values = (
            "a" * 31,
            "a" * 33,
            "A" * 32,
            "not-a-plan-id",
            "0" * 31 + "-",
            123,
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                restore_point_process(  # type: ignore[arg-type]
                    value,
                    "rdp",
                    elevated=False,
                )

    def test_unknown_or_injectable_action_keys_are_rejected(self) -> None:
        invalid_values = (
            "safe_but_not_allowlisted",
            "rdp; Remove-Item C:\\",
            "toggle:smb1:on ",
            "",
            123,
            None,
        )

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                restore_point_process(  # type: ignore[arg-type]
                    "f" * 32,
                    value,
                    elevated=False,
                )

    def test_raw_target_or_title_parameters_are_not_accepted(self) -> None:
        with self.assertRaises(TypeError):
            restore_point_process(
                "9" * 32,
                "rdp",
                elevated=False,
                target=r"C:\Users\PrivateUser",  # type: ignore[call-arg]
            )
        with self.assertRaises(TypeError):
            restore_point_process(
                "9" * 32,
                "rdp",
                elevated=False,
                title="Müşteri işlemi",  # type: ignore[call-arg]
            )

    def test_elevated_must_be_boolean(self) -> None:
        with self.assertRaises(TypeError):
            restore_point_process(
                "8" * 32,
                "rdp",
                elevated=1,  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
