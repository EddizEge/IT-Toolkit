from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from app_v2.services.command_builder import aggregate_sequence
from app_v2.services.command_runner import create_command_script


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
                ["cmd.exe", "/d", "/c", str(script)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("SONRAKI_ADIM_CALISTI", result.stdout)
            self.assertFalse(script.exists())


if __name__ == "__main__":
    unittest.main()
