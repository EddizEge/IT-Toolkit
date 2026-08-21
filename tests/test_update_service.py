from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_v2.services.update_service import (
    ReleaseInfo,
    UpdateError,
    compare_versions,
    download_update,
    release_from_payload,
    schedule_self_update,
    select_update,
)


def release_payload(
    tag: str,
    *,
    prerelease: bool = True,
    digest: str = "",
) -> dict[str, object]:
    executable = f"IT_Toolkit_{tag}.exe"
    return {
        "tag_name": tag,
        "name": f"IT Toolkit {tag}",
        "body": "Sürüm notları",
        "html_url": f"https://github.com/EddizEge/IT-Toolkit/releases/tag/{tag}",
        "draft": False,
        "prerelease": prerelease,
        "assets": [
            {
                "name": executable,
                "browser_download_url": (
                    "https://github.com/EddizEge/IT-Toolkit/releases/download/"
                    f"{tag}/{executable}"
                ),
                "size": 100,
                "digest": digest,
            },
            {
                "name": f"{executable}.sha256",
                "browser_download_url": (
                    "https://github.com/EddizEge/IT-Toolkit/releases/download/"
                    f"{tag}/{executable}.sha256"
                ),
            },
        ],
    }


class UpdateServiceTests(unittest.TestCase):
    def test_semver_prerelease_order(self) -> None:
        self.assertLess(compare_versions("v0.6.0-beta.1", "v0.6.0-beta.2"), 0)
        self.assertLess(compare_versions("v0.6.0-beta.2", "v0.6.0-rc.1"), 0)
        self.assertLess(compare_versions("v0.6.0-rc.1", "v0.6.0"), 0)
        self.assertGreater(compare_versions("v0.7.0-beta.1", "v0.6.0"), 0)

    def test_selects_highest_compatible_prerelease(self) -> None:
        releases = [
            release_payload("v0.6.0-beta.2"),
            release_payload("v0.7.0-beta.1"),
            release_payload("v0.6.0-beta.3"),
        ]

        selected = select_update(
            releases,
            current_version="0.6.0-beta.1",
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.tag, "v0.7.0-beta.1")

    def test_stable_channel_ignores_prerelease(self) -> None:
        selected = select_update(
            [
                release_payload("v1.1.0-beta.1"),
                release_payload("v1.0.1", prerelease=False),
            ],
            current_version="1.0.0",
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.tag, "v1.0.1")

    def test_release_requires_matching_executable_and_checksum(self) -> None:
        payload = release_payload("v0.6.0-beta.2")
        payload["assets"] = []

        self.assertIsNone(
            release_from_payload(
                payload,
                current_version="0.6.0-beta.1",
            )
        )

    def test_download_verifies_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.exe"
            source.write_bytes(b"verified executable")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            release = ReleaseInfo(
                tag="v0.6.0-beta.2",
                name="Beta 2",
                notes="",
                page_url="",
                prerelease=True,
                asset_name="IT_Toolkit_v0.6.0-beta.2.exe",
                asset_url=source.as_uri(),
                asset_size=source.stat().st_size,
                asset_digest=f"sha256:{digest}",
                checksum_url="",
            )

            downloaded = download_update(
                release,
                directory=root / "downloads",
            )

            self.assertEqual(downloaded.path.read_bytes(), source.read_bytes())
            self.assertEqual(downloaded.sha256, digest)

    def test_download_rejects_invalid_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.exe"
            source.write_bytes(b"tampered")
            release = ReleaseInfo(
                tag="v0.6.0-beta.2",
                name="Beta 2",
                notes="",
                page_url="",
                prerelease=True,
                asset_name="IT_Toolkit_v0.6.0-beta.2.exe",
                asset_url=source.as_uri(),
                asset_size=source.stat().st_size,
                asset_digest=f"sha256:{'0' * 64}",
                checksum_url="",
            )

            with self.assertRaises(UpdateError):
                download_update(
                    release,
                    directory=root / "downloads",
                )

    def test_schedule_builds_detached_verified_replace_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "IT_Toolkit_old.exe"
            downloaded = root / "IT_Toolkit_new.exe"
            current.write_bytes(b"old")
            downloaded.write_bytes(b"new")

            with patch(
                "app_v2.services.update_service.subprocess.Popen"
            ) as popen:
                schedule_self_update(
                    downloaded,
                    expected_sha256=hashlib.sha256(b"new").hexdigest(),
                    current_executable=current,
                    process_id=1234,
                )

            arguments = popen.call_args.args[0]
            encoded = arguments[arguments.index("-EncodedCommand") + 1]
            script = base64.b64decode(encoded).decode("utf-16-le")
            self.assertIn("Wait-Process -Id 1234", script)
            self.assertIn(str(current.resolve()), script)
            self.assertIn(str(downloaded.resolve()), script)
            self.assertIn("Get-FileHash", script)
            self.assertIn(hashlib.sha256(b"new").hexdigest(), script)


if __name__ == "__main__":
    unittest.main()
