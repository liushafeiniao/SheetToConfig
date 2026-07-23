import tempfile
import unittest
from pathlib import Path

from sheet_to_config.utils.exporter.constraints import ConstraintError, ConstraintValidator
from sheet_to_config.utils.exporter.converter import ExcelConverter
from sheet_to_config.utils.exporter.template import TypeDefinitionTemplate
from tests.workbook_factory import write_workbook


class ConstraintExampleTests(unittest.TestCase):
    def setUp(self):
        self.validator = ConstraintValidator()

    def _validate(self, name, params, field_value, row=None, raw=None):
        row = {"value": field_value} if row is None else row
        raw = row if raw is None else raw
        self.validator.validate(name, params, "value", field_value, row, raw)

    def test_len_len2_and_len3_cover_minimum_and_range_semantics(self):
        self._validate("len", ["2"], [1, 2, 3])
        with self.assertRaises(ConstraintError):
            self._validate("len", ["2"], [1])
        self._validate("len", ["1", "3"], [1, 2, 3])
        with self.assertRaises(ConstraintError):
            self._validate("len", ["1", "3"], [1, 2, 3, 4])

        self._validate("len2", ["1", "2"], [[1], [2, 3]])
        with self.assertRaises(ConstraintError):
            self._validate("len2", ["1", "2"], [[1, 2, 3]])

        self._validate("len3", ["1", "2"], [[[1], [2, 3]]])
        with self.assertRaises(ConstraintError):
            self._validate("len3", ["1", "2"], [[[1, 2, 3]]])

    def test_coexist_least_one_required_and_not_empty_match_documented_behavior(self):
        self._validate(
            "coexist", ["other"], "x",
            {"value": "x", "other": "y"}, {"value": "x", "other": "y"},
        )
        with self.assertRaises(ConstraintError):
            self._validate(
                "coexist", ["other"], "x",
                {"value": "x", "other": ""}, {"value": "x", "other": ""},
            )

        self._validate(
            "leastOne", ["email", "phone"], "",
            {"value": "", "email": "a@b.com", "phone": ""},
            {"value": "", "email": "a@b.com", "phone": ""},
        )
        with self.assertRaises(ConstraintError):
            self._validate(
                "leastOne", ["email", "phone"], "",
                {"value": "", "email": "", "phone": ""},
                {"value": "", "email": "", "phone": ""},
            )

        for name in ("required", "notEmpty"):
            with self.subTest(name=name), self.assertRaises(ConstraintError):
                self._validate(name, [], 0, {"value": 0}, {"value": "  "})

    def test_invalid_constraint_definitions_are_rejected_early(self):
        invalid = (
            ("len", []),
            ("len2", ["1", "2", "3"]),
            ("len3", ["-1"]),
            ("len", ["3", "1"]),
            ("coexist", []),
            ("leastOne", []),
            ("required", ["extra"]),
            ("range", ["0", "nan"]),
            ("regex", ["["]),
        )
        for name, params in invalid:
            with self.subTest(name=name, params=params), self.assertRaises(ConstraintError):
                self.validator.validate_definition(name, params)

    def test_unique_constraint_applies_to_a_non_primary_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tables = root / "tables"
            tables.mkdir()
            TypeDefinitionTemplate.ensure_exists(str(tables), locale="en")
            write_workbook(
                tables / "Unique.xlsx",
                fields=(("id", "int", "CS"), ("code", "string+unique()", "CS")),
                data_rows=((1, "same"), (2, "same")),
                code_rows=(("Item", "Unique.json", "c"),),
            )

            result = ExcelConverter().export_all(
                str(tables), str(root / "client"), str(root / "server"),
                "c", validation_only=True,
            )

            duplicates = [
                issue for issue in result["issues"]
                if issue["code"] == "DUPLICATE_VALUE" and issue["field"] == "code"
            ]
            self.assertFalse(result["success"], result["issues"])
            self.assertEqual(1, len(duplicates), result["issues"])
            self.assertIn("唯一字段", duplicates[0]["message"])


if __name__ == "__main__":
    unittest.main()
