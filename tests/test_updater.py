import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sheet_to_config.utils.updater import (
    DownloadedUpdate,
    ReleaseInfo,
    UpdateError,
    download_update,
    expected_sha256,
    fetch_latest_release,
    is_newer_version,
    launch_update,
    parse_version,
    release_info_from_payload,
    sha256_file,
)


class _Response:
    def __init__(self, body: bytes):
        self._body = body
        self._read = False
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _size=-1):
        if self._read:
            return b""
        self._read = True
        return self._body


def _release_payload(version="9.9.9"):
    executable_name = f"SheetToConfig-v{version}-windows-x64.exe"
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/liushafeiniao/SheetToConfig/releases/tag/v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": executable_name,
                "browser_download_url": f"https://github.com/liushafeiniao/SheetToConfig/releases/download/v{version}/{executable_name}",
                "size": 123,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": f"https://github.com/liushafeiniao/SheetToConfig/releases/download/v{version}/SHA256SUMS.txt",
            },
        ],
    }


class UpdaterTests(unittest.TestCase):
    def test_version_parsing_and_comparison(self):
        self.assertEqual((1, 2, 3), parse_version("v1.2.3"))
        self.assertTrue(is_newer_version("1.0.4", "1.0.3"))
        self.assertFalse(is_newer_version("1.0.3", "1.0.3"))
        self.assertFalse(is_newer_version("1.0.2", "1.0.3"))
        with self.assertRaises(UpdateError):
            parse_version("1.2")

    def test_release_payload_selects_the_exact_windows_assets(self):
        release = release_info_from_payload(_release_payload())

        self.assertEqual("9.9.9", release.version)
        self.assertEqual("SheetToConfig-v9.9.9-windows-x64.exe", release.asset_name)
        self.assertTrue(release.asset_url.startswith("https://"))
        self.assertEqual(123, release.asset_size)

    def test_fetch_latest_release_returns_none_for_current_version(self):
        response = _Response(json.dumps(_release_payload("1.0.4")).encode("utf-8"))
        opener = Mock(return_value=response)

        self.assertIsNone(fetch_latest_release(opener=opener))
        request = opener.call_args.args[0]
        self.assertEqual(15, opener.call_args.kwargs["timeout"])
        self.assertEqual("application/vnd.github+json", request.headers["Accept"])

    def test_expected_checksum_and_file_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "update.exe"
            path.write_bytes(b"update")
            digest = hashlib.sha256(b"update").hexdigest()

            self.assertEqual(
                digest,
                expected_sha256(f"{digest.upper()} *update.exe", "update.exe"),
            )
            self.assertEqual(digest, sha256_file(path))
            with self.assertRaises(UpdateError):
                expected_sha256("0" * 64 + " *other.exe", "update.exe")

    def test_download_update_verifies_checksum_and_reports_progress(self):
        executable_name = "SheetToConfig-v9.9.9-windows-x64.exe"
        executable = b"verified update"
        digest = hashlib.sha256(executable).hexdigest()
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            release_url="https://github.com/liushafeiniao/SheetToConfig/releases/tag/v9.9.9",
            asset_name=executable_name,
            asset_url="https://example.com/update.exe",
            checksum_url="https://example.com/SHA256SUMS.txt",
        )
        progress = []

        def opener(request, timeout):
            self.assertEqual(30, timeout)
            if request.full_url.endswith("SHA256SUMS.txt"):
                return _Response(f"{digest} *{executable_name}".encode("ascii"))
            return _Response(executable)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = download_update(
                release,
                download_root=Path(temp_dir),
                opener=opener,
                progress=lambda current, total: progress.append((current, total)),
            )
            try:
                self.assertIsInstance(result, DownloadedUpdate)
                self.assertEqual(executable, result.executable_path.read_bytes())
                self.assertEqual([(len(executable), len(executable))], progress)
            finally:
                shutil.rmtree(result.workspace, ignore_errors=True)

    def test_download_update_removes_staging_on_checksum_mismatch(self):
        executable = b"tampered update"
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            release_url="https://example.com/release",
            asset_name="SheetToConfig-v9.9.9-windows-x64.exe",
            asset_url="https://example.com/update.exe",
            checksum_url="https://example.com/SHA256SUMS.txt",
        )

        def opener(request, timeout):
            if request.full_url.endswith("SHA256SUMS.txt"):
                return _Response(("0" * 64 + " *" + release.asset_name).encode("ascii"))
            return _Response(executable)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(UpdateError):
                download_update(
                    release, download_root=Path(temp_dir), opener=opener
                )
            self.assertEqual([], list(Path(temp_dir).iterdir()))

    @unittest.skipUnless(os.name == "nt", "the replacement helper is Windows-only")
    def test_launch_update_stages_helper_and_passes_parent_pid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "SheetToConfig.exe"
            current.write_bytes(b"current")
            workspace = root / "update"
            workspace.mkdir()
            downloaded = workspace / "SheetToConfig-v9.9.9-windows-x64.exe"
            downloaded.write_bytes(b"downloaded")
            package = DownloadedUpdate(
                ReleaseInfo(
                    "9.9.9",
                    "v9.9.9",
                    "https://example.com/release",
                    downloaded.name,
                    "https://example.com/update.exe",
                    "https://example.com/SHA256SUMS.txt",
                ),
                downloaded,
                workspace,
            )
            popen = Mock()

            helper = launch_update(
                package,
                executable_path=current,
                frozen=True,
                popen=popen,
            )

            command = popen.call_args.args[0]
            self.assertEqual(helper, Path(command[0]))
            self.assertEqual(
                [
                    "--apply-update",
                    str(current.resolve()),
                    str(downloaded),
                    str(os.getpid()),
                    str(helper),
                ],
                command[1:],
            )
            self.assertTrue(helper.is_file())


if __name__ == "__main__":
    unittest.main()
