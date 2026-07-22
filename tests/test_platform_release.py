import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import QUrl

from build import artifact_name
from scripts.check_release import validate_release
from scripts.package_macos import dmg_filename, normalize_arch
from utils.os_integration import open_local_path


class PlatformIntegrationTests(unittest.TestCase):
    def test_desktop_opener_uses_a_local_file_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            with patch(
                "utils.os_integration.QDesktopServices.openUrl", return_value=True
            ) as open_url:
                self.assertTrue(open_local_path(target))
            url = open_url.call_args.args[0]
            self.assertIsInstance(url, QUrl)
            self.assertTrue(url.isLocalFile())
            self.assertEqual(target.resolve(), Path(url.toLocalFile()).resolve())

    def test_platform_artifact_names_are_native(self):
        self.assertEqual("SheetToConfig.exe", artifact_name("win32"))
        self.assertEqual("SheetToConfig.app", artifact_name("darwin"))
        self.assertEqual("SheetToConfig", artifact_name("linux"))


class ReleaseMetadataTests(unittest.TestCase):
    def test_release_tag_version_and_changelog_must_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            version_file = root / "version.py"
            changelog = root / "CHANGELOG.md"
            version_file.write_text('__version__ = "2.3.4"\n', encoding="utf-8")
            changelog.write_text("## [2.3.4] - 2026-07-22\n", encoding="utf-8")
            self.assertEqual(
                "2.3.4", validate_release("v2.3.4", version_file, changelog)
            )
            with self.assertRaisesRegex(ValueError, "must exactly match"):
                validate_release("v2.3.5", version_file, changelog)

    def test_macos_architecture_and_filename_are_stable(self):
        self.assertEqual("arm64", normalize_arch("aarch64"))
        self.assertEqual("x64", normalize_arch("x86_64"))
        self.assertEqual(
            "SheetToConfig-v1.0.0-macos-arm64.dmg",
            dmg_filename("1.0.0", "arm64"),
        )
        self.assertEqual(
            "SheetToConfig-v1.0.0-macos-x64-unsigned.dmg",
            dmg_filename("1.0.0", "x86_64", unsigned=True),
        )


if __name__ == "__main__":
    unittest.main()
