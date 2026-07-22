import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sheet_to_config import app_paths
from sheet_to_config.app_paths import DATA_DIR_ENV, local_data_dir, local_data_path


class AppPathsTests(unittest.TestCase):
    def test_environment_override_selects_local_data_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {DATA_DIR_ENV: temp_dir}):
                self.assertEqual(local_data_dir(), Path(temp_dir).resolve())
                self.assertEqual(
                    local_data_path("projects.json"),
                    Path(temp_dir).resolve() / "projects.json",
                )

    def test_local_data_path_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            local_data_path("../projects.json")

    def test_packaged_macos_uses_application_support(self):
        with patch.object(app_paths.sys, "frozen", True, create=True), patch.object(
            app_paths.sys, "platform", "darwin"
        ):
            self.assertEqual(
                Path.home() / "Library" / "Application Support" / "SheetToConfig",
                app_paths._canonical_data_dir(),
            )

    def test_packaged_linux_honors_xdg_config_home(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            app_paths.sys, "frozen", True, create=True
        ), patch.object(app_paths.sys, "platform", "linux"), patch.dict(
            os.environ, {"XDG_CONFIG_HOME": temp_dir}
        ):
            self.assertEqual(
                Path(temp_dir) / "SheetToConfig", app_paths._canonical_data_dir()
            )

    def test_source_clone_name_does_not_control_data_location(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            app_paths.sys, "frozen", False, create=True
        ), patch.object(app_paths.sys, "platform", "win32"), patch.object(
            app_paths, "__file__", str(Path(temp_dir) / "renamed-clone" / "app_paths.py")
        ), patch.dict(os.environ, {"APPDATA": str(Path(temp_dir) / "AppData")}, clear=False):
            self.assertEqual(
                Path(temp_dir) / "AppData" / "SheetToConfig",
                app_paths._canonical_data_dir(),
            )


if __name__ == "__main__":
    unittest.main()
