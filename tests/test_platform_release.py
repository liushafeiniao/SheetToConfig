import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import QUrl

from scripts.build import artifact_name
from scripts.check_release import validate_release
from scripts.package_macos import dmg_filename, normalize_arch
from sheet_to_config.utils.os_integration import open_local_path


ROOT = Path(__file__).resolve().parents[1]


class PlatformIntegrationTests(unittest.TestCase):
    def test_desktop_opener_uses_a_local_file_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            with patch(
                "sheet_to_config.utils.os_integration.QDesktopServices.openUrl",
                return_value=True,
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
            version_file = root / "sheet_to_config" / "version.py"
            version_file.parent.mkdir()
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


class BuildConfigurationTests(unittest.TestCase):
    def test_relocated_spec_resolves_launcher_from_repository_root(self):
        spec = (ROOT / "packaging" / "SheetToConfig.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn("[str(REPO_ROOT / 'SheetToConfig.py')]", spec)
        self.assertIn("REPO_ROOT / 'sheet_to_config' / 'assets'", spec)
        self.assertNotIn("\n    ['SheetToConfig.py'],", spec)


class ReleaseWorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

    def _job_block(self, job_name: str, next_job_name: str | None = None) -> str:
        marker = f"\n  {job_name}:"
        self.assertIn(marker, self.workflow)
        block = self.workflow.split(marker, 1)[1]
        if next_job_name is not None:
            block = block.split(f"\n  {next_job_name}:", 1)[0]
        return block

    def test_stable_tags_publish_only_windows_assets(self):
        publish_job = self._job_block("publish")
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", publish_job)
        self.assertIn("permissions:\n      contents: write", publish_job)
        self.assertIn("SheetToConfig-v${VERSION}-windows-x64.exe", publish_job)
        self.assertIn("SHA256SUMS.txt", publish_job)
        self.assertNotIn("macos", publish_job.casefold())
        self.assertNotIn("*.dmg", publish_job)

    def test_actions_are_commit_pinned_with_version_comments(self):
        expected_actions = {
            "actions/checkout": (
                "v4.4.0",
                "11d5960a326750d5838078e36cf38b85af677262",
            ),
            "actions/setup-python": (
                "v5.6.0",
                "a26af69be951a213d495a4c3e4e4022e16d87065",
            ),
            "actions/upload-artifact": (
                "v4.6.2",
                "ea165f8d65b6e75b540449e92b4886f43607fa02",
            ),
            "actions/download-artifact": (
                "v4.3.0",
                "d3f86a106a0bac45b974a628896c90dbdf5c8093",
            ),
        }
        for action, (version, commit) in expected_actions.items():
            self.assertIn(f"# {action} {version}", self.workflow)
            self.assertIn(f"uses: {action}@{commit}", self.workflow)
        self.assertNotIn("pull_request_target", self.workflow)

    def test_private_assets_are_injected_only_in_the_private_builder(self):
        private_builder = self._job_block("build-windows-private", "build-macos-preview")
        self.assertIn("environment: private-release-assets", private_builder)
        self.assertIn("github.event_name == 'push'", private_builder)
        self.assertIn("needs: [validate, test]", private_builder)
        self.assertIn("contents: read", private_builder)
        self.assertNotIn("contents: write", private_builder)
        self.assertNotIn("GH_TOKEN", private_builder)
        self.assertIn("python scripts/inject_donation_assets.py --from-env --require", private_builder)
        secret_names = {
            "DONATE_ALIPAY_PNG_B64_1",
            "DONATE_ALIPAY_PNG_B64_2",
            "DONATE_WECHAT_PNG_B64_1",
            "DONATE_WECHAT_PNG_B64_2",
            "DONATE_ALIPAY_PNG_SHA256",
            "DONATE_WECHAT_PNG_SHA256",
        }
        self.assertEqual(
            secret_names,
            {
                line.split("secrets.", 1)[1].split("}", 1)[0].strip()
                for line in private_builder.splitlines()
                if "secrets." in line
            },
        )
        self.assertIn("SHA256SUMS.txt", private_builder)
        self.assertIn("Compare-Object $files $expected", private_builder)
        self.assertIn("-ne $expectedChecksum", private_builder)
        self.assertEqual(1, self.workflow.count("environment: private-release-assets"))
        self.assertEqual(6, self.workflow.count("secrets."))

        for job_name, next_job in (
            ("validate", "test"),
            ("test", "build-windows-private"),
            ("build-macos-preview", "publish"),
            ("publish", None),
        ):
            with self.subTest(job=job_name):
                public_job = self._job_block(job_name, next_job)
                self.assertNotIn("environment:", public_job)
                self.assertNotIn("secrets.", public_job)
        self.assertEqual(1, self.workflow.count("contents: write"))

    def test_artifact_handoff_is_verified_before_the_only_mutation(self):
        publish_job = self._job_block("publish")
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", publish_job)
        self.assertIn("test \"${actual}\" = \"${expected_files}\"", publish_job)
        self.assertIn("sha256sum --check SHA256SUMS.txt", publish_job)
        self.assertIn("Release already exists", publish_job)
        self.assertNotIn("gh release upload", publish_job)
        self.assertEqual(1, self.workflow.count("gh release create"))
        self.assertLess(
            publish_job.index("Verify exact stable assets and checksums"),
            publish_job.index("Create the exact Windows stable release"),
        )

    def test_stable_assets_are_verified_before_remote_mutation(self):
        publish_job = self._job_block("publish")
        verify_position = publish_job.index("Verify exact stable assets and checksums")
        mutation_position = publish_job.index("Create the exact Windows stable release")
        self.assertLess(verify_position, mutation_position)
        self.assertIn("sha256sum --check SHA256SUMS.txt", publish_job)
        self.assertIn("find artifacts -maxdepth 1 -type f", publish_job)
        self.assertIn("gh release view", publish_job)
        self.assertIn("GH_REPO: ${{ github.repository }}", publish_job)
        self.assertIn("test \"${actual}\" = \"${expected_files}\"", publish_job)

    def test_macos_build_is_manual_internal_preview_only(self):
        dispatch = self.workflow.split("  workflow_dispatch:", 1)[1].split(
            "\n\npermissions:", 1
        )[0]
        self.assertIn("build_unsigned_macos:", dispatch)
        self.assertIn("default: false", dispatch)

        preview_job = self._job_block("build-macos-preview", "publish")
        self.assertIn("github.event_name == 'workflow_dispatch'", preview_job)
        self.assertIn("inputs.build_unsigned_macos", preview_job)
        self.assertIn("--unsigned", preview_job)
        self.assertIn("macos-internal-preview", preview_job)
        self.assertIn("ref: refs/heads/main", preview_job)
        self.assertNotIn("contents: write", preview_job)
        self.assertNotIn("gh release", preview_job)

    def test_tag_validation_requires_the_current_main_commit(self):
        validate_job = self._job_block("validate", "test")
        self.assertIn("git fetch --no-tags origin refs/heads/main", validate_job)
        self.assertIn('git rev-list -n 1 "${GITHUB_REF}"', validate_job)
        self.assertIn('git rev-parse origin/main', validate_job)
        self.assertIn('test "${tag_commit}" = "${checkout_commit}"', validate_job)
        self.assertIn('test "${tag_commit}" = "${main_commit}"', validate_job)
        self.assertIn('python scripts/check_release.py --tag "${GITHUB_REF_NAME}"', validate_job)

    def test_cross_platform_tests_remain_enabled(self):
        test_job = self._job_block("test", "build-windows-private")
        self.assertIn("windows-latest", test_job)
        self.assertIn("macos-15", test_job)
        self.assertIn("macos-15-intel", test_job)
        self.assertIn("python scripts/run_tests.py", test_job)
        self.assertNotIn("environment:", test_job)
        self.assertNotIn("secrets.", test_job)


if __name__ == "__main__":
    unittest.main()
