import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt5.QtCore import QBuffer, QIODevice
from PyQt5.QtGui import QColor, QImage

from scripts import inject_donation_assets as donation


def png(width, height, checker=False):
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("#2a5d8f"))
    if checker:
        light, dark = QColor("#2a5d8f"), QColor("#bb8844")
        for y in range(height):
            for x in range(width):
                image.setPixelColor(x, y, dark if (x // 8 + y // 8) % 2 else light)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def image_metadata(data, width, height):
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "width": width,
        "height": height,
    }


class DonationAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alipay = png(364, 367)
        cls.wechat = png(285, 286, checker=True)

    def private_manifest(self, alipay=None, wechat=None, dimensions=None):
        alipay = self.alipay if alipay is None else alipay
        wechat = self.wechat if wechat is None else wechat
        dimensions = dimensions or ((364, 367), (285, 286))
        return {
            "version": 1,
            "files": {
                "alipay.png": image_metadata(alipay, *dimensions[0]),
                "wechat.png": image_metadata(wechat, *dimensions[1]),
            },
        }

    def write_private_input(self, root, manifest=None):
        private = root / "private"
        private.mkdir(exist_ok=True)
        (private / "alipay.png").write_bytes(self.alipay)
        (private / "wechat.png").write_bytes(self.wechat)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest or self.private_manifest()), encoding="utf-8")
        return private, manifest_path

    def env_input(self):
        values = {}
        for label, data in (("ALIPAY", self.alipay), ("WECHAT", self.wechat)):
            encoded = base64.b64encode(data).decode("ascii")
            midpoint = len(encoded) // 2
            values[f"DONATE_{label}_PNG_B64_1"] = encoded[:midpoint]
            values[f"DONATE_{label}_PNG_B64_2"] = encoded[midpoint:]
            values[f"DONATE_{label}_PNG_SHA256"] = hashlib.sha256(data).hexdigest()
        return values

    def run_to(self, args, destination, environ=None):
        real_inject = donation.inject
        with patch.object(donation, "inject", side_effect=lambda payload: real_inject(payload, destination)):
            donation.run(args, environ)

    def test_private_directory_mode_injects_verified_pair(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            private, manifest = self.write_private_input(root)
            destination = root / "assets"
            self.run_to(["--private-dir", str(private), "--manifest", str(manifest), "--require"], destination)
            self.assertEqual(self.alipay, (destination / "alipay.png").read_bytes())
            self.assertEqual(self.wechat, (destination / "wechat.png").read_bytes())

    def test_private_directory_mode_rejects_inputs_inside_public_root(self):
        with tempfile.TemporaryDirectory() as raw:
            public_root = Path(raw) / "public"
            public_root.mkdir()
            private, manifest = self.write_private_input(public_root)
            with patch.object(donation, "ROOT", public_root), self.assertRaises(
                donation.InjectionError
            ):
                donation._load_from_private_dir(private, manifest)

    def test_environment_mode_injects_verified_pair(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "assets"
            self.run_to(["--from-env", "--require"], destination, self.env_input())
            self.assertEqual(self.alipay, (destination / "alipay.png").read_bytes())
            self.assertEqual(self.wechat, (destination / "wechat.png").read_bytes())

    def test_cli_requires_one_complete_mode_and_require(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            private, manifest = self.write_private_input(root)
            invalid = (
                [],
                ["--from-env", "--private-dir", str(private), "--manifest", str(manifest), "--require"],
                ["--private-dir", str(private), "--require"],
                ["--from-env", "--require"],
            )
            for args in invalid:
                with self.subTest(args=args), self.assertRaises(donation.InjectionError):
                    donation.run(args, {})

    def test_environment_rejects_partial_blank_extra_and_oversize_chunks(self):
        base = self.env_input()
        variants = []
        partial = dict(base)
        del partial["DONATE_WECHAT_PNG_B64_2"]
        variants.append(partial)
        blank = dict(base)
        blank["DONATE_ALIPAY_PNG_B64_1"] = ""
        variants.append(blank)
        extra = dict(base)
        extra["DONATE_ALIPAY_PNG_B64_3"] = "AA=="
        variants.append(extra)
        unrelated_extra = dict(base)
        unrelated_extra["DONATE_UNEXPECTED"] = "value"
        variants.append(unrelated_extra)
        oversize = dict(base)
        oversize["DONATE_WECHAT_PNG_B64_1"] = "A" * (donation.MAX_ENV_CHUNK_CHARS + 1)
        variants.append(oversize)
        malformed_base64 = dict(base)
        malformed_base64["DONATE_ALIPAY_PNG_B64_1"] = "private-secret-not-base64!"
        variants.append(malformed_base64)
        for environ in variants:
            with self.subTest(environ=list(environ)), self.assertRaises(donation.InjectionError) as caught:
                donation._load_from_env(environ)
            self.assertNotIn("DONATE_", str(caught.exception))

    def test_private_files_and_manifest_are_size_limited_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            private, manifest = self.write_private_input(root)
            manifest.write_bytes(b" " * (donation.MAX_MANIFEST_BYTES + 1))
            with self.assertRaises(donation.InjectionError) as caught:
                donation._parse_manifest(manifest)
            self.assertNotIn("private-secret", str(caught.exception))
            manifest.write_text(json.dumps(self.private_manifest()), encoding="utf-8")
            (private / "alipay.png").write_bytes(b"x" * (donation.MAX_IMAGE_BYTES + 1))
            with self.assertRaises(donation.InjectionError):
                donation._load_from_private_dir(private, manifest)

    def test_manifest_rejects_malformed_digest_and_dimension(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            invalid = self.private_manifest()
            invalid["extra"] = True
            _, manifest = self.write_private_input(root, invalid)
            with self.assertRaises(donation.InjectionError):
                donation._parse_manifest(manifest)
            malformed = self.private_manifest()
            malformed["files"]["alipay.png"]["sha256"] = "bad"
            _, manifest = self.write_private_input(root, malformed)
            with self.assertRaises(donation.InjectionError):
                donation._parse_manifest(manifest)
            wrong_dimension = self.private_manifest()
            wrong_dimension["files"]["wechat.png"]["width"] += 1
            private, manifest = self.write_private_input(root, wrong_dimension)
            with self.assertRaises(donation.InjectionError):
                donation.run(["--private-dir", str(private), "--manifest", str(manifest), "--require"])

    def test_validation_rejects_bad_digest_crc_trailing_and_duplicate(self):
        metadata = self.private_manifest()["files"]
        bad_digest = {name: dict(value) for name, value in metadata.items()}
        bad_digest["alipay.png"]["sha256"] = "0" * 64
        with self.assertRaises(donation.InjectionError):
            donation._validated_payloads({"alipay.png": self.alipay, "wechat.png": self.wechat}, bad_digest)
        corrupt = self.alipay[:-1] + bytes([self.alipay[-1] ^ 1])
        with self.assertRaises(donation.InjectionError):
            donation._validate_image(corrupt, metadata["alipay.png"], "alipay.png")
        with self.assertRaises(donation.InjectionError):
            donation._validate_image(self.alipay + b"extra", metadata["alipay.png"], "alipay.png")
        duplicate = png(4, 4)
        duplicate_metadata = {
            "alipay.png": image_metadata(duplicate, 4, 4),
            "wechat.png": image_metadata(duplicate, 4, 4),
        }
        with self.assertRaises(donation.InjectionError):
            donation._validated_payloads({"alipay.png": duplicate, "wechat.png": duplicate}, duplicate_metadata)

    def test_second_replacement_error_rolls_back_both_originals(self):
        with tempfile.TemporaryDirectory() as raw:
            assets = Path(raw) / "assets"
            assets.mkdir()
            old_alipay, old_wechat = b"old-one", b"old-two"
            (assets / "alipay.png").write_bytes(old_alipay)
            (assets / "wechat.png").write_bytes(old_wechat)
            calls = []
            original = donation._replace_target

            def fail_second(source, target):
                calls.append(target.name)
                if len(calls) == 2:
                    raise OSError("simulated")
                original(source, target)

            with patch.object(donation, "_replace_target", side_effect=fail_second), self.assertRaises(donation.InjectionError):
                donation.inject({"alipay.png": self.alipay, "wechat.png": self.wechat}, assets)
            self.assertEqual(old_alipay, (assets / "alipay.png").read_bytes())
            self.assertEqual(old_wechat, (assets / "wechat.png").read_bytes())
            self.assertFalse((assets / donation.JOURNAL_NAME).exists())

    def test_recovery_restores_partial_pair_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            assets = Path(raw) / "assets"
            assets.mkdir()
            old = {"alipay.png": b"old-one", "wechat.png": b"old-two"}
            for name, data in old.items():
                (assets / name).write_bytes(data)
            transaction = assets / donation.TRANSACTION_NAME
            backups = transaction / "backups"
            backups.mkdir(parents=True)
            for name, data in old.items():
                (backups / name).write_bytes(data)
            (assets / "alipay.png").write_bytes(self.alipay)
            expected = {name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)} for name, data in (("alipay.png", self.alipay), ("wechat.png", self.wechat))}
            donation._write_json_atomic(assets / donation.JOURNAL_NAME, {"version": 1, "expected": expected, "prior": {name: True for name in old}})
            donation.recover(assets)
            donation.recover(assets)
            self.assertEqual(old["alipay.png"], (assets / "alipay.png").read_bytes())
            self.assertEqual(old["wechat.png"], (assets / "wechat.png").read_bytes())

    def test_recovery_finalizes_complete_pair_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as raw:
            assets = Path(raw) / "assets"
            assets.mkdir()
            transaction = assets / donation.TRANSACTION_NAME
            (transaction / "backups").mkdir(parents=True)
            (assets / "alipay.png").write_bytes(self.alipay)
            (assets / "wechat.png").write_bytes(self.wechat)
            expected = {name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)} for name, data in (("alipay.png", self.alipay), ("wechat.png", self.wechat))}
            donation._write_json_atomic(assets / donation.JOURNAL_NAME, {"version": 1, "expected": expected, "prior": {name: False for name in donation.FILES}})
            donation.recover(assets)
            self.assertFalse((assets / donation.JOURNAL_NAME).exists())
            self.assertFalse(transaction.exists())


if __name__ == "__main__":
    unittest.main()
