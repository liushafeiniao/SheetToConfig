import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.exporter.artifact_manifest import (
    ArtifactRecord,
    build_manifest,
    canonical_manifest_bytes,
    diff_manifests,
    load_manifest,
)
from utils.exporter.atomic_writer import AtomicCommitError, commit_files


class ManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_hashes_only_runtime_identity(self):
        records = [
            ArtifactRecord.from_bytes("client", "B.lua", "lua", b"b", "B.xlsx", "B"),
            ArtifactRecord.from_bytes("client", "A.json", "json", b"alpha", "A.xlsx", "A"),
        ]

        first = build_manifest("client", records)
        second = build_manifest("client", list(reversed(records)))

        self.assertEqual(canonical_manifest_bytes(first), canonical_manifest_bytes(second))
        self.assertEqual([item["path"] for item in first["files"]], ["A.json", "B.lua"])
        self.assertEqual(
            first["files"][0]["sha256"], hashlib.sha256(b"alpha").hexdigest()
        )
        self.assertTrue(first["contentVersion"].startswith("sha256:"))

    def test_manifest_loader_rejects_unknown_versions_and_diff_reports_deletes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "excel2json-manifest.json"
            path.write_text(json.dumps({"manifestVersion": 9}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "version"):
                load_manifest(path, "client")

        old = build_manifest("client", [
            ArtifactRecord.from_bytes("client", "Old.json", "json", b"old", "Old.xlsx", "Old")
        ])
        new = build_manifest("client", [
            ArtifactRecord.from_bytes("client", "New.json", "json", b"new", "New.xlsx", "New")
        ])
        self.assertEqual(diff_manifests(old, new), {
            "added": ["New.json"], "modified": [], "removed": ["Old.json"]
        })


class AtomicWriterTests(unittest.TestCase):
    def test_mid_commit_failure_restores_every_old_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.json"
            second = root / "second.json"
            first.write_bytes(b"old-first")
            second.write_bytes(b"old-second")
            real_replace = __import__("os").replace
            calls = 0

            def fail_second_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("disk stopped")
                return real_replace(source, destination)

            with patch("utils.exporter.atomic_writer.os.replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(AtomicCommitError, "restored"):
                    commit_files({first: b"new-first", second: b"new-second"}, [])

            self.assertEqual(first.read_bytes(), b"old-first")
            self.assertEqual(second.read_bytes(), b"old-second")


if __name__ == "__main__":
    unittest.main()
