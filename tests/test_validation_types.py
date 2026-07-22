import math
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from utils.exporter.constraints import ConstraintError, ConstraintValidator
from utils.exporter.expression import parse_field_type
from utils.exporter.type_registry import TypeRegistry, UndefinedTypeError
from utils.exporter.types import TypeConverter


def write_type_definition(path, definitions):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "CODE"
    worksheet.append(["类型名字", "调用函数", "说明"])
    for name, expression in definitions:
        worksheet.append([name, expression, ""])
    workbook.save(path / "TypeDefinition.xlsx")


class TypeValidationTests(unittest.TestCase):
    def test_field_type_parser_preserves_nested_constraint_arguments(self):
        parsed = parse_field_type(
            r"string+regex(^(foo|bar)\+[0-9]{1,3}$)+required()"
        )

        self.assertEqual(parsed.base_type, "string")
        self.assertEqual(parsed.constraints[0].name, "regex")
        self.assertEqual(parsed.constraints[0].args, (r"^(foo|bar)\+[0-9]{1,3}$",))
        self.assertEqual(parsed.constraints[1].name, "required")

    def test_constraints_use_raw_required_and_closed_range_and_full_regex(self):
        validator = ConstraintValidator()

        with self.assertRaisesRegex(ConstraintError, "不能为空"):
            validator.validate("required", [], "count", 0, {"count": 0}, {"count": ""})
        validator.validate("range", ["1", "3"], "count", 1, {}, {"count": 1})
        validator.validate("range", ["1", "3"], "count", 3, {}, {"count": 3})
        with self.assertRaisesRegex(ConstraintError, "范围"):
            validator.validate("range", ["1", "3"], "count", 4, {}, {"count": 4})
        validator.validate("regex", [r"A[0-9]+"], "code", "A12", {}, {"code": "A12"})
        with self.assertRaisesRegex(ConstraintError, "格式"):
            validator.validate("regex", [r"A[0-9]+"], "code", "xA12", {}, {"code": "xA12"})

    def test_equal_len_constraints_compare_converted_outer_shapes(self):
        validator = ConstraintValidator()
        row = {"left": [[1], [2]], "right": [[3], [4]]}
        validator.validate("equalLen", ["right"], "left", row["left"], row, row)
        validator.validate("equalLen2", ["right"], "left", row["left"], row, row)

        with self.assertRaisesRegex(ConstraintError, "外层"):
            validator.validate(
                "equalLen2", ["right"], "left", [[1], [2]],
                {"right": [[3]]}, {"right": [[3]]}
            )

    def test_scalar_conversions_reject_values_that_would_be_silently_changed(self):
        self.assertEqual(TypeConverter.to_int("1"), 1)
        self.assertEqual(TypeConverter.to_float("1.25"), 1.25)
        self.assertIs(TypeConverter.to_bool("off"), False)

        with self.assertRaisesRegex(ValueError, "整数"):
            TypeConverter.to_int("1.5")
        with self.assertRaisesRegex(ValueError, "布尔"):
            TypeConverter.to_bool("maybe")
        with self.assertRaisesRegex(ValueError, "有限"):
            TypeConverter.to_float(math.inf)

    def test_type_definition_supports_string_and_integer_enums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            table_dir = Path(temp_dir)
            write_type_definition(table_dir, [
                ("quality", "enum(string,白,绿,蓝)"),
                ("stage", "enum(int,1,2,3)"),
            ])

            registry = TypeRegistry(str(table_dir))

            self.assertEqual(registry.get_type("quality")["convert_func"]("绿"), "绿")
            self.assertEqual(registry.get_type("stage")["convert_func"]("2"), 2)
            with self.assertRaisesRegex(ValueError, "枚举"):
                registry.get_type("stage")["convert_func"]("4")

    def test_type_definition_rejects_unknown_functions_when_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            table_dir = Path(temp_dir)
            write_type_definition(table_dir, [("bad", "silently_guess(int)")])

            with self.assertRaisesRegex(UndefinedTypeError, "未知"):
                TypeRegistry(str(table_dir))

    def test_complex_types_reject_empty_items_and_require_exact_dict_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            table_dir = Path(temp_dir)
            write_type_definition(table_dir, [
                ("ids", "split_list(int)"),
                ("reward", "split_dict(int id;string name)"),
            ])
            registry = TypeRegistry(str(table_dir))
            ids = registry.get_type("ids")["convert_func"]
            reward = registry.get_type("reward")["convert_func"]

            self.assertEqual(ids("1#2"), [1, 2])
            with self.assertRaisesRegex(ValueError, "空"):
                ids("1##2")
            self.assertEqual(reward("1,Sword"), {"id": 1, "name": "Sword"})
            with self.assertRaisesRegex(ValueError, "数量"):
                reward("1")
            with self.assertRaisesRegex(ValueError, "未知"):
                reward("id:1;name:Sword;extra:x")


if __name__ == "__main__":
    unittest.main()
