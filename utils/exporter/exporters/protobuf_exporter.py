# -*- coding: utf-8 -*-
"""Strongly typed Protobuf exporter backed by dynamic descriptors."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from ..protobuf_schema import (
    PROTO_SCALAR_TYPES,
    ProtoField,
    ProtoMessage,
    ProtoSchema,
    ProtoSchemaError,
    extract_manifest,
    validate_compatible,
)
from ..csharp_generator import CSharpGenerationError, generate_csharp


class ProtobufExportError(Exception):
    """Raised when schema binding, serialization, or output fails."""


_MISSING = object()

_PROTO_DESCRIPTOR_TYPES = {
    "double": descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE,
    "float": descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT,
    "int32": descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
    "int64": descriptor_pb2.FieldDescriptorProto.TYPE_INT64,
    "uint32": descriptor_pb2.FieldDescriptorProto.TYPE_UINT32,
    "uint64": descriptor_pb2.FieldDescriptorProto.TYPE_UINT64,
    "sint32": descriptor_pb2.FieldDescriptorProto.TYPE_SINT32,
    "sint64": descriptor_pb2.FieldDescriptorProto.TYPE_SINT64,
    "fixed32": descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32,
    "fixed64": descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64,
    "sfixed32": descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32,
    "sfixed64": descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64,
    "bool": descriptor_pb2.FieldDescriptorProto.TYPE_BOOL,
    "string": descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    "bytes": descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,
}

_SIGNED_32 = {"int32", "sint32", "sfixed32"}
_UNSIGNED_32 = {"uint32", "fixed32"}
_SIGNED_64 = {"int64", "sint64", "sfixed64"}
_UNSIGNED_64 = {"uint64", "fixed64"}


class ProtobufExporter:
    """Render one schema and atomically export it to one or more targets."""

    def __init__(self, schema: ProtoSchema, source_file: str = ""):
        self.schema = schema
        self.source_file = source_file
        source_name = os.path.basename(source_file) if source_file else ""
        self.location_prefix = (
            f"[{source_name}:{schema.sheet}]" if source_name else schema.sheet
        )
        self._message_class = self._build_message_class()

    def serialize(self, rows: Iterable[Mapping[str, Any]]) -> bytes:
        row_values = list(rows)
        root = self._message_class()
        try:
            self._assign_field(
                root,
                self.schema.root_field,
                row_values,
                f"{self.location_prefix}.$rows",
            )
            return root.SerializeToString(deterministic=True)
        except ProtobufExportError:
            raise
        except Exception as exc:
            raise ProtobufExportError(
                f"{self.schema.sheet} Protobuf序列化失败: {exc}"
            ) from exc

    def export_targets(
        self,
        targets: Sequence[Tuple[str, str, Iterable[Mapping[str, Any]]]],
        allow_breaking_change: bool = False,
        csharp_target: str = "",
        export_pb: bool = True,
    ) -> List[str]:
        """Write schema and data as one transaction.

        ``allow_breaking_change`` must be explicitly selected by the caller;
        it rebuilds a managed protocol from the current Excel definition.
        """
        if not targets:
            raise ProtobufExportError("没有可写入的Protobuf目标")

        proto_text = self.schema.render_proto()
        new_manifest = self.schema.manifest()
        normalized_targets = [
            (str(Path(proto_path)), str(Path(pb_path)), list(rows))
            for proto_path, pb_path, rows in targets
        ]
        all_paths = [
            path
            for proto_path, pb_path, _ in normalized_targets
            for path in ((proto_path, pb_path) if export_pb else (proto_path,))
        ]
        if csharp_target:
            all_paths.append(str(Path(csharp_target)))
        if len(set(os.path.normcase(os.path.abspath(path)) for path in all_paths)) != len(
            all_paths
        ):
            raise ProtobufExportError("Protobuf客户端和服务端输出路径发生冲突")

        self._validate_existing_protocols(
            [proto_path for proto_path, _, _ in normalized_targets],
            new_manifest,
            allow_breaking_change,
        )

        output_payloads: List[Tuple[str, bytes]] = []
        proto_bytes = proto_text.encode("utf-8")
        for proto_path, pb_path, rows in normalized_targets:
            output_payloads.append((proto_path, proto_bytes))
            if export_pb:
                output_payloads.append((pb_path, self.serialize(rows)))
        if csharp_target:
            try:
                csharp_bytes = generate_csharp(
                    proto_text, csharp_target, f"{self.schema.sheet}.proto"
                )
            except CSharpGenerationError as exc:
                raise ProtobufExportError(str(exc)) from exc
            output_payloads.append((str(Path(csharp_target)), csharp_bytes))

        self._atomic_write_many(output_payloads)
        return all_paths

    def _build_message_class(self):
        file_descriptor = descriptor_pb2.FileDescriptorProto()
        file_descriptor.name = f"{self.schema.sheet}.proto"
        file_descriptor.package = self.schema.package
        file_descriptor.syntax = "proto3"
        file_descriptor.options.csharp_namespace = self.schema.csharp_namespace

        for message_name in self.schema._ordered_message_names():
            message = self.schema.messages[message_name]
            descriptor = file_descriptor.message_type.add()
            descriptor.name = message.name
            self._populate_descriptor_message(descriptor, message)

        try:
            pool = descriptor_pool.DescriptorPool()
            pool.Add(file_descriptor)
            full_name = f"{self.schema.package}.{self.schema.root_message}"
            return message_factory.GetMessageClass(
                pool.FindMessageTypeByName(full_name)
            )
        except Exception as exc:
            raise ProtobufExportError(
                f"PROTO[{self.schema.sheet}] 动态descriptor构建失败: {exc}"
            ) from exc

    def _populate_descriptor_message(
        self,
        descriptor: descriptor_pb2.DescriptorProto,
        message: ProtoMessage,
    ) -> None:
        for number in sorted(message.reserved_numbers):
            reserved_range = descriptor.reserved_range.add()
            reserved_range.start = number
            reserved_range.end = number + 1
        descriptor.reserved_name.extend(sorted(message.reserved_names))

        user_oneofs = []
        for proto_field in sorted(message.fields, key=lambda item: item.number):
            if proto_field.oneof and proto_field.oneof not in user_oneofs:
                user_oneofs.append(proto_field.oneof)
        oneof_indices: Dict[str, int] = {}
        field_names = {item.name for item in message.fields}
        used_oneof_names = set()
        for oneof_name in user_oneofs:
            oneof_indices[oneof_name] = len(descriptor.oneof_decl)
            descriptor.oneof_decl.add(name=oneof_name)
            used_oneof_names.add(oneof_name)

        for proto_field in sorted(message.fields, key=lambda item: item.number):
            field_descriptor = descriptor.field.add()
            field_descriptor.name = proto_field.name
            field_descriptor.number = proto_field.number
            field_descriptor.label = (
                descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                if proto_field.rule == "repeated"
                else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
            )

            if proto_field.type_name in PROTO_SCALAR_TYPES:
                field_descriptor.type = _PROTO_DESCRIPTOR_TYPES[proto_field.type_name]
            else:
                field_descriptor.type = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                field_descriptor.type_name = (
                    f".{self.schema.package}.{proto_field.type_name}"
                )

            if proto_field.oneof:
                field_descriptor.oneof_index = oneof_indices[proto_field.oneof]
            elif proto_field.rule == "optional":
                synthetic_name = f"_{proto_field.name}"
                while (
                    synthetic_name in used_oneof_names
                    or synthetic_name in field_names
                ):
                    synthetic_name = "_" + synthetic_name
                field_descriptor.oneof_index = len(descriptor.oneof_decl)
                descriptor.oneof_decl.add(name=synthetic_name)
                used_oneof_names.add(synthetic_name)
                field_descriptor.proto3_optional = True

    def _populate_message(
        self, message_object: Any, message_name: str, value: Any, path: str
    ) -> None:
        message = self.schema.messages[message_name]
        regular_fields = [item for item in message.fields if not item.oneof]
        for proto_field in regular_fields:
            resolved = _resolve_source(value, proto_field.source)
            if resolved is _MISSING or resolved is None:
                # Row字段可能因C/S平台过滤而缺失；嵌套结构则必须完整，
                # 只有显式optional字段可以省略。
                platform_omitted = (
                    message_name == self.schema.row_message.name
                    and _source_root_missing(value, proto_field.source)
                )
                if (
                    not platform_omitted
                    and proto_field.rule != "optional"
                ):
                    raise ProtobufExportError(
                        f"{path}.{proto_field.name} 缺少source: {proto_field.source}"
                    )
                continue
            self._assign_field(message_object, proto_field, resolved, path)

        oneof_groups: Dict[str, List[ProtoField]] = {}
        for proto_field in message.fields:
            if proto_field.oneof:
                oneof_groups.setdefault(proto_field.oneof, []).append(proto_field)

        for oneof_name, candidates in oneof_groups.items():
            present_values = []
            matching = []
            for proto_field in candidates:
                resolved = _resolve_source(value, proto_field.source)
                if resolved is _MISSING or resolved is None:
                    continue
                present_values.append((proto_field, resolved))
                if self._value_matches_field(proto_field, resolved):
                    matching.append((proto_field, resolved))
            if not present_values:
                continue
            if len(matching) != 1:
                candidate_names = ", ".join(item.name for item in candidates)
                raise ProtobufExportError(
                    f"{path}.{oneof_name} 无法唯一选择oneof分支，候选: {candidate_names}"
                )
            proto_field, resolved = matching[0]
            self._assign_field(message_object, proto_field, resolved, path)

    def _assign_field(
        self, message_object: Any, proto_field: ProtoField, value: Any, path: str
    ) -> None:
        field_path = f"{path}.{proto_field.name}"
        is_message = proto_field.type_name not in PROTO_SCALAR_TYPES

        if proto_field.rule == "repeated":
            if not _is_sequence(value):
                raise ProtobufExportError(
                    f"{field_path} 需要列表，实际为 {type(value).__name__}"
                )
            container = getattr(message_object, proto_field.name)
            if is_message:
                for index, item in enumerate(value):
                    child = container.add()
                    item_path = (
                        f"{self.location_prefix} 第{getattr(item, 'excel_row', index + 5)}行"
                        if proto_field.kind == "root"
                        else f"{field_path}[{index}]"
                    )
                    self._populate_message(
                        child, proto_field.type_name, item, item_path
                    )
            else:
                for index, item in enumerate(value):
                    container.append(
                        self._coerce_scalar(
                            proto_field.type_name, item, f"{field_path}[{index}]"
                        )
                    )
            return

        if is_message:
            child = getattr(message_object, proto_field.name)
            self._populate_message(child, proto_field.type_name, value, field_path)
            child.SetInParent()
        else:
            setattr(
                message_object,
                proto_field.name,
                self._coerce_scalar(proto_field.type_name, value, field_path),
            )

    def _value_matches_field(self, proto_field: ProtoField, value: Any) -> bool:
        if proto_field.type_name not in PROTO_SCALAR_TYPES:
            message = self.schema.messages[proto_field.type_name]
            if isinstance(value, Mapping):
                return True
            return any(item.source == "$self" for item in message.fields)
        try:
            self._coerce_scalar(proto_field.type_name, value, proto_field.name)
            return True
        except ProtobufExportError:
            return False

    @staticmethod
    def _coerce_scalar(type_name: str, value: Any, path: str) -> Any:
        if isinstance(value, Mapping):
            # TypeDefinition find_id values retain display metadata in a
            # dictionary; protobuf fields carry only the referenced ID scalar.
            candidates = [item for key, item in value.items() if not str(key).startswith("_")]
            value = candidates[0] if candidates else None
        if type_name == "bool":
            if type(value) is not bool:
                raise ProtobufExportError(f"{path} 需要bool")
            return value
        if type_name == "string":
            if not isinstance(value, str):
                raise ProtobufExportError(f"{path} 需要string")
            return value
        if type_name == "bytes":
            if not isinstance(value, (bytes, bytearray)):
                raise ProtobufExportError(f"{path} 需要bytes")
            return bytes(value)
        if type_name in ("float", "double"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProtobufExportError(f"{path} 需要数值")
            return float(value)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProtobufExportError(f"{path} 需要整数")

        if type_name in _SIGNED_32:
            minimum, maximum = -(2**31), 2**31 - 1
        elif type_name in _UNSIGNED_32:
            minimum, maximum = 0, 2**32 - 1
        elif type_name in _SIGNED_64:
            minimum, maximum = -(2**63), 2**63 - 1
        elif type_name in _UNSIGNED_64:
            minimum, maximum = 0, 2**64 - 1
        else:
            raise ProtobufExportError(f"{path} 使用了不支持的标量类型: {type_name}")
        if value < minimum or value > maximum:
            raise ProtobufExportError(
                f"{path}={value} 超出{type_name}范围 [{minimum}, {maximum}]"
            )
        return value

    @staticmethod
    def _validate_existing_protocols(
        proto_paths: Iterable[str], new_manifest: Dict[str, Any],
        allow_breaking_change: bool = False,
    ) -> None:
        for proto_path in proto_paths:
            if not os.path.exists(proto_path):
                continue
            try:
                with open(proto_path, "r", encoding="utf-8") as file:
                    old_manifest = extract_manifest(file.read())
                if old_manifest is None:
                    raise ProtobufExportError(
                        f"已有协议不是本工具管理的文件，拒绝覆盖: {proto_path}"
                    )
                if not allow_breaking_change:
                    validate_compatible(old_manifest, new_manifest)
            except ProtoSchemaError as exc:
                raise ProtobufExportError(f"{proto_path}: {exc}") from exc

    @staticmethod
    def _atomic_write_many(outputs: Sequence[Tuple[str, bytes]]) -> None:
        temp_files: Dict[str, str] = {}
        backup_files: Dict[str, str | None] = {}
        replaced = []
        preserved_backups = set()
        try:
            for output_path, payload in outputs:
                parent = os.path.dirname(output_path) or "."
                os.makedirs(parent, exist_ok=True)
                handle, temp_path = tempfile.mkstemp(
                    prefix=f".{os.path.basename(output_path)}.",
                    suffix=".tmp",
                    dir=parent,
                )
                with os.fdopen(handle, "wb") as file:
                    file.write(payload)
                    file.flush()
                    os.fsync(file.fileno())
                temp_files[output_path] = temp_path

            for output_path, _ in outputs:
                if os.path.exists(output_path):
                    handle, backup_path = tempfile.mkstemp(
                        prefix=f".{os.path.basename(output_path)}.",
                        suffix=".bak",
                        dir=os.path.dirname(output_path) or ".",
                    )
                    os.close(handle)
                    shutil.copy2(output_path, backup_path)
                    backup_files[output_path] = backup_path
                else:
                    backup_files[output_path] = None

            for output_path, _ in outputs:
                os.replace(temp_files[output_path], output_path)
                temp_files.pop(output_path, None)
                replaced.append(output_path)
        except Exception as exc:
            rollback_errors = []
            for output_path in reversed(replaced):
                backup_path = backup_files.get(output_path)
                try:
                    if backup_path and os.path.exists(backup_path):
                        os.replace(backup_path, output_path)
                        backup_files[output_path] = None
                    elif os.path.exists(output_path):
                        os.remove(output_path)
                except Exception as rollback_exc:
                    rollback_errors.append(f"{output_path}: {rollback_exc}")
                    if backup_path and os.path.exists(backup_path):
                        preserved_backups.add(backup_path)

            if rollback_errors:
                backup_hint = ", ".join(sorted(preserved_backups)) or "无可用备份"
                raise ProtobufExportError(
                    "Protobuf输出写入失败且回滚不完整；"
                    f"恢复备份保留在: {backup_hint}; "
                    + "; ".join(rollback_errors)
                ) from exc
            raise ProtobufExportError(
                f"Protobuf输出写入失败，旧文件已恢复: {exc}"
            ) from exc
        finally:
            for temp_path in temp_files.values():
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            for backup_path in backup_files.values():
                if (
                    backup_path
                    and backup_path not in preserved_backups
                    and os.path.exists(backup_path)
                ):
                    os.remove(backup_path)


def _resolve_source(value: Any, source: str) -> Any:
    if source in ("$self", "$rows"):
        return value
    current = value
    for part in source.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _source_root_missing(value: Any, source: str) -> bool:
    if source.startswith("$") or not isinstance(value, Mapping):
        return False
    return source.split(".", 1)[0] not in value


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
