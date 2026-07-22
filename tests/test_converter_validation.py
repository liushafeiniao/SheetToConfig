import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from tests.workbook_factory import write_workbook
from utils.exporter.converter import ExcelConverter
from utils.exporter.template import TypeDefinitionTemplate


class ConverterValidationTests(unittest.TestCase):
    def test_validation_collects_bad_rows_and_uses_converted_first_column_as_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            client = root / "client"
            server = root / "server"
            tables.mkdir()
            write_workbook(
                tables / "A.xlsx",
                fields=(("key", "int", "CS"), ("count", "int+required()", "CS")),
                data_rows=((None, 5), ("bad", "oops"), (1, 1), ("1", 2)),
                code_rows=(("Item", "A.json", "c"),),
            )
            write_workbook(
                tables / "B.xlsx",
                fields=(("code", "int", "CS"), ("enabled", "bool", "CS")),
                data_rows=((2, "maybe"),),
                code_rows=(("Item", "B.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(client), str(server), "c", validation_only=True
            )

            self.assertFalse(result["success"])
            codes = {issue["code"] for issue in result["issues"]}
            self.assertIn("MISSING_PRIMARY_KEY", codes)
            self.assertIn("CONVERSION_ERROR", codes)
            self.assertIn("DUPLICATE_VALUE", codes)
            duplicate = next(
                issue for issue in result["issues"]
                if issue["code"] == "DUPLICATE_VALUE"
            )
            self.assertIn("主键必须唯一", duplicate["message"])
            self.assertIn("A8", duplicate["message"])
            self.assertIn("A7", duplicate["message"])
            self.assertEqual(
                set(result["issues"][0]),
                {"code", "message", "file", "sheet", "row", "column", "field", "path", "rawValue"},
            )
            self.assertFalse(client.exists())

    def test_formula_without_cached_value_is_reported_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            client = root / "client"
            server = root / "server"
            tables.mkdir()
            path = write_workbook(
                tables / "Formula.xlsx",
                fields=(("id", "int", "CS"), ("value", "int", "CS")),
                data_rows=((1, 2),),
                code_rows=(("Item", "Formula.json", "c"),),
            )
            workbook = load_workbook(path)
            workbook["Item"]["B5"] = "=1+1"
            workbook.save(path)
            workbook.close()

            result = ExcelConverter().export_all(
                str(tables), str(client), str(server), "c"
            )

            issue = next(
                item for item in result["issues"]
                if item["code"] == "FORMULA_NO_CACHED_VALUE"
            )
            self.assertEqual((issue["row"], issue["column"], issue["field"]), (5, 2, "value"))
            self.assertFalse((client / "Formula.json").exists())

    def test_asset_root_validates_path_existence_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            assets = root / "assets"
            tables.mkdir()
            (assets / "icons").mkdir(parents=True)
            (assets / "icons" / "sword.png").write_bytes(b"png")
            TypeDefinitionTemplate.ensure_exists(str(tables))
            workbook = load_workbook(tables / "TypeDefinition.xlsx")
            workbook["CODE"].append(("asset", "path(icons/,.png)", ""))
            workbook.save(tables / "TypeDefinition.xlsx")
            workbook.close()

            def export_value(value):
                write_workbook(
                    tables / "Asset.xlsx",
                    fields=(("id", "int", "CS"), ("icon", "asset", "CS")),
                    data_rows=((1, value),),
                    code_rows=(("Item", "Asset.json", "c"),),
                )
                return ExcelConverter().export_all(
                    str(tables), str(root / "client"), str(root / "server"),
                    "c", validation_only=True, asset_root=str(assets),
                )

            self.assertTrue(export_value("sword")["success"])
            missing = export_value("missing")
            self.assertFalse(missing["success"])
            self.assertIn("文件不存在", missing["issues"][0]["message"])
            traversal = export_value("../../outside")
            self.assertFalse(traversal["success"])
            self.assertTrue(any(
                "越过资源根目录" in issue["message"] for issue in traversal["issues"]
            ))

    def test_missing_asset_root_logs_one_warning_without_blocking_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            write_workbook(
                tables / "Item.xlsx",
                fields=(("id", "int", "CS"),), data_rows=((1,),),
                code_rows=(("Item", "Item.json", "c"),),
            )
            logs = []
            result = ExcelConverter(logs.append).export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )
            self.assertTrue(result["success"], result["issues"])
            self.assertEqual(sum("assetRoot" in line for line in logs), 1)
            self.assertFalse((tables / "TypeDefinition.xlsx").exists())
            self.assertFalse((root / "client").exists())
            self.assertFalse((root / "server").exists())

    def test_code_bytes_and_reference_failures_have_specific_issue_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            TypeDefinitionTemplate.ensure_exists(str(tables))
            workbook = load_workbook(tables / "TypeDefinition.xlsx")
            workbook["CODE"].append(("missing_ref", "find_id(Missing,Missing,id)", ""))
            workbook.save(tables / "TypeDefinition.xlsx")
            workbook.close()
            write_workbook(
                tables / "Bytes.xlsx",
                fields=(("id", "int", "CS"), ("payload", "bytes", "CS")),
                data_rows=((1, "raw"),), code_rows=(("Item", "Bytes.json", "c"),),
            )
            write_workbook(
                tables / "Reference.xlsx",
                fields=(("id", "int", "CS"), ("target", "missing_ref", "CS")),
                data_rows=((1, 99),), code_rows=(("Item", "Reference.json", "c"),),
            )
            write_workbook(
                tables / "NoCode.xlsx",
                fields=(("id", "int", "CS"),), data_rows=((1,),), code_rows=None,
            )
            write_workbook(
                tables / "BadFormat.xlsx",
                fields=(("id", "int", "CS"),), data_rows=((1,),),
                code_rows=(("Item", "BadFormat.csv", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            codes = {issue["code"] for issue in result["issues"]}
            self.assertTrue({
                "BYTES_FORMAT_ERROR", "REFERENCE_TABLE_ERROR",
                "MISSING_CODE", "UNKNOWN_OUTPUT_FORMAT",
            }.issubset(codes), result["issues"])

    def test_primary_key_must_be_scalar_and_exported_to_every_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            write_workbook(
                tables / "Platform.xlsx",
                fields=(("id", "int", "C"), ("value", "str", "CS")),
                data_rows=((None, None), (1, "kept")),
                code_rows=(("Item", "Platform.json", "cs"),),
            )
            write_workbook(
                tables / "ListKey.xlsx",
                fields=(("ids", "intList", "CS"), ("value", "str", "CS")),
                data_rows=(("1#2", "bad key"),),
                code_rows=(("Item", "ListKey.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "cs", validation_only=True,
            )

            codes = {issue["code"] for issue in result["issues"]}
            self.assertIn("PRIMARY_KEY_NOT_EXPORTED", codes)
            self.assertIn("INVALID_PRIMARY_KEY", codes)
            self.assertNotIn("MISSING_PRIMARY_KEY", codes)
            invalid_type = next(
                issue for issue in result["issues"]
                if issue["code"] == "INVALID_PRIMARY_KEY"
            )
            self.assertEqual((invalid_type["row"], invalid_type["column"]), (2, 1))
            self.assertIn("intList", invalid_type["message"])
            self.assertIn("A2", invalid_type["message"])
            self.assertIn("int/string", invalid_type["message"])

    def test_repeated_row_errors_are_reported_once_per_field(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            write_workbook(
                tables / "Repeated.xlsx",
                fields=(
                    ("id", "int", "CS"),
                    ("count", "int", "CS"),
                    ("price", "int", "CS"),
                ),
                data_rows=tuple(
                    (row_id, f"bad-count-{row_id}", f"bad-price-{row_id}")
                    for row_id in range(1, 11)
                ),
                code_rows=(("Item", "Repeated.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            conversion_issues = [
                issue for issue in result["issues"]
                if issue["code"] == "CONVERSION_ERROR"
            ]
            self.assertEqual(len(conversion_issues), 2, result["issues"])
            self.assertEqual(
                {(issue["field"], issue["row"]) for issue in conversion_issues},
                {("count", 5), ("price", 5)},
            )

    def test_different_constraints_on_one_field_remain_separate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            write_workbook(
                tables / "Constraints.xlsx",
                fields=(
                    ("id", "int", "CS"),
                    ("value", "int+range(1,2)+regex(^[A-Z]+$)", "CS"),
                ),
                data_rows=((1, 3), (2, 1)),
                code_rows=(("Item", "Constraints.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            issues = [
                issue for issue in result["issues"]
                if issue["code"] == "CONSTRAINT_ERROR"
            ]
            self.assertEqual(len(issues), 2, result["issues"])
            self.assertEqual({issue["row"] for issue in issues}, {5, 6})
            self.assertTrue(any("闭区间" in issue["message"] for issue in issues))
            self.assertTrue(any("正则表达式" in issue["message"] for issue in issues))

    def test_repeated_missing_and_duplicate_primary_keys_report_first_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            write_workbook(
                tables / "Primary.xlsx",
                fields=(("id", "int", "CS"), ("value", "str", "CS")),
                data_rows=(
                    (None, "missing one"),
                    (None, "missing two"),
                    *((1, f"duplicate {index}") for index in range(20)),
                ),
                code_rows=(("Item", "Primary.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            missing = [
                issue for issue in result["issues"]
                if issue["code"] == "MISSING_PRIMARY_KEY"
            ]
            duplicate = [
                issue for issue in result["issues"]
                if issue["code"] == "DUPLICATE_VALUE"
            ]
            self.assertEqual(len(missing), 1, result["issues"])
            self.assertEqual(missing[0]["row"], 5)
            self.assertEqual(len(duplicate), 1, result["issues"])
            self.assertEqual(duplicate[0]["row"], 8)

    def test_repeated_missing_references_report_first_row_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            TypeDefinitionTemplate.ensure_exists(str(tables))
            workbook = load_workbook(tables / "TypeDefinition.xlsx")
            workbook["CODE"].append(
                ("item_ref", "find_id(Target,Target,id)", "")
            )
            workbook.save(tables / "TypeDefinition.xlsx")
            workbook.close()
            write_workbook(
                tables / "Target.xlsx",
                fields=(("id", "int", "CS"),),
                data_rows=((1,),),
                code_rows=(("Target", "Target.json", "c"),),
                sheet="Target",
            )
            write_workbook(
                tables / "Source.xlsx",
                fields=(("id", "int", "CS"), ("target_id", "item_ref", "CS")),
                data_rows=((10, 99), (11, 98), (12, 97)),
                code_rows=(("Source", "Source.json", "c"),),
                sheet="Source",
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            issues = [
                issue for issue in result["issues"]
                if issue["code"] == "REFERENCE_NOT_FOUND"
            ]
            self.assertEqual(len(issues), 1, result["issues"])
            self.assertEqual(
                (issues[0]["field"], issues[0]["row"], issues[0]["column"]),
                ("target_id", 5, 2),
            )
            self.assertIn("='99'", issues[0]["message"])


if __name__ == "__main__":
    unittest.main()
