"""GitHub Release checking and Windows self-update support."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from sheet_to_config.version import (
    GITHUB_LATEST_RELEASE_API_URL,
    __version__,
)


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, downloaded, or installed."""


@dataclass(frozen=True)
class ReleaseInfo:
    """Validated metadata for one stable Windows release."""

    version: str
    tag_name: str
    release_url: str
    asset_name: str
    asset_url: str
    checksum_url: str
    asset_size: int = 0


@dataclass(frozen=True)
class DownloadedUpdate:
    """A verified update package staged in a temporary directory."""

    release: ReleaseInfo
    executable_path: Path
    workspace: Path


ProgressCallback = Callable[[int, int], None]
VersionTuple = tuple[int, int, int]

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_CHECKSUM_RE = re.compile(r"^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")
_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
_USER_AGENT = f"SheetToConfig/{__version__}"


def parse_version(value: str) -> VersionTuple:
    """Parse the stable release format used by the Windows workflow."""
    match = _VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        raise UpdateError(f"Unsupported release version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    """Return whether candidate is a newer stable semantic version."""
    return parse_version(candidate) > parse_version(current)


def supports_automatic_update() -> bool:
    """Return whether this process can replace itself with the Windows helper."""
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


def _asset_url(asset: dict[str, Any]) -> str:
    value = str(asset.get("browser_download_url") or asset.get("url") or "")
    if not value.startswith("https://"):
        raise UpdateError("Release asset URL is not HTTPS")
    return value


def release_info_from_payload(payload: dict[str, Any]) -> ReleaseInfo:
    """Validate the latest-release response and select stable Windows assets."""
    if payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("The latest release is not a stable release")

    tag_name = str(payload.get("tag_name") or "").strip()
    version = tag_name.removeprefix("v")
    parse_version(version)
    if not is_newer_version(version):
        raise UpdateError("No newer release is available")

    expected_asset_name = f"SheetToConfig-v{version}-windows-x64.exe"
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("Release assets are missing")

    by_name = {
        str(asset.get("name") or ""): asset
        for asset in assets
        if isinstance(asset, dict)
    }
    executable = by_name.get(expected_asset_name)
    checksum = by_name.get("SHA256SUMS.txt")
    if not executable or not checksum:
        raise UpdateError("The stable Windows update assets are incomplete")

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        release_url=str(payload.get("html_url") or ""),
        asset_name=expected_asset_name,
        asset_url=_asset_url(executable),
        checksum_url=_asset_url(checksum),
        asset_size=int(executable.get("size") or 0),
    )


def fetch_latest_release(
    api_url: str = GITHUB_LATEST_RELEASE_API_URL,
    *,
    opener: Callable[..., Any] = urlopen,
) -> Optional[ReleaseInfo]:
    """Fetch the latest stable release, returning None when already current."""
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with opener(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("No public GitHub release is available") from exc
        raise UpdateError(f"GitHub API request failed: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise UpdateError(f"GitHub API request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise UpdateError("GitHub API returned an invalid release response")
    try:
        return release_info_from_payload(payload)
    except UpdateError as exc:
        if str(exc) == "No newer release is available":
            return None
        raise


def _download_file(
    url: str,
    destination: Path,
    *,
    opener: Callable[..., Any] = urlopen,
    progress: Optional[ProgressCallback] = None,
) -> None:
    if not url.startswith("https://"):
        raise UpdateError("Update download URL is not HTTPS")
    request = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": _USER_AGENT,
        },
    )
    written = 0
    try:
        with opener(request, timeout=30) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            if total > _MAX_DOWNLOAD_BYTES:
                raise UpdateError("The update package is too large")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    raise UpdateError("The update package is too large")
                output.write(chunk)
                if progress:
                    progress(written, total)
    except UpdateError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Update download failed: {exc}") from exc


def expected_sha256(checksum_text: str, asset_name: str) -> str:
    """Extract the checksum for one release asset."""
    for line in checksum_text.splitlines():
        match = _CHECKSUM_RE.match(line)
        if match and match.group(2).strip() == asset_name:
            return match.group(1).lower()
    raise UpdateError(f"Checksum for {asset_name} is missing")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(
    release: ReleaseInfo,
    *,
    download_root: Optional[Path] = None,
    opener: Callable[..., Any] = urlopen,
    progress: Optional[ProgressCallback] = None,
) -> DownloadedUpdate:
    """Download and verify the Windows EXE before any replacement is attempted."""
    workspace = Path(download_root or tempfile.gettempdir()) / (
        f"SheetToConfig-update-{uuid4().hex}"
    )
    workspace.mkdir(parents=True, exist_ok=False)
    executable_path = workspace / release.asset_name
    checksum_path = workspace / "SHA256SUMS.txt"
    try:
        _download_file(
            release.asset_url, executable_path, opener=opener, progress=progress
        )
        _download_file(release.checksum_url, checksum_path, opener=opener)
        expected = expected_sha256(
            checksum_path.read_text(encoding="utf-8"), release.asset_name
        )
        actual = sha256_file(executable_path)
        if actual != expected:
            raise UpdateError("The downloaded update failed SHA-256 verification")
        return DownloadedUpdate(release, executable_path, workspace)
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def _creation_flags() -> int:
    return (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )


def launch_update(
    package: DownloadedUpdate,
    *,
    executable_path: Optional[Path] = None,
    frozen: Optional[bool] = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> Path:
    """Launch a copied updater process and return its helper path."""
    if os.name != "nt":
        raise UpdateError("Automatic updates currently support Windows only")
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        raise UpdateError("Automatic updates require the packaged Windows EXE")

    current = Path(executable_path or sys.executable).resolve()
    if current.suffix.casefold() != ".exe" or not current.is_file():
        raise UpdateError("The current Windows EXE could not be located")
    helper = package.workspace / f"SheetToConfig-updater-{uuid4().hex}.exe"
    try:
        shutil.copy2(current, helper)
        command = [
            str(helper),
            "--apply-update",
            str(current),
            str(package.executable_path),
            str(os.getpid()),
            str(helper),
        ]
        popen(
            command,
            cwd=str(current.parent),
            creationflags=_creation_flags(),
            close_fds=True,
        )
    except Exception:
        helper.unlink(missing_ok=True)
        raise UpdateError("Could not start the update helper")
    return helper


def _wait_for_process(pid: int, timeout_seconds: int = 120) -> bool:
    if pid <= 0 or os.name != "nt":
        return True
    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return True
    try:
        result = kernel32.WaitForSingleObject(handle, timeout_seconds * 1000)
        return result in (0, infinite)
    finally:
        kernel32.CloseHandle(handle)


def _update_workspace(
    downloaded_path: Path,
    helper_path: Optional[Path],
) -> Optional[tuple[Path, Path]]:
    """Return the guarded temporary workspace and helper path, if valid."""
    if helper_path is None:
        return None
    try:
        workspace = downloaded_path.resolve().parent
        helper = helper_path.resolve()
    except OSError:
        return None
    if helper.parent != workspace:
        return None
    if not workspace.name.startswith("SheetToConfig-update-"):
        return None
    if not helper.name.startswith("SheetToConfig-updater-"):
        return None
    return workspace, helper


def _launch_cleanup_worker(
    current_path: Path,
    downloaded_path: Path,
    helper_path: Optional[Path],
    helper_pid: int,
    *,
    popen: Callable[..., Any] = subprocess.Popen,
) -> bool:
    """Ask the restarted EXE to remove the temporary update workspace."""
    workspace_and_helper = _update_workspace(downloaded_path, helper_path)
    if workspace_and_helper is None:
        return False
    workspace, helper = workspace_and_helper
    try:
        popen(
            [
                str(current_path),
                "--cleanup-update",
                str(workspace),
                str(helper),
                str(helper_pid),
            ],
            cwd=str(current_path.parent),
            creationflags=_creation_flags(),
            close_fds=True,
        )
        return True
    except Exception:
        return False


def cleanup_update_workspace(
    workspace_path: Path,
    helper_path: Path,
    helper_pid: int,
) -> int:
    """Delete the temporary update workspace after the helper exits."""
    if not _wait_for_process(helper_pid):
        return 1
    try:
        workspace = workspace_path.resolve()
        helper = helper_path.resolve()
    except OSError:
        return 1
    if helper.parent != workspace:
        return 1
    if not workspace.name.startswith("SheetToConfig-update-"):
        return 1
    if not helper.name.startswith("SheetToConfig-updater-"):
        return 1

    for _ in range(120):
        try:
            helper.unlink(missing_ok=True)
            shutil.rmtree(workspace)
            return 0
        except FileNotFoundError:
            return 0
        except PermissionError:
            time.sleep(0.25)
        except OSError:
            time.sleep(0.25)
    return 1


def cleanup_update_from_cli(arguments: list[str]) -> int:
    """Entry point used by the restarted EXE to remove update temp files."""
    if len(arguments) != 3:
        return 1
    try:
        workspace_path = Path(arguments[0])
        helper_path = Path(arguments[1])
        helper_pid = int(arguments[2])
    except (TypeError, ValueError):
        return 1
    return cleanup_update_workspace(workspace_path, helper_path, helper_pid)


def apply_update(
    current_path: Path,
    downloaded_path: Path,
    parent_pid: int,
    helper_path: Optional[Path] = None,
) -> int:
    """Replace the old EXE after the parent exits, then restart it."""
    if not _wait_for_process(parent_pid):
        return 1
    current_path = current_path.resolve()
    downloaded_path = downloaded_path.resolve()
    if not current_path.is_file() or not downloaded_path.is_file():
        return 1

    backup_path = current_path.with_name(f".{current_path.name}.backup")
    staged_path = current_path.with_name(f".{current_path.name}.staged")
    for _ in range(120):
        try:
            backup_path.unlink(missing_ok=True)
            staged_path.unlink(missing_ok=True)
            # Stage the verified download on the target volume first so the
            # final swap works even when TEMP and the installed EXE are on
            # different drives.
            shutil.copy2(downloaded_path, staged_path)
            os.replace(current_path, backup_path)
            try:
                os.replace(staged_path, current_path)
            except Exception:
                staged_path.unlink(missing_ok=True)
                os.replace(backup_path, current_path)
                return 1
            subprocess.Popen(
                [str(current_path)],
                cwd=str(current_path.parent),
                creationflags=_creation_flags(),
                close_fds=True,
            )
            _launch_cleanup_worker(
                current_path,
                downloaded_path,
                helper_path,
                os.getpid(),
            )
            backup_path.unlink(missing_ok=True)
            return 0
        except PermissionError:
            time.sleep(0.25)
        except OSError:
            return 1
    return 1


def apply_update_from_cli(arguments: list[str]) -> int:
    """Entry point used by the copied packaged EXE."""
    if len(arguments) != 4:
        return 1
    try:
        current_path = Path(arguments[0])
        downloaded_path = Path(arguments[1])
        parent_pid = int(arguments[2])
        helper_path = Path(arguments[3])
    except (TypeError, ValueError):
        return 1
    result = apply_update(current_path, downloaded_path, parent_pid, helper_path)
    return result
