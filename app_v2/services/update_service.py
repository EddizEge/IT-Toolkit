from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app_v2 import __version__

RELEASES_API_URL = (
    "https://api.github.com/repos/EddizEge/IT-Toolkit/releases?per_page=20"
)
API_VERSION = "2022-11-28"
USER_AGENT = f"IT-Toolkit/{__version__}"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
VERSION_PATTERN = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?$"
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...]


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    name: str
    notes: str
    page_url: str
    prerelease: bool
    asset_name: str
    asset_url: str
    asset_size: int
    asset_digest: str
    checksum_url: str


@dataclass(frozen=True)
class DownloadedUpdate:
    path: Path
    sha256: str


def default_update_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return root / "IT Toolkit" / "updates"


def parse_version(value: str) -> ParsedVersion:
    match = VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Geçersiz sürüm: {value}")
    prerelease = tuple(
        item
        for item in (match.group("prerelease") or "").split(".")
        if item
    )
    return ParsedVersion(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
    )


def compare_versions(left: str, right: str) -> int:
    left_version = parse_version(left)
    right_version = parse_version(right)
    left_core = (
        left_version.major,
        left_version.minor,
        left_version.patch,
    )
    right_core = (
        right_version.major,
        right_version.minor,
        right_version.patch,
    )
    if left_core != right_core:
        return 1 if left_core > right_core else -1
    if not left_version.prerelease and not right_version.prerelease:
        return 0
    if not left_version.prerelease:
        return 1
    if not right_version.prerelease:
        return -1

    for left_item, right_item in zip(
        left_version.prerelease,
        right_version.prerelease,
    ):
        if left_item == right_item:
            continue
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_item) > int(right_item) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_item.casefold() > right_item.casefold() else -1
    if len(left_version.prerelease) == len(right_version.prerelease):
        return 0
    return 1 if len(left_version.prerelease) > len(right_version.prerelease) else -1


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    try:
        return compare_versions(candidate, current) > 0
    except ValueError:
        return False


def _asset_map(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return {}
    return {
        str(asset.get("name") or ""): asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name")
    }


def release_from_payload(
    release: dict[str, Any],
    *,
    current_version: str = __version__,
) -> ReleaseInfo | None:
    if release.get("draft"):
        return None
    tag = str(release.get("tag_name") or "")
    if not is_newer_version(tag, current_version):
        return None
    current_is_prerelease = bool(parse_version(current_version).prerelease)
    if release.get("prerelease") and not current_is_prerelease:
        return None

    assets = _asset_map(release)
    executable_name = f"IT_Toolkit_{tag}.exe"
    executable = assets.get(executable_name)
    if not executable:
        return None
    asset_url = str(executable.get("browser_download_url") or "")
    if not asset_url.startswith("https://github.com/"):
        return None

    checksum_name = f"{executable_name}.sha256"
    checksum = assets.get(checksum_name, {})
    checksum_url = str(checksum.get("browser_download_url") or "")
    digest = str(executable.get("digest") or "")
    if not digest.startswith("sha256:") and not checksum_url.startswith(
        "https://github.com/"
    ):
        return None

    return ReleaseInfo(
        tag=tag,
        name=str(release.get("name") or tag),
        notes=str(release.get("body") or ""),
        page_url=str(release.get("html_url") or ""),
        prerelease=bool(release.get("prerelease")),
        asset_name=executable_name,
        asset_url=asset_url,
        asset_size=max(0, int(executable.get("size") or 0)),
        asset_digest=digest,
        checksum_url=checksum_url,
    )


def select_update(
    releases: list[dict[str, Any]],
    *,
    current_version: str = __version__,
) -> ReleaseInfo | None:
    candidates = [
        item
        for release in releases
        if (item := release_from_payload(
            release,
            current_version=current_version,
        ))
    ]
    if not candidates:
        return None
    selected = candidates[0]
    for candidate in candidates[1:]:
        if compare_versions(candidate.tag, selected.tag) > 0:
            selected = candidate
    return selected


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )


def check_for_update(
    *,
    current_version: str = __version__,
    timeout: int = 12,
) -> ReleaseInfo | None:
    try:
        with urlopen(_request(RELEASES_API_URL), timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise UpdateError(f"GitHub sürüm bilgisi alınamadı: {exc}") from exc
    if not isinstance(payload, list):
        raise UpdateError("GitHub geçersiz sürüm verisi döndürdü.")
    releases = [item for item in payload if isinstance(item, dict)]
    return select_update(releases, current_version=current_version)


def _expected_checksum(release: ReleaseInfo, *, timeout: int) -> str:
    if release.asset_digest.startswith("sha256:"):
        digest = release.asset_digest.removeprefix("sha256:").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    if not release.checksum_url:
        raise UpdateError("Yayın için SHA-256 doğrulama dosyası bulunamadı.")
    try:
        with urlopen(_request(release.checksum_url), timeout=timeout) as response:
            checksum_text = response.read(4096).decode("ascii", errors="replace")
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise UpdateError(f"SHA-256 dosyası indirilemedi: {exc}") from exc
    match = re.search(r"(?i)\b[0-9a-f]{64}\b", checksum_text)
    if not match:
        raise UpdateError("SHA-256 dosyası geçerli bir özet içermiyor.")
    return match.group(0).lower()


def download_update(
    release: ReleaseInfo,
    *,
    directory: Path | None = None,
    timeout: int = 45,
    progress_callback: Any = None,
) -> DownloadedUpdate:
    destination_directory = directory or default_update_directory()
    destination_directory.mkdir(parents=True, exist_ok=True)
    temporary_path = destination_directory / f"{release.asset_name}.download"
    final_path = destination_directory / release.asset_name
    expected = _expected_checksum(release, timeout=timeout)
    digest = hashlib.sha256()
    downloaded = 0

    try:
        with urlopen(_request(release.asset_url), timeout=timeout) as response:
            total = max(
                release.asset_size,
                int(response.headers.get("Content-Length") or 0),
            )
            with temporary_path.open("wb") as handle:
                while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                    handle.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        actual = digest.hexdigest().lower()
        if actual != expected:
            raise UpdateError(
                "İndirilen güncellemenin SHA-256 doğrulaması başarısız."
            )
        temporary_path.replace(final_path)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise UpdateError(f"Güncelleme indirilemedi: {exc}") from exc
    except UpdateError:
        raise
    finally:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
    return DownloadedUpdate(path=final_path, sha256=actual)


def can_self_update() -> bool:
    return bool(getattr(sys, "frozen", False)) and Path(sys.executable).suffix.lower() == ".exe"


def _powershell_literal(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def schedule_self_update(
    downloaded_executable: Path,
    *,
    expected_sha256: str,
    current_executable: Path | None = None,
    process_id: int | None = None,
) -> None:
    target = (current_executable or Path(sys.executable)).resolve()
    source = downloaded_executable.resolve()
    if current_executable is None and not can_self_update():
        raise UpdateError(
            "Otomatik kurulum yalnızca paketlenmiş IT Toolkit EXE içinde kullanılabilir."
        )
    if (
        target.suffix.lower() != ".exe"
        or source.suffix.lower() != ".exe"
        or not target.is_file()
        or not source.is_file()
        or source == target
    ):
        raise UpdateError("Güncelleme dosyası veya hedef uygulama yolu geçersiz.")
    normalized_sha256 = expected_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized_sha256):
        raise UpdateError("Güncelleme için geçerli SHA-256 özeti bulunamadı.")

    backup = target.with_suffix(".previous.exe")
    log_path = default_update_directory() / "update-result.log"
    pid = process_id or os.getpid()
    script = f"""
$ErrorActionPreference = 'Stop'
$source = {_powershell_literal(source)}
$target = {_powershell_literal(target)}
$backup = {_powershell_literal(backup)}
$log = {_powershell_literal(log_path)}
try {{
    $actualHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne '{normalized_sha256}') {{
        throw 'Güncelleme dosyası değiştirme öncesi doğrulanamadı.'
    }}
    Wait-Process -Id {pid} -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 900
    if (Test-Path -LiteralPath $target) {{
        Copy-Item -LiteralPath $target -Destination $backup -Force
    }}
    Copy-Item -LiteralPath $source -Destination $target -Force
    Start-Process -FilePath $target
    Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
    'Güncelleme başarıyla uygulandı.' | Set-Content -LiteralPath $log -Encoding UTF8
}} catch {{
    $_ | Out-String | Set-Content -LiteralPath $log -Encoding UTF8
    if (Test-Path -LiteralPath $backup) {{
        Copy-Item -LiteralPath $backup -Destination $target -Force
        Start-Process -FilePath $target
    }}
}}
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            creationflags=(
                CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            ),
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError(f"Güncelleme yardımcısı başlatılamadı: {exc}") from exc
