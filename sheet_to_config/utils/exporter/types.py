# -*- coding: utf-8 -*-
"""
类型转换模块
defines data types and conversion functions
支持复杂的嵌套类型语法，如:
- split_list(int) - 逗号分隔的整数列表
- split_list[_](string) - 下划线分隔的字符串列表
- split_list2(split_list(int)) - 二维列表
- split_dict(find_id(item,道具,id) id;int minNum;int maxNum;int chance) - 字典
- path(res/spine/role.json) - 路径处理
- find_id(item,物品表,id) - 关联表查找
"""
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, List, Dict, Optional, Callable


class TypeConverter:
    """类型转换器"""

    # 分隔符映射表
    SEPARATOR_MAP = {
        '_': '_',
        '|': '|',
    }

    @staticmethod
    def to_string(value: Any) -> str:
        """转字符串"""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        """转整数"""
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"无法将 '{value}' 转换为整数")
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f"'{value}' 不是有效整数")
        return int(number)

    @staticmethod
    def to_float(value: Any, default: float = 0.0) -> float:
        """转浮点数"""
        if value is None or value == "":
            return default
        try:
            result = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"无法将 '{value}' 转换为浮点数")
        if not math.isfinite(result):
            raise ValueError(f"'{value}' 不是有限浮点数")
        return result

    @staticmethod
    def to_bool(value: Any) -> bool:
        """转布尔值"""
        if value is None or value == "":
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"'{value}' 不是有效布尔值")
        val_str = str(value).strip().lower()
        if val_str in ('1', 'true', 'yes', 'on'):
            return True
        if val_str in ('0', 'false', 'no', 'off'):
            return False
        raise ValueError(f"'{value}' 不是有效布尔值")

    @staticmethod
    def to_bytes(value: Any) -> bytes:
        """Convert Excel text to UTF-8 bytes for Protobuf bytes fields."""
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        return str(value).encode("utf-8")

    @staticmethod
    def split_list(value: Any, item_type='string', separator: str = ',') -> list:
        """
        分割列表
        :param value: 原始值
        :param item_type: 元素类型 (int, float, string) 或转换函数
        :param separator: 分隔符，默认为逗号
        """
        if value is None or value == "":
            return []
        # Check whether the element definition is a nested converter.
        is_callable = callable(item_type) and not isinstance(item_type, str)

        if isinstance(value, list):
            parts = value
        # 如果是单个数值（int/float），包装成列表
        elif isinstance(value, (int, float)):
            val = value
            if is_callable:
                return [item_type(val)]
            elif item_type == 'int':
                return [TypeConverter.to_int(val)]
            elif item_type == 'float':
                return [float(val)]
            else:  # string
                return [str(val)]

        else:
            parts = str(value).split(separator)
        result = []

        for p in parts:
            p = p.strip() if isinstance(p, str) else p
            if p is None or (isinstance(p, str) and not p):
                raise ValueError("列表中存在空元素")
            if is_callable:
                # item_type 是转换函数
                result.append(item_type(p))
            elif item_type == 'int':
                result.append(TypeConverter.to_int(p))
            elif item_type == 'float':
                result.append(TypeConverter.to_float(p))
            elif item_type == 'bool':
                result.append(TypeConverter.to_bool(p))
            else:  # string
                result.append(p)

        return result

    @staticmethod
    def split_list2(value: Any, item_converter: Optional[Callable] = None) -> list:
        """
        分割二维列表（使用 | 分隔外层，# 分隔内层）
        支持嵌套函数调用，如 split_list2(split_list(find(...)))
        :param value: 原始值
        :param item_converter: 元素转换函数（可以是嵌套的 split_list/find 等）
        """
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value

        # 第一层用 | 分隔（外层）
        outer_parts = str(value).split('|')
        if any(not part.strip() for part in outer_parts):
            raise ValueError("二维列表中存在空分组")
        result = []

        for outer_part in outer_parts:
            outer_part = outer_part.strip()
            # 第二层用 # 分隔（内层）
            inner_parts = outer_part.split('#')
            if any(not part.strip() for part in inner_parts):
                raise ValueError("二维列表中存在空元素")
            inner_result = []
            
            for inner_part in inner_parts:
                inner_part = inner_part.strip()
                if item_converter:
                    # 调用转换函数处理内层元素
                    converted = item_converter(inner_part)
                    # 如果转换结果是列表（如 split_list 返回的），直接扩展
                    if isinstance(converted, list):
                        inner_result.extend(converted)
                    else:
                        inner_result.append(converted)
                else:
                    inner_result.append(inner_part)
            
            result.append(inner_result)

        return result

    @staticmethod
    def split_list3(value: Any, item_converter: Optional[Callable] = None) -> list:
        """
        分割三维列表（使用 _ 分隔最外层，| 分隔中层，# 分隔内层）
        :param value: 原始值
        :param item_converter: 元素转换函数
        """
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value

        # 第一层用 _ 分隔（最外层）
        outer_parts = str(value).split('_')
        if any(not part.strip() for part in outer_parts):
            raise ValueError("三维列表中存在空分组")
        result = []

        for outer_part in outer_parts:
            outer_part = outer_part.strip()
            # 第二层用 | 分隔（中层）
            mid_parts = outer_part.split('|')
            if any(not part.strip() for part in mid_parts):
                raise ValueError("三维列表中存在空分组")
            mid_result = []
            
            for mid_part in mid_parts:
                mid_part = mid_part.strip()
                # 第三层用 # 分隔（内层）
                inner_parts = mid_part.split('#')
                if any(not part.strip() for part in inner_parts):
                    raise ValueError("三维列表中存在空元素")
                inner_result = []
                
                for inner_part in inner_parts:
                    inner_part = inner_part.strip()
                    if item_converter:
                        converted = item_converter(inner_part)
                        if isinstance(converted, list):
                            inner_result.extend(converted)
                        else:
                            inner_result.append(converted)
                    else:
                        inner_result.append(inner_part)
                
                mid_result.append(inner_result)
            
            result.append(mid_result)

        return result

    @staticmethod
    def split_dict(value: Any, *field_defs) -> dict:
        """
        分割字典
        :param value: 原始值，格式如 "id:1;name:test" 或 "1;test"
        :param field_defs: 字段定义，格式如 "id:int", "name:string"
        """
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            return value

        result = {}

        # 解析字段定义
        fields = []
        for fd in field_defs:
            if isinstance(fd, str):
                if ':' in fd:
                    name, ftype = fd.split(':', 1)
                    fields.append((name.strip(), ftype.strip()))
                else:
                    fields.append((fd.strip(), 'string'))

        # 分割键值对（使用分号或逗号分隔）
        if ';' in str(value):
            pairs = str(value).split(';')
        else:
            pairs = str(value).split(',')

        for i, pair in enumerate(pairs):
            pair = pair.strip()
            if not pair:
                continue

            if ':' in pair:
                # 格式: key:value
                k, v = pair.split(':', 1)
                k = k.strip()
                v = v.strip()
            else:
                # 无 key，使用字段定义中的名称
                if i < len(fields):
                    k = fields[i][0]
                    v = pair
                else:
                    continue

            # 根据类型转换值
            if i < len(fields):
                ftype = fields[i][1]
                if ftype == 'int':
                    try:
                        v = int(float(v))
                    except (ValueError, TypeError):
                        v = 0
                elif ftype == 'float':
                    try:
                        v = float(v)
                    except (ValueError, TypeError):
                        v = 0.0
                elif ftype == 'bool':
                    v = TypeConverter.to_bool(v)

            result[k] = v

        return result

    @staticmethod
    def split_dict_fields(value: Any, fields: list[tuple[str, Callable]]) -> dict:
        """Convert a strict positional or named compact dictionary."""
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            raw_values = dict(value)
            unknown = set(raw_values) - {name for name, _ in fields}
            missing = {name for name, _ in fields} - set(raw_values)
            if unknown:
                raise ValueError(f"字典包含未知字段: {', '.join(sorted(unknown))}")
            if missing:
                raise ValueError(f"字典缺少字段: {', '.join(sorted(missing))}")
        else:
            source = str(value).strip()
            separator = ';' if ';' in source else ','
            parts = [part.strip() for part in source.split(separator)]
            if any(not part for part in parts):
                raise ValueError("字典中存在空元素")
            named = [':' in part for part in parts]
            if any(named) and not all(named):
                raise ValueError("字典不能混用命名值和位置值")
            if all(named):
                raw_values = {}
                for part in parts:
                    name, raw = part.split(':', 1)
                    name, raw = name.strip(), raw.strip()
                    if not name or not raw:
                        raise ValueError("字典中存在空键或空值")
                    if name in raw_values:
                        raise ValueError(f"字典字段重复: {name}")
                    raw_values[name] = raw
                expected = {name for name, _ in fields}
                unknown = set(raw_values) - expected
                missing = expected - set(raw_values)
                if unknown:
                    raise ValueError(f"字典包含未知字段: {', '.join(sorted(unknown))}")
                if missing:
                    raise ValueError(f"字典缺少字段: {', '.join(sorted(missing))}")
            else:
                if len(parts) != len(fields):
                    raise ValueError(
                        f"字典值数量不匹配: 需要{len(fields)}个，实际{len(parts)}个"
                    )
                raw_values = {
                    name: raw for (name, _), raw in zip(fields, parts)
                }

        return {
            name: converter(raw_values[name]) for name, converter in fields
        }

    @staticmethod
    def find_id(value: Any, table_name: str, display_field: str = 'name', id_field: str = 'id') -> dict:
        """
        ID 引用查找（返回包含 id 和显示字段的字典）
        :param value: ID 值
        :param table_name: 表名
        :param display_field: 显示字段名
        :param id_field: ID 字段名
        """
        if value is None or value == "":
            return {id_field: 0, display_field: ""}

        id_val = TypeConverter.to_int(value)

        # 返回结构，实际关联数据在运行时从对应表获取
        return {
            id_field: id_val,
            '_table': table_name,
            '_display_field': display_field,
        }

    @staticmethod
    def path(value: Any, *path_parts) -> str:
        """
        路径处理
        格式: path(前缀,后缀) 或 path(完整路径模板)
        示例:
          - path(res/spine/,json) + "role" -> "res/spine/role.json"
          - path(res/spine/role.json) -> "res/spine/role.json"
        :param value: 基础值（通常是文件名或ID）
        :param path_parts: 路径片段，用于拼接
        """
        import os

        if value is None:
            value = ""

        value_str = str(value).strip()

        # 如果没有额外参数，直接返回原值
        if not path_parts:
            return value_str

        # 拼接路径片段
        prefix = path_parts[0] if len(path_parts) > 0 else ""
        suffix = path_parts[1] if len(path_parts) > 1 else ""

        result = prefix + value_str + suffix
        return result

    @staticmethod
    def to_text_key(value: Any) -> Any:
        """
        文本键处理：数字转int，其他转string
        """
        if value is None or value == "":
            return ""

        val_str = str(value).strip()

        # 尝试转换为整数
        try:
            # 如果完全是数字，返回整数
            if val_str.isdigit() or (val_str.startswith('-') and val_str[1:].isdigit()):
                return int(val_str)
        except ValueError:
            pass

        # 否则返回字符串
        return val_str

    @staticmethod
    def common_string_param_for_split(value: Any) -> str:
        """
        通用字符串参数处理（用于分割）
        处理特殊字符转义等
        """
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _convert_find_id_int(value: Any) -> int:
        """
        转换为int类型的ID（用于引用int类型字段）
        :param value: ID 值
        :return: 整数，空值返回0
        """
        if value is None or value == "":
            return 0
        return TypeConverter.to_int(value)

    @staticmethod
    def _convert_find_id_str(value: Any) -> str:
        """
        转换为string类型的ID（用于引用string类型字段）
        :param value: ID 值
        :return: 字符串，空值返回""
        """
        if value is None or value == "":
            return ""
        return str(value).strip()

    @staticmethod
    def _convert_find_id_float(value: Any) -> float:
        """
        转换为float类型的ID（用于引用float类型字段）
        :param value: ID 值
        :return: 浮点数，空值返回0.0
        """
        if value is None or value == "":
            return 0.0
        return TypeConverter.to_float(value)

    @staticmethod
    def parse_type(value: Any, type_name: str, param: str = '') -> Any:
        """
        根据类型名称解析值（支持复杂嵌套语法）
        :param value: 原始值
        :param type_name: 类型名称，如 "split_list(int)", "split_list[_](string)"
        :param param: 额外参数
        """
        if value is None or value == "":
            return None

        type_name = type_name.lower().strip()

        # 基础类型
        if type_name in ('string', 'str'):
            return TypeConverter.to_string(value)
        elif type_name in ('int', 'integer'):
            return TypeConverter.to_int(value)
        elif type_name == 'float':
            return TypeConverter.to_float(value)
        elif type_name == 'bool':
            return TypeConverter.to_bool(value)

        # 列表类型
        if 'split_list' in type_name:
            # 解析分隔符和内部类型
            match = re.match(r'split_list\[(.)\]\((\w+)\)', type_name)
            if match:
                separator = match.group(1)
                inner_type = match.group(2)
                return TypeConverter.split_list(value, inner_type, separator)
            else:
                # 默认使用逗号分隔
                match = re.match(r'split_list\((\w+)\)', type_name)
                if match:
                    inner_type = match.group(1)
                    return TypeConverter.split_list(value, inner_type)

        return value


class PathValidationError(Exception):
    """路径验证错误"""
    pass
