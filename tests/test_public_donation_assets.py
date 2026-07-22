import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
import binascii
import zlib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.check_public_donation_assets import check, main


ROOT = Path(__file__).resolve().parents[1]


def png_gray(value: int, *, split_idat: bool = False) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = binascii.crc32(kind + body).to_bytes(4, "big")
        return len(body).to_bytes(4, "big") + kind + body + crc

    raw = zlib.compress(bytes((0, value)))
    idat = (chunk(b"IDAT", raw[:2]) + chunk(b"IDAT", raw[2:])) if split_idat else chunk(b"IDAT", raw)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", b"\0\0\0\1\0\0\0\1\10\0\0\0\0") + idat + chunk(b"IEND", b"")


class PublicDonationAssetCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repository = self.root / "repository"
        self.private_dir = self.root / "private"
        self.repository.mkdir()
        self.private_dir.mkdir()
        self.alipay = png_gray(30)
        self.wechat = png_gray(220)
        for name, data in (("alipay.png", self.alipay), ("wechat.png", self.wechat)):
            (self.private_dir / name).write_bytes(data)
        self.manifest = self.root / "private-manifest.json"
        self.manifest.write_text(json.dumps({
            "version": 1,
            "files": {
                name: {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                    "width": 1,
                    "height": 1,
                }
                for name, data in (("alipay.png", self.alipay), ("wechat.png", self.wechat))
            },
        }), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _track(self, name: str, data: bytes) -> Path:
        path = self.repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        subprocess.run(["git", "-C", str(self.repository), "add", name], check=True)
        return path

    def test_detects_raw_base64_checksum_and_pixel_equality_without_printing_values(self):
        raw_path = self._track("assets/raw.bin", self.alipay)
        self._track("assets/base64.txt", base64.urlsafe_b64encode(self.wechat).replace(b"A", b"A\n"))
        self._track("assets/checksum.txt", hashlib.sha256(self.alipay).digest())
        pixel_copy = png_gray(30, split_idat=True)
        self._track("assets/reencoded.png", pixel_copy)

        findings = check(self.repository, self.private_dir, self.manifest, [], [], [])
        by_path = {}
        for path, category in findings:
            by_path.setdefault(path, set()).add(category)
        self.assertIn("raw-png", by_path[raw_path.relative_to(self.repository).as_posix()])
        self.assertIn("base64", by_path["assets/base64.txt"])
        self.assertIn("sha256", by_path["assets/checksum.txt"])
        self.assertIn("decoded-pixels", by_path["assets/reencoded.png"])

        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(1, main([
                "--repository", str(self.repository), "--private-dir", str(self.private_dir),
                "--manifest", str(self.manifest),
            ]))
        public_output = output.getvalue()
        self.assertNotIn(self.alipay.hex(), public_output)
        self.assertNotIn(hashlib.sha256(self.wechat).hexdigest(), public_output)
        self.assertNotIn(base64.b64encode(self.alipay).decode("ascii"), public_output)

    def test_scans_supplied_patch_and_rejects_a_bad_manifest(self):
        self._track("README.md", b"safe public file")
        patch = self.root / "candidate.patch"
        patch.write_bytes(base64.b64encode(self.alipay))
        findings = check(self.repository, self.private_dir, self.manifest, [patch], [], [])
        self.assertIn(("patch:candidate.patch", "base64"), findings)

        invalid = self.root / "invalid.json"
        invalid.write_text('{"version": 1, "files": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected donation files"):
            check(self.repository, self.private_dir, invalid, [], [], [])

    def test_public_tree_has_no_donation_images(self):
        donation_dir = ROOT / "sheet_to_config" / "assets" / "donate"
        tracked = subprocess.run(
            [
                "git", "ls-tree", "-r", "--name-only", "HEAD", "--",
                "sheet_to_config/assets/donate",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
        for name in ("alipay.png", "wechat.png"):
            public_path = f"sheet_to_config/assets/donate/{name}"
            self.assertNotIn(public_path, tracked)
            if (donation_dir / name).exists():
                ignored = subprocess.run(
                    ["git", "check-ignore", "--quiet", public_path],
                    cwd=ROOT,
                    check=False,
                )
                self.assertEqual(0, ignored.returncode)
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("sheet_to_config/assets/donate/*", ignore)
        self.assertIn("!sheet_to_config/assets/donate/README.txt", ignore)
        self.assertNotIn("!sheet_to_config/assets/donate/alipay.png", ignore)
        self.assertNotIn("!sheet_to_config/assets/donate/wechat.png", ignore)


if __name__ == "__main__":
    unittest.main()
