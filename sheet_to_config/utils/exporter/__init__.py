# -*- coding: utf-8 -*-
"""
导表模块
将 Excel 配置表转换为程序可用的格式

特性：
- 严格类型验证（所有类型必须在TypeDefinition.xlsx中定义）
- 完整的分隔符支持（#、|、_等）
- 约束系统（len、len2、equalLen、coexist、leastOne等）
- 空值默认处理（int→0, float→0.0, list→[]）
"""
from .core import WorkSheet, Row, FieldInfo
from .reader import ExcelReader, CodeSheet
from .converter import ExcelConverter
from .template import TypeDefinitionTemplate
from .type_registry import TypeRegistry, UndefinedTypeError
from .constraints import ConstraintValidator, ConstraintError
from .protobuf_schema import ProtoSchema, ProtoSchemaError, ProtoSchemaParser
from .validation import ValidationIssue

__all__ = [
    'WorkSheet',
    'Row',
    'FieldInfo',
    'CodeSheet',
    'ExcelReader',
    'ExcelConverter',
    'TypeDefinitionTemplate',
    'TypeRegistry',
    'UndefinedTypeError',
    'ConstraintValidator',
    'ConstraintError',
    'ProtoSchema',
    'ProtoSchemaError',
    'ProtoSchemaParser',
    'ValidationIssue',
]
