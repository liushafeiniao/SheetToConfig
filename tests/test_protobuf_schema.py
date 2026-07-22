import copy
import tempfile
import unittest
from pathlib import Path

from utils.exporter.converter import ExcelConverter
from utils.exporter.protobuf_schema import (
    ProtoSchemaError,
    ProtoSchemaParser,
    extract_manifest,
    validate_compatible,
)

from tests.workbook_factory import base_proto_rows, write_workbook


class ProtoSchemaParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _write(self, rows, **kwargs):
        return write_workbook(
            self.root / "Item.xlsx",
            fields=(("id", "int", "CS"), ("name", "string", "CS")),
            data_rows=((1, "Sword"),),
            proto_rows=rows,
            **kwargs,
        )

    def test_parse_and_render_embeds_round_trippable_manifest(self):
        workbook_path = self._write(base_proto_rows())

        schema = ProtoSchemaParser.parse_workbook(str(workbook_path), "Item")
        proto_text = schema.render_proto()

        self.assertEqual("config", schema.package)
        self.assertEqual("Game.Config", schema.csharp_namespace)
        self.assertEqual("ItemTable", schema.root_message)
        self.assertEqual("ItemRow", schema.row_message.name)
        self.assertEqual(schema.manifest(), extract_manifest(proto_text))
        self.assertIn('syntax = "proto3";', proto_text)
        self.assertIn("repeated ItemRow rows = 1;", proto_text)
        self.assertIn("int32 id = 1;", proto_text)

    def test_defaults_package_and_csharp_namespace(self):
        workbook_path = self._write(base_proto_rows(), package="", csharp_namespace="")

        schema = ProtoSchemaParser.parse_workbook(str(workbook_path), "Item")

        self.assertEqual("config", schema.package)
        self.assertEqual("Game.Config", schema.csharp_namespace)

    def test_requires_proto_sheet(self):
        workbook_path = write_workbook(
            self.root / "MissingProto.xlsx",
            fields=(("id", "int", "CS"),),
            data_rows=((1,),),
        )

        with self.assertRaisesRegex(ProtoSchemaError, "PROTO"):
            ProtoSchemaParser.parse_workbook(str(workbook_path), "Item")

    def test_rejects_invalid_field_numbers_duplicate_members_and_bad_root(self):
        invalid_cases = {
            "reserved range": [
                *base_proto_rows()[:1],
                ("field", "Item", "ItemRow", "id", 19000, "int32", "singular", "", "id", ""),
            ],
            "fractional number": [
                *base_proto_rows()[:1],
                ("field", "Item", "ItemRow", "id", 1.5, "int32", "singular", "", "id", ""),
            ],
            "duplicate number": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "other", 2, "string", "singular", "", "name", ""),
            ],
            "duplicate name": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "name", 3, "string", "singular", "", "name", ""),
            ],
            "bad root": [
                ("root", "Item", "ItemTable", "rows", 1, "ItemRow", "singular", "", "$rows", ""),
                *base_proto_rows()[1:],
            ],
            "unknown message": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "stats", 3, "Missing", "singular", "", "stats", ""),
            ],
            "invalid oneof rule": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "key", 3, "string", "repeated", "value", "name", ""),
            ],
            "invalid special source": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "other", 3, "string", "singular", "", "$bad", ""),
            ],
            "optional source reuse": [
                *base_proto_rows(),
                ("field", "Item", "ItemRow", "maybe_name", 3, "string", "optional", "", "name", ""),
            ],
        }

        for label, rows in invalid_cases.items():
            with self.subTest(label=label):
                workbook_path = self._write(rows)
                with self.assertRaises(ProtoSchemaError):
                    ProtoSchemaParser.parse_workbook(str(workbook_path), "Item")

    def test_reserved_row_renders_both_name_and_number(self):
        rows = [
            *base_proto_rows()[:2],
            ("reserved", "Item", "ItemRow", "name", 2, "", "", "", "", ""),
        ]
        schema = ProtoSchemaParser.parse_workbook(str(self._write(rows)), "Item")

        proto_text = schema.render_proto()

        self.assertIn("reserved 2;", proto_text)
        self.assertIn('reserved "name";', proto_text)

    def test_validates_all_non_x_excel_fields_are_mapped(self):
        workbook_path = write_workbook(
            self.root / "Coverage.xlsx",
            fields=(("id", "int", "CS"), ("name", "string", "CS"), ("debug", "str", "X")),
            data_rows=((1, "Sword", "ignored"),),
            proto_rows=base_proto_rows(),
        )
        converter = ExcelConverter()
        worksheet = converter._read_worksheet(str(workbook_path), "Item")
        schema = ProtoSchemaParser.parse_workbook(str(workbook_path), "Item")

        schema.validate_excel_fields(worksheet)

        incomplete_path = write_workbook(
            self.root / "Incomplete.xlsx",
            fields=(("id", "int", "CS"), ("name", "string", "CS")),
            data_rows=((1, "Sword"),),
            proto_rows=base_proto_rows()[:2],
        )
        incomplete_schema = ProtoSchemaParser.parse_workbook(str(incomplete_path), "Item")
        incomplete_worksheet = converter._read_worksheet(str(incomplete_path), "Item")
        with self.assertRaisesRegex(ProtoSchemaError, "name"):
            incomplete_schema.validate_excel_fields(incomplete_worksheet)


class ProtoCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        path = write_workbook(
            self.root / "Item.xlsx",
            fields=(("id", "int", "CS"), ("name", "string", "CS")),
            data_rows=((1, "Sword"),),
            proto_rows=base_proto_rows(),
        )
        self.old_manifest = ProtoSchemaParser.parse_workbook(str(path), "Item").manifest()

    def test_adding_field_is_compatible(self):
        new_manifest = copy.deepcopy(self.old_manifest)
        row_message = next(item for item in new_manifest["messages"] if item["name"] == "ItemRow")
        row_message["fields"].append(
            {"name": "enabled", "number": 3, "type": "bool", "rule": "singular", "oneof": ""}
        )

        validate_compatible(self.old_manifest, new_manifest)

    def test_type_or_number_change_is_rejected(self):
        for changed_key, changed_value in (("type", "int64"), ("number", 9)):
            with self.subTest(changed_key=changed_key):
                new_manifest = copy.deepcopy(self.old_manifest)
                row_message = next(item for item in new_manifest["messages"] if item["name"] == "ItemRow")
                id_field = next(item for item in row_message["fields"] if item["name"] == "id")
                id_field[changed_key] = changed_value
                with self.assertRaises(ProtoSchemaError):
                    validate_compatible(self.old_manifest, new_manifest)

    def test_deleted_field_requires_name_and_number_reservations(self):
        new_manifest = copy.deepcopy(self.old_manifest)
        row_message = next(item for item in new_manifest["messages"] if item["name"] == "ItemRow")
        row_message["fields"] = [item for item in row_message["fields"] if item["name"] != "name"]

        with self.assertRaisesRegex(ProtoSchemaError, "reserved"):
            validate_compatible(self.old_manifest, new_manifest)

        row_message["reserved_names"].append("name")
        row_message["reserved_numbers"].append(2)
        validate_compatible(self.old_manifest, new_manifest)

    def test_extract_manifest_returns_none_for_unmanaged_proto(self):
        self.assertIsNone(extract_manifest('syntax = "proto3";\n'))


if __name__ == "__main__":
    unittest.main()
