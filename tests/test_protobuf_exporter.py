import tempfile
import unittest
from pathlib import Path
from unittest import mock

from utils.exporter.exporters.protobuf_exporter import (
    ProtobufExporter,
    ProtobufExportError,
)
from utils.exporter.protobuf_schema import ProtoSchemaParser

from tests.workbook_factory import write_workbook


def complex_proto_rows():
    return [
        ("root", "Item", "ItemTable", "rows", 1, "ItemRow", "repeated", "", "$rows", ""),
        ("field", "Item", "ItemRow", "id", 1, "int32", "singular", "", "id", ""),
        ("field", "Item", "ItemRow", "values", 2, "int32", "repeated", "", "values", ""),
        ("field", "Item", "ItemRow", "matrix", 3, "IntList", "repeated", "", "matrix", ""),
        ("field", "Item", "ItemRow", "cube", 4, "IntList2", "repeated", "", "cube", ""),
        ("field", "Item", "ItemRow", "stats", 5, "Stats", "singular", "", "stats", ""),
        ("field", "Item", "ItemRow", "key_number", 6, "int64", "singular", "key_value", "key", ""),
        ("field", "Item", "ItemRow", "key_text", 7, "string", "singular", "key_value", "key", ""),
        ("field", "Item", "ItemRow", "enabled", 8, "bool", "optional", "", "enabled", ""),
        ("field", "Item", "IntList", "values", 1, "int32", "repeated", "", "$self", ""),
        ("field", "Item", "IntList2", "values", 1, "IntList", "repeated", "", "$self", ""),
        ("field", "Item", "Stats", "score", 1, "int32", "singular", "", "score", ""),
    ]


def scalar_proto_rows():
    scalar_types = (
        "double",
        "float",
        "int32",
        "int64",
        "uint32",
        "uint64",
        "sint32",
        "sint64",
        "fixed32",
        "fixed64",
        "sfixed32",
        "sfixed64",
        "bool",
        "string",
        "bytes",
    )
    rows = [
        ("root", "Item", "ScalarTable", "rows", 1, "ScalarRow", "repeated", "", "$rows", "")
    ]
    rows.extend(
        ("field", "Item", "ScalarRow", type_name, index, type_name, "singular", "", type_name, "")
        for index, type_name in enumerate(scalar_types, start=1)
    )
    return rows


class ProtobufExporterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _schema(self, proto_rows):
        path = write_workbook(
            self.root / "Schema.xlsx",
            fields=(("id", "int", "CS"),),
            data_rows=((1,),),
            proto_rows=proto_rows,
        )
        return ProtoSchemaParser.parse_workbook(str(path), "Item")

    @staticmethod
    def _decode(exporter, payload):
        message = exporter._message_class()
        message.ParseFromString(payload)
        return message

    def test_serializes_repeated_nested_messages_dictionary_and_oneof(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        rows = [
            {
                "id": 1,
                "values": [5, 8],
                "matrix": [[1, 2], [3]],
                "cube": [[[1], [2, 3]], [[4]]],
                "stats": {"score": 99},
                "key": 1234567890123,
                "enabled": True,
            },
            {"id": 2, "values": [], "matrix": [], "cube": [], "key": "sword"},
        ]

        decoded = self._decode(exporter, exporter.serialize(rows))

        self.assertEqual([1, 2], [row.id for row in decoded.rows])
        self.assertEqual([5, 8], list(decoded.rows[0].values))
        self.assertEqual([1, 2], list(decoded.rows[0].matrix[0].values))
        self.assertEqual([2, 3], list(decoded.rows[0].cube[0].values[1].values))
        self.assertEqual(99, decoded.rows[0].stats.score)
        self.assertEqual("key_number", decoded.rows[0].WhichOneof("key_value"))
        self.assertEqual(1234567890123, decoded.rows[0].key_number)
        self.assertEqual("key_text", decoded.rows[1].WhichOneof("key_value"))
        self.assertEqual("sword", decoded.rows[1].key_text)
        self.assertTrue(decoded.rows[0].HasField("enabled"))
        self.assertFalse(decoded.rows[1].HasField("enabled"))

    def test_supports_every_proto_scalar_type(self):
        exporter = ProtobufExporter(self._schema(scalar_proto_rows()))
        values = {
            "double": 1.25,
            "float": 2.5,
            "int32": -(2**31),
            "int64": -(2**63),
            "uint32": 2**32 - 1,
            "uint64": 2**64 - 1,
            "sint32": -17,
            "sint64": -(2**40),
            "fixed32": 2**32 - 1,
            "fixed64": 2**64 - 1,
            "sfixed32": -(2**31),
            "sfixed64": -(2**63),
            "bool": True,
            "string": "Sword",
            "bytes": b"\x00\xff",
        }

        decoded = self._decode(exporter, exporter.serialize([values])).rows[0]

        for name, expected in values.items():
            with self.subTest(type_name=name):
                actual = getattr(decoded, name)
                if name in ("float", "double"):
                    self.assertAlmostEqual(expected, actual, places=5)
                else:
                    self.assertEqual(expected, actual)

    def test_rejects_scalar_overflow_with_data_location(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))

        with self.assertRaisesRegex(ProtobufExportError, "Item.*5.*id.*int32"):
            exporter.serialize([{"id": 2**31, "key": "valid"}])

    def test_rejects_ambiguous_oneof_value(self):
        rows = [
            ("root", "Item", "ItemTable", "rows", 1, "ItemRow", "repeated", "", "$rows", ""),
            ("field", "Item", "ItemRow", "signed_key", 1, "int64", "singular", "key_value", "key", ""),
            ("field", "Item", "ItemRow", "unsigned_key", 2, "uint64", "singular", "key_value", "key", ""),
        ]
        exporter = ProtobufExporter(self._schema(rows))

        with self.assertRaisesRegex(ProtobufExportError, "oneof"):
            exporter.serialize([{"key": 1}])

    def test_optional_synthetic_oneof_avoids_field_name_collision(self):
        rows = [
            ("root", "Item", "ItemTable", "rows", 1, "ItemRow", "repeated", "", "$rows", ""),
            ("field", "Item", "ItemRow", "foo", 1, "int32", "optional", "", "foo", ""),
            ("field", "Item", "ItemRow", "_foo", 2, "int32", "singular", "", "other", ""),
        ]
        exporter = ProtobufExporter(self._schema(rows))

        decoded = self._decode(exporter, exporter.serialize([{"foo": 1, "other": 2}]))

        self.assertTrue(decoded.rows[0].HasField("foo"))
        self.assertEqual(2, decoded.rows[0]._foo)

    def test_rejects_missing_nested_dictionary_source(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))

        with self.assertRaisesRegex(ProtobufExportError, "stats.score.*source"):
            exporter.serialize(
                [{"id": 1, "values": [], "matrix": [], "cube": [], "stats": {}, "key": "ok"}]
            )

    def test_exports_shared_proto_and_platform_specific_data_in_row_order(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        client_proto = self.root / "client" / "Item.proto"
        client_pb = self.root / "client" / "Item.pb"
        server_proto = self.root / "server" / "Item.proto"
        server_pb = self.root / "server" / "Item.pb"

        written = exporter.export_targets(
            [
                (str(client_proto), str(client_pb), [{"id": 2, "key": "c"}, {"id": 1, "key": "c2"}]),
                (str(server_proto), str(server_pb), [{"id": 2, "key": 20}, {"id": 1, "key": 10}]),
            ]
        )

        self.assertEqual(4, len(written))
        self.assertEqual(client_proto.read_bytes(), server_proto.read_bytes())
        self.assertNotEqual(client_pb.read_bytes(), server_pb.read_bytes())
        client = self._decode(exporter, client_pb.read_bytes())
        server = self._decode(exporter, server_pb.read_bytes())
        self.assertEqual([2, 1], [row.id for row in client.rows])
        self.assertEqual([2, 1], [row.id for row in server.rows])
        self.assertEqual("key_text", client.rows[0].WhichOneof("key_value"))
        self.assertEqual("key_number", server.rows[0].WhichOneof("key_value"))

    def test_unmanaged_proto_or_serialization_error_preserves_old_outputs(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        proto_path = self.root / "Item.proto"
        pb_path = self.root / "Item.pb"
        proto_path.write_text('syntax = "proto3";\n', encoding="utf-8")
        pb_path.write_bytes(b"old-pb")

        with self.assertRaisesRegex(ProtobufExportError, "拒绝覆盖"):
            exporter.export_targets(
                [(str(proto_path), str(pb_path), [{"id": 1, "key": "sword"}])]
            )
        self.assertEqual('syntax = "proto3";\n', proto_path.read_text(encoding="utf-8"))
        self.assertEqual(b"old-pb", pb_path.read_bytes())

        proto_path.write_text(exporter.schema.render_proto(), encoding="utf-8")
        with self.assertRaises(ProtobufExportError):
            exporter.export_targets(
                [(str(proto_path), str(pb_path), [{"id": 2**31, "key": "sword"}])]
            )
        self.assertEqual(exporter.schema.render_proto(), proto_path.read_text(encoding="utf-8"))
        self.assertEqual(b"old-pb", pb_path.read_bytes())

    def test_write_failure_rolls_back_every_replaced_file(self):
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        proto_path = self.root / "Item.proto"
        pb_path = self.root / "Item.pb"
        exporter.export_targets(
            [(str(proto_path), str(pb_path), [{"id": 1, "key": "old"}])]
        )
        old_proto = proto_path.read_bytes()
        old_pb = pb_path.read_bytes()
        real_replace = __import__("os").replace
        replace_count = 0

        def fail_second_replace(source, target):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("injected replace failure")
            return real_replace(source, target)

        with mock.patch(
            "utils.exporter.exporters.protobuf_exporter.os.replace",
            side_effect=fail_second_replace,
        ):
            with self.assertRaisesRegex(ProtobufExportError, "旧文件已恢复"):
                exporter.export_targets(
                    [(str(proto_path), str(pb_path), [{"id": 2, "key": "new"}])]
                )

        self.assertEqual(old_proto, proto_path.read_bytes())
        self.assertEqual(old_pb, pb_path.read_bytes())

    def test_staged_client_then_shared_schema_upgrade_converges(self):
        client_proto = self.root / "client" / "Item.proto"
        client_pb = self.root / "client" / "Item.pb"
        server_proto = self.root / "server" / "Item.proto"
        server_pb = self.root / "server" / "Item.pb"
        base_rows = complex_proto_rows()

        v1 = ProtobufExporter(self._schema(base_rows))
        v1.export_targets(
            [
                (str(client_proto), str(client_pb), [{"id": 1, "key": "c"}]),
                (str(server_proto), str(server_pb), [{"id": 1, "key": 1}]),
            ]
        )

        v2_rows = [
            *base_rows,
            ("field", "Item", "ItemRow", "v2", 9, "string", "singular", "", "v2", ""),
        ]
        v2 = ProtobufExporter(self._schema(v2_rows))
        v2.export_targets(
            [(str(client_proto), str(client_pb), [{"id": 1, "key": "c", "v2": "yes"}])]
        )
        self.assertNotEqual(client_proto.read_bytes(), server_proto.read_bytes())

        v3_rows = [
            *v2_rows,
            ("field", "Item", "ItemRow", "v3", 10, "int32", "singular", "", "v3", ""),
        ]
        v3 = ProtobufExporter(self._schema(v3_rows))
        v3.export_targets(
            [
                (str(client_proto), str(client_pb), [{"id": 1, "key": "c", "v2": "yes", "v3": 3}]),
                (str(server_proto), str(server_pb), [{"id": 1, "key": 1, "v2": "yes", "v3": 3}]),
            ]
        )

        self.assertEqual(client_proto.read_bytes(), server_proto.read_bytes())

    def test_optional_csharp_generation_requires_protoc_and_is_atomic(self):
        proto_path = self.root / "client" / "Item.proto"
        pb_path = self.root / "client" / "Item.pb"
        csharp_path = self.root / "unity" / "Item.cs"
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        with mock.patch(
            "utils.exporter.csharp_generator.shutil.which", return_value=None
        ), mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ProtobufExportError, "找不到protoc"):
                exporter.export_targets(
                    [(str(proto_path), str(pb_path), [{"id": 1, "key": "x"}])],
                    csharp_target=str(csharp_path),
                )
        self.assertFalse(proto_path.exists())
        self.assertFalse(pb_path.exists())
        self.assertFalse(csharp_path.exists())

    def test_optional_csharp_generation_writes_to_independent_target(self):
        proto_path = self.root / "client" / "Item.proto"
        pb_path = self.root / "client" / "Item.pb"
        csharp_path = self.root / "unity" / "Item.cs"
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        with mock.patch(
            "utils.exporter.exporters.protobuf_exporter.generate_csharp",
            return_value=b"// generated C#\n",
        ):
            written = exporter.export_targets(
                [(str(proto_path), str(pb_path), [{"id": 1, "key": "x"}])],
                csharp_target=str(csharp_path),
            )
        self.assertIn(str(csharp_path), written)
        self.assertEqual(b"// generated C#\n", csharp_path.read_bytes())

    def test_pb_export_can_be_disabled_without_deleting_existing_binary(self):
        proto_path = self.root / "client" / "Item.proto"
        pb_path = self.root / "client" / "Item.pb"
        pb_path.parent.mkdir(parents=True, exist_ok=True)
        pb_path.write_bytes(b"old-pb")
        exporter = ProtobufExporter(self._schema(complex_proto_rows()))
        exporter.export_targets(
            [(str(proto_path), str(pb_path), [{"id": 1, "key": "x"}])],
            export_pb=False,
        )
        self.assertTrue(proto_path.exists())
        self.assertEqual(b"old-pb", pb_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
