from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app_v2.services import command_runner
from app_v2.services.command_builder import aggregate_sequence
from app_v2.services.command_runner import (
    create_command_script,
    run_command,
    trusted_system_executable,
    trusted_windows_powershell,
)


class CommandRunnerTests(unittest.TestCase):
    def test_self_deleting_script_preserves_failure_from_subroutine(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            script = create_command_script(
                aggregate_sequence(
                    (
                        "cmd /d /c exit 9",
                        "echo SONRAKI_ADIM_CALISTI",
                    )
                ),
                directory=Path(root) / "boşluklu görev dizini",
                self_delete=True,
            )

            result = subprocess.run(
                [
                    trusted_system_executable("cmd.exe"),
                    "/d",
                    "/c",
                    str(script),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("SONRAKI_ADIM_CALISTI", result.stdout)
            self.assertFalse(script.exists())

    def test_trusted_executables_use_only_absolute_system32_path(self) -> None:
        with patch.object(
            command_runner,
            "_get_system_directory_windows",
            return_value=r"D:\TrustedWindows\System32",
        ) as resolver:
            command = trusted_system_executable("CMD.EXE")
            dism = trusted_system_executable("dism.exe")
            netsh = trusted_system_executable("netsh.exe")
            taskkill = trusted_system_executable("taskkill.exe")
            sc = trusted_system_executable("sc.exe")
            net = trusted_system_executable("net.exe")
            reg = trusted_system_executable("reg.exe")
            powercfg = trusted_system_executable("powercfg.exe")
            shutdown = trusted_system_executable("shutdown.exe")
            powershell = trusted_windows_powershell()

        self.assertEqual(command, r"D:\TrustedWindows\System32\cmd.exe")
        self.assertEqual(dism, r"D:\TrustedWindows\System32\dism.exe")
        self.assertEqual(netsh, r"D:\TrustedWindows\System32\netsh.exe")
        self.assertEqual(
            taskkill,
            r"D:\TrustedWindows\System32\taskkill.exe",
        )
        self.assertEqual(sc, r"D:\TrustedWindows\System32\sc.exe")
        self.assertEqual(net, r"D:\TrustedWindows\System32\net.exe")
        self.assertEqual(reg, r"D:\TrustedWindows\System32\reg.exe")
        self.assertEqual(
            powercfg,
            r"D:\TrustedWindows\System32\powercfg.exe",
        )
        self.assertEqual(
            shutdown,
            r"D:\TrustedWindows\System32\shutdown.exe",
        )
        self.assertEqual(
            powershell,
            (
                r"D:\TrustedWindows\System32\WindowsPowerShell"
                r"\v1.0\powershell.exe"
            ),
        )
        self.assertEqual(resolver.call_count, 10)

    def test_relative_or_non_system_directory_is_rejected(self) -> None:
        for system_directory in (
            r"relative\System32",
            r"C:\Windows\Temp",
            r"\\server\share\System32",
        ):
            with (
                self.subTest(system_directory=system_directory),
                patch.object(
                    command_runner,
                    "_get_system_directory_windows",
                    return_value=system_directory,
                ),
                self.assertRaisesRegex(OSError, "System32"),
            ):
                trusted_system_executable("cmd.exe")

    def test_unknown_or_injectable_executable_is_rejected(self) -> None:
        for executable_name in (
            "powershell.exe",
            r"..\cmd.exe",
            r"C:\Windows\System32\cmd.exe",
            "cmd.exe & calc.exe",
        ):
            with (
                self.subTest(executable_name=executable_name),
                self.assertRaises(ValueError),
            ):
                trusted_system_executable(executable_name)

    def test_non_windows_environment_has_no_path_fallback(self) -> None:
        with (
            patch.object(command_runner.os, "name", "posix"),
            self.assertRaisesRegex(OSError, "yalnız Windows"),
        ):
            command_runner._get_system_directory_windows()

    def test_standard_command_uses_resolved_cmd_path(self) -> None:
        resolved = r"C:\Windows\System32\cmd.exe"
        script = Path(tempfile.gettempdir()) / "trusted-command-test.cmd"
        with (
            patch.object(
                command_runner,
                "trusted_system_executable",
                return_value=resolved,
            ),
            patch.object(
                command_runner,
                "create_command_script",
                return_value=script,
            ),
            patch.object(command_runner.subprocess, "Popen") as popen,
        ):
            ok, _message = run_command(
                "echo test",
                admin=False,
                keep_open=False,
            )

        self.assertTrue(ok)
        self.assertEqual(popen.call_args.args[0][0], resolved)
        self.assertEqual(
            popen.call_args.kwargs["cwd"],
            r"C:\Windows\System32",
        )

    def test_admin_command_uses_resolved_cmd_path(self) -> None:
        resolved = r"C:\Windows\System32\cmd.exe"
        script = Path(tempfile.gettempdir()) / "trusted-admin-test.cmd"
        shell32 = Mock()
        shell32.ShellExecuteW.return_value = 42
        windll = Mock(shell32=shell32)
        with (
            patch.object(
                command_runner,
                "trusted_system_executable",
                return_value=resolved,
            ),
            patch.object(
                command_runner,
                "create_command_script",
                return_value=script,
            ),
            patch.object(command_runner.ctypes, "windll", windll),
        ):
            ok, _message = run_command(
                "echo test",
                admin=True,
                keep_open=False,
            )

        self.assertTrue(ok)
        self.assertEqual(shell32.ShellExecuteW.call_args.args[2], resolved)
        self.assertEqual(
            shell32.ShellExecuteW.call_args.args[4],
            r"C:\Windows\System32",
        )

    def test_resolver_failure_does_not_create_or_run_script(self) -> None:
        with (
            patch.object(
                command_runner,
                "trusted_system_executable",
                side_effect=OSError("System32 çözülemedi"),
            ),
            patch.object(command_runner, "create_command_script") as create,
            patch.object(command_runner.subprocess, "Popen") as popen,
        ):
            ok, message = run_command(
                "echo çalışmamalı",
                admin=False,
                keep_open=False,
            )

        self.assertFalse(ok)
        self.assertIn("başlatılamadı", message)
        create.assert_not_called()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
