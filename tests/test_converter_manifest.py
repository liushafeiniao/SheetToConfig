import json
import tempfile
import unittest
from pathlib import Path

from tests.workbook_factory import base_proto_rows, write_workbook
from sheet_to_config.utils.exporter.artifact_manifest import MANIFEST_NAME
from sheet_to_config.utils.exporter.converter import ExcelConverter


class ConverterManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tables = self.root / "tables"
        self.client = self.root / "client"
        self.server = self.root / "server"
        self.tables.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, value, *, code_rows=None):
        return write_workbook(
            self.tables / f"{name}.xlsx",
            fields=(("code", "int", "CS"), ("value", "str", "CS")),
            data_rows=((1, value),),
            code_rows=code_rows or (("Item", f"{name}.json", "c"),),
        )

    def test_full_export_writes_deterministic_manifest_and_first_column_json_key(self):
        self._write("Item", "Sword")

        first = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        manifest_path = self.client / MANIFEST_NAME
        first_bytes = manifest_path.read_bytes()
        payload = json.loads((self.client / "Item.json").read_text(encoding="utf-8"))

        self.assertTrue(first["success"], first["issues"])
        self.assertEqual(list(payload), ["1"])
        self.assertEqual(first["changes"]["client"]["added"], ["Item.json"])
        self.assertEqual(first["artifacts"][0]["source"]["workbook"], "Item.xlsx")

        second = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(second["success"], second["issues"])
        self.assertEqual(first_bytes, manifest_path.read_bytes())
        self.assertEqual(second["changes"]["client"], {
            "added": [], "modified": [], "removed": []
        })

    def test_zero_is_a_valid_first_column_key_even_when_field_is_not_named_id(self):
        write_workbook(
            self.tables / "Zero.xlsx",
            fields=(("identifier", "int", "CS"), ("value", "str", "CS")),
            data_rows=((0, "zero"),),
            code_rows=(("Item", "Zero.json", "c"),),
        )

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertTrue(result["success"], result["issues"])
        payload = json.loads((self.client / "Zero.json").read_text(encoding="utf-8"))
        self.assertEqual(list(payload), ["0"])

    def test_legacy_id_field_takes_priority_over_the_first_column(self):
        write_workbook(
            self.tables / "Legacy.xlsx",
            fields=(("name", "str", "CS"), ("id", "int", "CS")),
            data_rows=(("sword", 1001), ("shield", 0)),
            code_rows=(("Item", "Legacy.json", "c"),),
        )

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertTrue(result["success"], result["issues"])
        payload = json.loads((self.client / "Legacy.json").read_text(encoding="utf-8"))
        self.assertEqual(list(payload), ["1001", "0"])

    def test_duplicate_legacy_id_blocks_json_commit(self):
        write_workbook(
            self.tables / "Duplicate.xlsx",
            fields=(("name", "str", "CS"), ("id", "int", "CS")),
            data_rows=(("sword", 1), ("shield", 1)),
            code_rows=(("Item", "Duplicate.json", "c"),),
        )

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertFalse(result["success"])
        self.assertIn("DUPLICATE_VALUE", {issue["code"] for issue in result["issues"]})
        self.assertFalse((self.client / "Duplicate.json").exists())

    def test_empty_legacy_id_blocks_json_commit(self):
        write_workbook(
            self.tables / "MissingId.xlsx",
            fields=(("name", "str", "CS"), ("id", "int", "CS")),
            data_rows=(("sword", None),),
            code_rows=(("Item", "MissingId.json", "c"),),
        )

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertFalse(result["success"])
        self.assertIn("INVALID_JSON_ROOT_KEY", {
            issue["code"] for issue in result["issues"]
        })
        self.assertFalse((self.client / "MissingId.json").exists())

    def test_legacy_output_without_extension_exports_json_with_warning(self):
        self._write("LegacyName", "value", code_rows=(("Item", "LegacyName", "c"),))
        logs = []

        result = ExcelConverter(logs.append).export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertTrue(result["success"], result["issues"])
        self.assertTrue((self.client / "LegacyName.json").is_file())
        self.assertTrue(any("[WARNING]" in line and ".json" in line for line in logs))

    def test_bad_workbook_keeps_all_old_outputs_and_manifest_unchanged(self):
        self._write("A", "old-a")
        self._write("B", "old-b")
        initial = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(initial["success"], initial["issues"])
        old_a = (self.client / "A.json").read_bytes()
        old_b = (self.client / "B.json").read_bytes()
        old_manifest = (self.client / MANIFEST_NAME).read_bytes()

        self._write("A", "new-a")
        write_workbook(
            self.tables / "B.xlsx",
            fields=(("code", "int", "CS"), ("value", "int", "CS")),
            data_rows=((1, "not-an-int"),),
            code_rows=(("Item", "B.json", "c"),),
        )
        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertFalse(result["success"])
        self.assertEqual((self.client / "A.json").read_bytes(), old_a)
        self.assertEqual((self.client / "B.json").read_bytes(), old_b)
        self.assertEqual((self.client / MANIFEST_NAME).read_bytes(), old_manifest)

    def test_incremental_export_merges_unselected_files_and_removes_old_selected_output(self):
        self._write("A", "old-a", code_rows=(
            ("Item", "A.json", "c"), ("Item", "A.lua", "c")
        ))
        self._write("B", "old-b")
        initial = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(initial["success"], initial["issues"])

        self._write("A", "new-a", code_rows=(("Item", "A.json", "c"),))
        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c", filename="A"
        )

        self.assertTrue(result["success"], result["issues"])
        self.assertFalse((self.client / "A.lua").exists())
        self.assertTrue((self.client / "B.json").exists())
        self.assertEqual(result["changes"]["client"]["removed"], ["A.lua"])
        manifest = json.loads((self.client / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(
            [item["path"] for item in manifest["files"]], ["A.json", "B.json"]
        )

    def test_incremental_export_requires_manifest_and_zero_match_fails(self):
        self._write("A", "value")
        missing_manifest = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c", filename="A"
        )
        self.assertFalse(missing_manifest["success"])
        self.assertFalse((self.client / "A.json").exists())
        self.assertIn("INCREMENTAL_MANIFEST_REQUIRED", {
            issue["code"] for issue in missing_manifest["issues"]
        })

        full = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(full["success"], full["issues"])
        zero_match = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c", filename="Missing"
        )
        self.assertFalse(zero_match["success"])
        self.assertIn("SELECTED_FILE_NOT_FOUND", {
            issue["code"] for issue in zero_match["issues"]
        })

    def test_corrupt_manifest_blocks_full_export_without_touching_data(self):
        self._write("A", "old")
        initial = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(initial["success"], initial["issues"])
        data_path = self.client / "A.json"
        old_data = data_path.read_bytes()
        manifest_path = self.client / MANIFEST_NAME
        manifest_path.write_text("not json", encoding="utf-8")
        corrupt_bytes = manifest_path.read_bytes()
        self._write("A", "new")

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertFalse(result["success"])
        self.assertEqual(data_path.read_bytes(), old_data)
        self.assertEqual(manifest_path.read_bytes(), corrupt_bytes)

    def test_same_platform_output_collision_fails_before_commit(self):
        self._write("A", "a", code_rows=(("Item", "Same.json", "c"),))
        self._write("B", "b", code_rows=(("Item", "Same.json", "c"),))

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertFalse(result["success"])
        self.assertIn("OUTPUT_PATH_CONFLICT", {
            issue["code"] for issue in result["issues"]
        })
        self.assertFalse((self.client / "Same.json").exists())
        self.assertFalse((self.client / MANIFEST_NAME).exists())

    def test_full_export_removes_only_stale_files_owned_by_old_manifest(self):
        self._write("A", "a")
        self._write("B", "b")
        first = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(first["success"], first["issues"])
        unmanaged = self.client / "keep.txt"
        unmanaged.write_text("keep", encoding="utf-8")
        (self.tables / "A.xlsx").unlink()

        result = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )

        self.assertTrue(result["success"], result["issues"])
        self.assertEqual(result["changes"]["client"]["removed"], ["A.json"])
        self.assertFalse((self.client / "A.json").exists())
        self.assertTrue((self.client / "B.json").exists())
        self.assertEqual(unmanaged.read_text(encoding="utf-8"), "keep")

    def test_export_without_pb_preserves_existing_pb_and_manifest_record(self):
        write_workbook(
            self.tables / "Proto.xlsx",
            fields=(("id", "int", "CS"), ("name", "str", "CS")),
            data_rows=((1, "Sword"),),
            proto_rows=base_proto_rows(),
            code_rows=(("Item", "Item.pb", "c"),),
        )
        first = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c"
        )
        self.assertTrue(first["success"], first["issues"])
        pb_path = self.client / "Item.pb"
        old_pb = pb_path.read_bytes()

        second = ExcelConverter().export_all(
            str(self.tables), str(self.client), str(self.server), "c", export_pb=False
        )

        self.assertTrue(second["success"], second["issues"])
        self.assertEqual(pb_path.read_bytes(), old_pb)
        manifest = json.loads((self.client / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual([item["path"] for item in manifest["files"]], ["Item.pb"])


if __name__ == "__main__":
    unittest.main()
