from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from app_v2.services import command_runner
from app_v2.services.undo_execution import (
    PRECONDITION_MISMATCH_EXIT_CODE,
    PRECONDITION_QUERY_FAILED_EXIT_CODE,
    SMB_PRECONDITION_TIMEOUT_MS,
    protected_action_process,
    undo_process,
)


def _decode(arguments: tuple[str, ...]) -> str:
    index = arguments.index("-EncodedCommand")
    return base64.b64decode(arguments[index + 1]).decode("utf-16-le")


class UndoExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system32 = r"D:\TrustedWindows\System32"
        self.resolver = patch.object(
            command_runner,
            "_get_system_directory_windows",
            return_value=self.system32,
        )
        self.resolver.start()
        self.addCleanup(self.resolver.stop)

    def test_all_allowed_pairs_compile_without_temporary_script(self) -> None:
        pairs = (
            ("toggle:windows_update:on", "toggle:windows_update:off"),
            ("toggle:windows_update:off", "toggle:windows_update:on"),
            ("toggle:hibernation:on", "toggle:hibernation:off"),
            ("toggle:hibernation:off", "toggle:hibernation:on"),
            ("toggle:smb1:on", "toggle:smb1:off"),
            ("toggle:smb1:off", "toggle:smb1:on"),
            (
                "toggle:usb_write_protect:on",
                "toggle:usb_write_protect:off",
            ),
            (
                "toggle:usb_write_protect:off",
                "toggle:usb_write_protect:on",
            ),
            ("shutdown_schedule", "shutdown_cancel"),
        )

        for action_key, undo_key in pairs:
            with self.subTest(action_key=action_key, undo_key=undo_key):
                program, arguments = undo_process(
                    action_key,
                    undo_key,
                    elevated=False,
                )
                script = _decode(arguments)

                self.assertEqual(
                    program,
                    (
                        self.system32
                        + r"\WindowsPowerShell\v1.0\powershell.exe"
                    ),
                )
                self.assertNotIn(".cmd", script.casefold())
                self.assertNotIn("%temp%", script.casefold())
                self.assertTrue(script.endswith("exit 0"))

    def test_native_tools_are_absolute_system32_paths(self) -> None:
        expected_tools = {
            ("toggle:windows_update:off", "toggle:windows_update:on"): (
                "sc.exe",
                "net.exe",
                "reg.exe",
            ),
            ("toggle:hibernation:on", "toggle:hibernation:off"): (
                "powercfg.exe",
            ),
            ("toggle:smb1:on", "toggle:smb1:off"): ("dism.exe",),
            (
                "toggle:usb_write_protect:on",
                "toggle:usb_write_protect:off",
            ): ("reg.exe",),
            ("shutdown_schedule", "shutdown_cancel"): ("shutdown.exe",),
        }

        for pair, executable_names in expected_tools.items():
            with self.subTest(pair=pair):
                _program, arguments = undo_process(
                    *pair,
                    elevated=False,
                )
                script = _decode(arguments)
                for name in executable_names:
                    self.assertIn(
                        f"'{self.system32}\\{name}'",
                        script,
                    )

    def test_windows_update_preserves_first_nonzero_exit_code(self) -> None:
        _program, arguments = undo_process(
            "toggle:windows_update:off",
            "toggle:windows_update:on",
            elevated=False,
        )
        script = _decode(arguments)

        self.assertEqual(script.count("$stepExit=[int]$LASTEXITCODE"), 3)
        self.assertEqual(
            script.count("if ($stepExit -ne 0) { exit $stepExit }"),
            3,
        )
        self.assertLess(script.index("sc.exe"), script.index("net.exe"))
        self.assertLess(script.index("net.exe"), script.index("reg.exe"))

    def test_toggle_undo_rechecks_state_before_first_mutation(self) -> None:
        pairs_and_mutations = (
            (
                ("toggle:windows_update:on", "toggle:windows_update:off"),
                f"& '{self.system32}\\net.exe'",
            ),
            (
                ("toggle:windows_update:off", "toggle:windows_update:on"),
                f"& '{self.system32}\\sc.exe'",
            ),
            (
                ("toggle:hibernation:on", "toggle:hibernation:off"),
                f"& '{self.system32}\\powercfg.exe'",
            ),
            (
                ("toggle:hibernation:off", "toggle:hibernation:on"),
                f"& '{self.system32}\\powercfg.exe'",
            ),
            (
                ("toggle:smb1:on", "toggle:smb1:off"),
                f"& '{self.system32}\\dism.exe'",
            ),
            (
                ("toggle:smb1:off", "toggle:smb1:on"),
                f"& '{self.system32}\\dism.exe'",
            ),
            (
                (
                    "toggle:usb_write_protect:on",
                    "toggle:usb_write_protect:off",
                ),
                f"& '{self.system32}\\reg.exe'",
            ),
            (
                (
                    "toggle:usb_write_protect:off",
                    "toggle:usb_write_protect:on",
                ),
                f"& '{self.system32}\\reg.exe'",
            ),
        )

        for pair, first_mutation in pairs_and_mutations:
            with self.subTest(pair=pair):
                _program, arguments = undo_process(
                    *pair,
                    elevated=False,
                )
                script = _decode(arguments)
                mismatch_exit = f"exit {PRECONDITION_MISMATCH_EXIT_CODE}"
                query_exit = f"exit {PRECONDITION_QUERY_FAILED_EXIT_CODE}"
                self.assertIn(mismatch_exit, script)
                self.assertIn(query_exit, script)
                self.assertLess(script.index(mismatch_exit), script.index(first_mutation))
                self.assertLess(script.index(query_exit), script.index(first_mutation))

    def test_toggle_on_and_off_preconditions_are_directional(self) -> None:
        cases = (
            (
                "windows_update",
                ("toggle:windows_update:on", "toggle:windows_update:off"),
                ("toggle:windows_update:off", "toggle:windows_update:on"),
            ),
            (
                "hibernation",
                ("toggle:hibernation:on", "toggle:hibernation:off"),
                ("toggle:hibernation:off", "toggle:hibernation:on"),
            ),
            (
                "smb1",
                ("toggle:smb1:on", "toggle:smb1:off"),
                ("toggle:smb1:off", "toggle:smb1:on"),
            ),
            (
                "usb_write_protect",
                (
                    "toggle:usb_write_protect:on",
                    "toggle:usb_write_protect:off",
                ),
                (
                    "toggle:usb_write_protect:off",
                    "toggle:usb_write_protect:on",
                ),
            ),
        )

        for name, parent_on, parent_off in cases:
            with self.subTest(toggle=name):
                _program, on_arguments = undo_process(*parent_on, elevated=False)
                _program, off_arguments = undo_process(*parent_off, elevated=False)
                self.assertNotEqual(_decode(on_arguments), _decode(off_arguments))

    def test_shutdown_cancel_relies_on_atomic_native_result(self) -> None:
        _program, arguments = undo_process(
            "shutdown_schedule",
            "shutdown_cancel",
            elevated=False,
        )
        script = _decode(arguments)

        self.assertNotIn(f"exit {PRECONDITION_QUERY_FAILED_EXIT_CODE}", script)
        self.assertNotIn(f"exit {PRECONDITION_MISMATCH_EXIT_CODE}", script)
        self.assertIn(f"& '{self.system32}\\shutdown.exe'", script)

    def test_smb_undo_is_fixed_encoded_powershell(self) -> None:
        _program, arguments = undo_process(
            "toggle:smb1:on",
            "toggle:smb1:off",
            elevated=False,
        )
        script = _decode(arguments)

        self.assertIn(f"'{self.system32}\\dism.exe'", script)
        self.assertIn("'/Disable-Feature'", script)
        self.assertIn("'/FeatureName:SMB1Protocol'", script)
        self.assertIn("'/NoRestart'", script)
        self.assertIn("$stepExit -ne 3010", script)
        self.assertIn("$PSModuleAutoLoadingPreference='None'", script)
        self.assertNotIn("Import-Module", script)
        self.assertNotIn("cmd.exe", script.casefold())

    def test_smb_precondition_has_bounded_async_query_and_cleanup(self) -> None:
        _program, arguments = undo_process(
            "toggle:smb1:on",
            "toggle:smb1:off",
            elevated=False,
        )
        script = _decode(arguments)
        mutation = f"& '{self.system32}\\dism.exe'"

        self.assertIn("StandardOutput.ReadToEndAsync()", script)
        self.assertIn(f"WaitForExit({SMB_PRECONDITION_TIMEOUT_MS})", script)
        self.assertIn("$preconditionProcess.Kill()", script)
        self.assertIn("$preconditionProcess.Dispose()", script)
        self.assertNotIn("StandardOutput.ReadToEnd()", script)
        self.assertLess(script.index("WaitForExit("), script.index(mutation))

    def test_registry_preconditions_require_dword_and_exact_missing_state(self) -> None:
        missing_pairs = (
            ("toggle:windows_update:on", "toggle:windows_update:off"),
            (
                "toggle:usb_write_protect:off",
                "toggle:usb_write_protect:on",
            ),
        )

        for pair in missing_pairs:
            with self.subTest(pair=pair):
                _program, arguments = undo_process(*pair, elevated=False)
                script = _decode(arguments)
                self.assertIn("$preconditionMatches=$true", script)
                self.assertIn("$preconditionMatches=$false", script)

        value_pairs = (
            (
            "toggle:windows_update:off",
            "toggle:windows_update:on",
            ),
            (
                "toggle:usb_write_protect:on",
                "toggle:usb_write_protect:off",
            ),
        )

        for pair in value_pairs:
            with self.subTest(pair=pair):
                _program, arguments = undo_process(*pair, elevated=False)
                script = _decode(arguments)
                self.assertIn("RegistryValueKind]::DWord", script)
                self.assertIn("$preconditionMatches=$false", script)
                self.assertNotIn("$preconditionMatches=$true", script)

    def test_elevated_wrapper_uses_same_trusted_powershell_and_real_exit(self) -> None:
        program, arguments = undo_process(
            "toggle:hibernation:on",
            "toggle:hibernation:off",
            elevated=True,
        )
        outer_script = _decode(arguments)

        self.assertIn(f"$processInfo.FileName='{program}'", outer_script)
        self.assertIn("$processInfo.Verb='runas'", outer_script)
        self.assertIn("$process.WaitForExit()", outer_script)
        self.assertIn("exit ([int]$process.ExitCode)", outer_script)
        self.assertNotIn("Start-Process", outer_script)
        self.assertNotIn(".cmd", outer_script.casefold())

    def test_unknown_mismatched_and_injectable_pairs_are_rejected(self) -> None:
        invalid_pairs = (
            ("toggle:hibernation:on", "toggle:hibernation:on"),
            ("toggle:hibernation:on", "toggle:smb1:off"),
            ("undo:toggle:hibernation:on", "toggle:hibernation:off"),
            ("shutdown_schedule", "shutdown_cancel & calc.exe"),
            ("unknown", "shutdown_cancel"),
        )

        for action_key, undo_key in invalid_pairs:
            with (
                self.subTest(action_key=action_key, undo_key=undo_key),
                self.assertRaises(ValueError),
            ):
                undo_process(action_key, undo_key, elevated=False)

    def test_non_string_keys_and_non_boolean_elevation_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            undo_process(1, "shutdown_cancel", elevated=False)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            undo_process("shutdown_schedule", None, elevated=False)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            undo_process(
                "shutdown_schedule",
                "shutdown_cancel",
                elevated=1,  # type: ignore[arg-type]
            )

    def test_resolver_failure_stops_before_process_is_returned(self) -> None:
        with (
            patch.object(
                command_runner,
                "_get_system_directory_windows",
                side_effect=OSError("System32 çözülemedi"),
            ),
            self.assertRaises(OSError),
        ):
            undo_process(
                "shutdown_schedule",
                "shutdown_cancel",
                elevated=False,
            )

    def test_rdp_protected_action_uses_only_absolute_native_tools(self) -> None:
        program, arguments = protected_action_process(
            "rdp",
            elevated=False,
        )
        script = _decode(arguments)

        self.assertTrue(program.startswith(self.system32))
        self.assertIn(f"'{self.system32}\\reg.exe'", script)
        self.assertIn(f"'{self.system32}\\netsh.exe'", script)
        self.assertIn("'fDenyTSConnections'", script)
        self.assertIn("'group=@FirewallAPI.dll,-28752'", script)
        self.assertEqual(script.count("$stepExit=[int]$LASTEXITCODE"), 2)
        self.assertNotIn(".cmd", script.casefold())

    def test_smb_protected_action_uses_absolute_dism(self) -> None:
        _program, arguments = protected_action_process(
            "toggle:smb1:on",
            elevated=True,
        )
        wrapper = _decode(arguments)
        inner_command = wrapper.split("$innerCommand='", 1)[1].split("'", 1)[0]
        inner_script = base64.b64decode(inner_command).decode("utf-16-le")

        self.assertIn(f"'{self.system32}\\dism.exe'", inner_script)
        self.assertIn("'/Enable-Feature'", inner_script)
        self.assertIn("'/All'", inner_script)
        self.assertNotIn("Start-Process", wrapper)

    def test_unknown_protected_action_is_rejected(self) -> None:
        for action_key in ("sfc", "rdp & calc.exe", "", 1):
            with (
                self.subTest(action_key=action_key),
                self.assertRaises((TypeError, ValueError)),
            ):
                protected_action_process(
                    action_key,  # type: ignore[arg-type]
                    elevated=False,
                )


if __name__ == "__main__":
    unittest.main()
