"""
类型注册表模块

管理类型定义，提供严格类型验证：
- 所有类型必须在TypeDefinition.xlsx中定义
- 无默认类型，未定义类型将导致错误
- 支持从类型定义解析转换函数
"""

import os
from typing import Any, Callable, Dict, List, Optional
from openpyxl import load_workbook

from .expression import (
    ExpressionSyntaxError, parse_call, parse_field_type, split_top_level, unquote,
)


class UndefinedTypeError(Exception):
    """未定义类型错误"""
    pass


class TypeRegistry:
    """类型注册表"""
    
    def __init__(self, table_dir: str):
        """
        初始化类型注册表
        
        Args:
            table_dir: Excel文件目录
        
        Raises:
            FileNotFoundError: TypeDefinition.xlsx不存在
            UndefinedTypeError: 类型定义解析失败
        """
        self.table_dir = table_dir
        self._types: Dict[str, Dict[str, Any]] = {}
        self._load_type_definition()
    
    def _load_type_definition(self):
        """加载类型定义文件"""
        type_def_path = os.path.join(self.table_dir, "TypeDefinition.xlsx")
        
        if not os.path.exists(type_def_path):
            raise FileNotFoundError(
                f"类型定义文件不存在: {type_def_path}\n"
                f"请运行工具自动生成或手动创建TypeDefinition.xlsx"
            )
        
        wb = load_workbook(type_def_path, read_only=True, data_only=True)
        
        if 'CODE' not in wb.sheetnames:
            wb.close()
            raise UndefinedTypeError("TypeDefinition.xlsx中缺少CODE工作表")
        
        ws = wb['CODE']
        rows = list(ws.rows)
        
        if len(rows) < 2:
            wb.close()
            raise UndefinedTypeError("TypeDefinition.xlsx数据不完整")
        
        # 解析表头
        header = [cell.value for cell in rows[0]]
        
        # 查找列索引
        col_indices = {}
        for i, col_name in enumerate(header):
            if col_name:
                col_name_str = str(col_name).strip().lower()
                if col_name_str in {
                    'name', 'type name', 'typename', 'type',
                    '类型名', '类型名称', '名前', '이름', 'nombre', '型別名稱',
                }:
                    col_indices['name'] = i
                elif col_name_str in {
                    'convert', 'convert func', 'converter', 'conversion',
                    '转换函数', '変換関数', '변환 함수', 'conversión', '轉換函式',
                }:
                    col_indices['convert'] = i
        
        # 如果没有找到标准列，假设第一列是名称，第二列是转换函数
        if 'name' not in col_indices:
            col_indices['name'] = 0
        if 'convert' not in col_indices:
            col_indices['convert'] = 1
        
        # 解析类型定义
        for row in rows[1:]:
            values = [cell.value for cell in row]
            
            if len(values) <= col_indices['name']:
                continue
            
            type_name = str(values[col_indices['name']]).strip() if values[col_indices['name']] else None
            if not type_name:
                continue
            
            convert_func_str = ""
            if 'convert' in col_indices and len(values) > col_indices['convert']:
                convert_func_str = str(values[col_indices['convert']]).strip() if values[col_indices['convert']] else ""
            
            # Parse while the workbook is still open, but always release the
            # Windows file handle before propagating a bad definition.
            try:
                convert_func = self._parse_convert_func(convert_func_str)
            except Exception:
                wb.close()
                raise
            
            self._types[type_name] = {
                'name': type_name,
                'convert_func_str': convert_func_str,
                'convert_func': convert_func
            }

        wb.close()
        
        if not self._types:
            raise UndefinedTypeError("TypeDefinition.xlsx中没有找到有效的类型定义")

        # bytes was added with Protobuf support. Keep existing projects working
        # even when their already-created TypeDefinition.xlsx predates this type.
        if 'bytes' not in self._types:
            from .types import TypeConverter
            self._types['bytes'] = {
                'name': 'bytes',
                'convert_func_str': 'bytes',
                'convert_func': TypeConverter.to_bytes,
            }
    
    def _parse_convert_func(self, func_str: str) -> Callable:
        """
        解析转换函数字符串
        
        Args:
            func_str: 转换函数字符串，如 "int", "split_list(int)", "split_list2(split_list(int))"
        
        Returns:
            转换函数
        """
        from .types import TypeConverter
        
        if not func_str:
            # 默认返回字符串转换
            return TypeConverter.to_string
        
        func_str = func_str.strip()
        try:
            expression = parse_call(func_str)
        except ExpressionSyntaxError as exc:
            raise UndefinedTypeError(f"转换函数语法错误 '{func_str}': {exc}") from exc
        if expression.is_call:
            return self._create_convert_func(
                expression.name, list(expression.args), func_str
            )
        return self._create_simple_convert_func(expression.name)
    
    def _parse_args(self, args_str: str) -> List[Any]:
        """解析函数参数"""
        return [part for part in split_top_level(args_str, (',', ';')) if part]

    @staticmethod
    def _require_arg_count(func_name: str, args: List[str], minimum: int,
                           maximum: Optional[int] = None) -> None:
        maximum = minimum if maximum is None else maximum
        if not minimum <= len(args) <= maximum:
            expected = str(minimum) if minimum == maximum else f"{minimum}-{maximum}"
            raise UndefinedTypeError(
                f"转换函数 {func_name} 参数数量错误: 需要{expected}个，实际{len(args)}个"
            )
    
    def _create_convert_func(self, func_name: str, args: List[str], 
                             full_func_str: str = '') -> Callable:
        """创建转换函数"""
        from .types import TypeConverter
        
        # 处理带方括号的自定义分隔符语法，如 split_list[_] 或 split_list[|]
        separator = None
        if '[' in func_name and ']' in func_name:
            base_name = func_name[:func_name.find('[')]
            sep_part = func_name[func_name.find('[')+1:func_name.find(']')]
            separator = TypeConverter.SEPARATOR_MAP.get(sep_part, sep_part)
            func_name = base_name
        
        if func_name == 'int':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_int
        elif func_name == 'float':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_float
        elif func_name == 'str' or func_name == 'string':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_string
        elif func_name == 'bool':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_bool
        elif func_name == 'bytes':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_bytes
        elif func_name == 'enum':
            if len(args) < 2:
                raise UndefinedTypeError("转换函数 enum 至少需要基础类型和一个允许值")
            base_type = args[0].strip().lower()
            if base_type not in ('int', 'string', 'str'):
                raise UndefinedTypeError("enum 仅支持 int 或 string 基础类型")
            base_converter = (
                TypeConverter.to_int if base_type == 'int' else TypeConverter.to_string
            )
            try:
                allowed_values = tuple(base_converter(unquote(item)) for item in args[1:])
            except Exception as exc:
                raise UndefinedTypeError(f"enum 允许值转换失败: {exc}") from exc

            def convert_enum(value):
                converted = base_converter(value)
                if converted not in allowed_values:
                    allowed = ", ".join(str(item) for item in allowed_values)
                    raise ValueError(f"值 '{value}' 不在枚举允许值中: {allowed}")
                return converted

            return convert_enum
        elif func_name == 'split_list':
            self._require_arg_count(func_name, args, 1)
            if args:
                inner_type = args[0]
                # 检查是否是嵌套函数调用（如 find(...)）
                if '(' in inner_type and inner_type.endswith(')'):
                    # 递归解析嵌套函数
                    inner_func = self._parse_convert_func(inner_type)
                    # 一维列表默认使用 # 分隔
                    sep = separator if separator else '#'
                    return lambda v: TypeConverter.split_list(v, inner_func, sep)
                else:
                    # 简单类型（int/string/float）
                    # 一维列表默认使用 # 分隔
                    sep = separator if separator else '#'
                    return lambda v: TypeConverter.split_list(v, inner_type, sep)
            return TypeConverter.split_list
        elif func_name == 'split_list_ex':
            self._require_arg_count(func_name, args, 2)
            # 自定义分隔符版本
            if len(args) >= 2:
                sep = args[0]
                inner_type = args[1]
                return lambda v: TypeConverter.split_list(v, inner_type, sep)
            return TypeConverter.split_list
        elif func_name == 'split_list2':
            self._require_arg_count(func_name, args, 1)
            if args:
                inner_type = args[0]
                # 检查是否是嵌套函数调用
                if '(' in inner_type and inner_type.endswith(')'):
                    inner_func = self._parse_convert_func(inner_type)
                    return lambda v: TypeConverter.split_list2(v, inner_func)
                else:
                    # 简单类型（int/string/float）
                    type_map = {
                        'int': TypeConverter.to_int,
                        'float': TypeConverter.to_float,
                        'string': TypeConverter.to_string,
                        'str': TypeConverter.to_string,
                    }
                    converter = type_map.get(inner_type, TypeConverter.to_string)
                    return lambda v: TypeConverter.split_list2(v, converter)
            return TypeConverter.split_list2
        elif func_name == 'split_list3':
            self._require_arg_count(func_name, args, 1)
            if args:
                inner_type = args[0]
                # 检查是否是嵌套函数调用
                if '(' in inner_type and inner_type.endswith(')'):
                    inner_func = self._parse_convert_func(inner_type)
                    return lambda v: TypeConverter.split_list3(v, inner_func)
                else:
                    # 简单类型（int/string/float）
                    type_map = {
                        'int': TypeConverter.to_int,
                        'float': TypeConverter.to_float,
                        'string': TypeConverter.to_string,
                        'str': TypeConverter.to_string,
                    }
                    converter = type_map.get(inner_type, TypeConverter.to_string)
                    return lambda v: TypeConverter.split_list3(v, converter)
            return TypeConverter.split_list3
        elif func_name == 'split_dict':
            if not args:
                raise UndefinedTypeError("转换函数 split_dict 至少需要一个字段定义")
            fields = []
            for definition in args:
                if ':' in definition and ' ' not in definition:
                    field_name, field_expression = definition.split(':', 1)
                else:
                    try:
                        field_expression, field_name = definition.rsplit(None, 1)
                    except ValueError as exc:
                        raise UndefinedTypeError(
                            f"split_dict 字段定义错误: {definition}"
                        ) from exc
                field_name = field_name.strip()
                if not field_name or any(name == field_name for name, _ in fields):
                    raise UndefinedTypeError(f"split_dict 字段名无效或重复: {field_name}")
                fields.append((field_name, self._parse_convert_func(field_expression)))
            return lambda v: TypeConverter.split_dict_fields(v, fields)
        elif func_name == 'find_id':
            self._require_arg_count(func_name, args, 3)
            if len(args) >= 3:
                table_name = args[0]
                table_desc = args[1]
                id_field = args[2]

                # 获取被引用字段的类型，用于决定空值的默认值
                ref_type = self._get_referenced_field_type(table_name, id_field)

                # 根据被引用字段的类型，创建对应的转换函数
                if ref_type == 'int':
                    # 引用的是int类型字段，空值返回0
                    return lambda v: TypeConverter._convert_find_id_int(v)
                elif ref_type in ('str', 'string'):
                    # 引用的是string类型字段，空值返回""
                    return lambda v: TypeConverter._convert_find_id_str(v)
                elif ref_type == 'float':
                    # 引用的是float类型字段，空值返回0.0
                    return lambda v: TypeConverter._convert_find_id_float(v)
                else:
                    # 未知类型，使用默认处理
                    return lambda v: TypeConverter.find_id(v, table_name, table_desc, id_field)
            return lambda v: v
        elif func_name == 'find':
            self._require_arg_count(func_name, args, 3)
            # find 是 find_id 的简写形式，功能相同
            if len(args) >= 3:
                table_name = args[0]
                table_desc = args[1]
                id_field = args[2]

                # 获取被引用字段的类型
                ref_type = self._get_referenced_field_type(table_name, id_field)

                # 根据被引用字段的类型，创建对应的转换函数
                if ref_type == 'int':
                    return lambda v: TypeConverter._convert_find_id_int(v)
                elif ref_type in ('str', 'string'):
                    return lambda v: TypeConverter._convert_find_id_str(v)
                elif ref_type == 'float':
                    return lambda v: TypeConverter._convert_find_id_float(v)
                else:
                    return lambda v: TypeConverter.find_id(v, table_name, table_desc, id_field)
            return lambda v: v
        elif func_name == 'path':
            self._require_arg_count(func_name, args, 0, 2)
            if args:
                return lambda v: TypeConverter.path(v, *args)
            return TypeConverter.path
        elif func_name == 'text_key':
            self._require_arg_count(func_name, args, 0)
            return TypeConverter.to_text_key
        elif func_name == 'commonStringParamForSplit':
            self._require_arg_count(func_name, args, 0)
            return lambda v: TypeConverter.split_list(v, 'string', '#')
        else:
            raise UndefinedTypeError(f"未知的转换函数: {func_name}")
    
    def _create_simple_convert_func(self, type_name: str) -> Callable:
        """创建简单类型转换函数"""
        from .types import TypeConverter
        
        type_map = {
            'int': TypeConverter.to_int,
            'float': TypeConverter.to_float,
            'str': TypeConverter.to_string,
            'string': TypeConverter.to_string,
            'bool': TypeConverter.to_bool,
            'bytes': TypeConverter.to_bytes,
            'text_key': TypeConverter.to_text_key,
            'commonStringParamForSplit': lambda value: TypeConverter.split_list(
                value, 'string', '#'
            ),
        }
        
        converter = type_map.get(type_name)
        if converter is None:
            raise UndefinedTypeError(f"未知的转换函数: {type_name}")
        return converter
    
    def has_type(self, type_name: str) -> bool:
        """检查类型是否已定义"""
        return type_name in self._types
    
    def get_reference_info(self, type_name: str) -> Optional[Dict[str, str]]:
        """
        获取类型的引用信息（用于ID引用验证）
        
        Args:
            type_name: 类型名称
        
        Returns:
            {'table': 表名, 'field': 字段名} 或 None
        """
        if type_name not in self._types:
            return None
        
        func_str = self._types[type_name].get('convert_func_str', '')
        if not func_str:
            return None
        
        # 解析 find/find_id 调用
        # 格式: find(table,desc,field) 或 find_id(table,desc,field)
        for func_name in ['find(', 'find_id(']:
            if func_name in func_str:
                # 提取 find(...) 的参数
                start = func_str.find(func_name)
                if start == -1:
                    continue
                
                # 找到匹配的括号
                paren_start = func_str.find('(', start)
                if paren_start == -1:
                    continue
                
                # 寻找匹配的右括号
                depth = 1
                paren_end = paren_start + 1
                while paren_end < len(func_str) and depth > 0:
                    if func_str[paren_end] == '(':
                        depth += 1
                    elif func_str[paren_end] == ')':
                        depth -= 1
                    paren_end += 1
                
                if depth == 0:
                    # 提取参数
                    args_str = func_str[paren_start + 1:paren_end - 1]
                    args = [
                        item for item in split_top_level(args_str, (',',)) if item
                    ]
                    if len(args) >= 3:
                        return {
                            'table': args[0],
                            'field': args[2]
                        }
        
        return None
    
    def get_type(self, type_name: str) -> Dict[str, Any]:
        """
        获取类型定义
        
        Args:
            type_name: 类型名称
        
        Returns:
            类型定义字典
        
        Raises:
            UndefinedTypeError: 类型未定义
        """
        if type_name not in self._types:
            available = list(self._types.keys())
            raise UndefinedTypeError(
                f"类型 '{type_name}' 未定义。\n"
                f"请在TypeDefinition.xlsx中添加此类型定义。\n"
                f"可用类型: {', '.join(available)}"
            )
        
        return self._types[type_name]
    
    def get_all_types(self) -> List[str]:
        """获取所有类型名称"""
        return list(self._types.keys())

    def get_referenced_type(self, type_name: str) -> Optional[str]:
        """
        获取引用类型的基础类型

        例如：如果类型名是 'itemId'，转换函数是 'find_id(item,物品表,id)'
              而 item.xlsx 的 id 字段类型是 'string'
              则返回 'string'

        Args:
            type_name: 类型名称，如 'itemId'

        Returns:
            基础类型名称，如 'int', 'string' 等，如果不是引用类型则返回 None
        """
        if type_name not in self._types:
            return None

        convert_func_str = self._types[type_name].get('convert_func_str', '')

        # 检查是否是 find_id / find 类型
        if not (convert_func_str.startswith('find_id(') or convert_func_str.startswith('find(')):
            return None

        # 解析 find_id 参数: find_id(item,物品表,id) -> ['item', '物品表', 'id']
        import re
        match = re.search(r'find(?:_id)?\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)', convert_func_str)
        if not match:
            return None

        ref_table = match.group(1).strip()  # 如 'item'
        ref_field = match.group(3).strip()  # 如 'id'

        # 查找被引用的 xlsx 文件
        import os
        table_dir = self.table_dir
        ref_file_path = None

        for filename in os.listdir(table_dir):
            if filename.lower().startswith(ref_table.lower()) and filename.endswith('.xlsx'):
                ref_file_path = os.path.join(table_dir, filename)
                break

        if not ref_file_path:
            return None

        # 读取被引用文件，查找被引用字段的类型
        try:
            from openpyxl import load_workbook
            wb = load_workbook(ref_file_path, read_only=True, data_only=True)

            ref_field_type = None
            for sheet_name in wb.sheetnames:
                if sheet_name.upper() == 'CODE':
                    continue

                ws = wb[sheet_name]
                rows = list(ws.rows)
                if len(rows) < 2:
                    continue

                names_row = rows[0]
                types_row = rows[1]

                for col_idx, cell in enumerate(names_row):
                    if cell.value and str(cell.value).strip() == ref_field:
                        if col_idx < len(types_row) and types_row[col_idx].value:
                            ref_field_type = str(types_row[col_idx].value).strip()
                            break

                if ref_field_type:
                    break

            wb.close()

            if not ref_field_type:
                return None

            # 解析被引用字段的类型（去掉约束，如 "int+notEmpty()" -> "int"）
            ref_base_type = parse_field_type(ref_field_type).base_type

            return ref_base_type

        except Exception:
            return None

    def _get_referenced_field_type(self, table_name: str, field_name: str) -> str:
        """
        获取被引用字段的类型

        例如：table_name='item', field_name='id' -> 查找 item.xlsx 的 id 字段类型 -> 'int'

        Args:
            table_name: 表名（不含扩展名）
            field_name: 字段名

        Returns:
            字段类型，如 'int', 'string', 'float'，未找到返回 'str'
        """
        import os
        from openpyxl import load_workbook

        # 查找被引用的 xlsx 文件
        ref_file_path = None
        for filename in os.listdir(self.table_dir):
            if filename.lower().startswith(table_name.lower()) and filename.endswith('.xlsx'):
                ref_file_path = os.path.join(self.table_dir, filename)
                break

        if not ref_file_path:
            return 'str'  # 默认返回字符串类型

        try:
            wb = load_workbook(ref_file_path, read_only=True, data_only=True)

            ref_field_type = None
            for sheet_name in wb.sheetnames:
                if sheet_name.upper() == 'CODE':
                    continue

                ws = wb[sheet_name]
                rows = list(ws.rows)
                if len(rows) < 2:
                    continue

                names_row = rows[0]
                types_row = rows[1]

                for col_idx, cell in enumerate(names_row):
                    if cell.value and str(cell.value).strip() == field_name:
                        if col_idx < len(types_row) and types_row[col_idx].value:
                            ref_field_type = str(types_row[col_idx].value).strip()
                            break

                if ref_field_type:
                    break

            wb.close()

            if not ref_field_type:
                return 'str'

            # 解析类型（去掉约束）
            base_type = parse_field_type(ref_field_type).base_type
            return base_type

        except Exception:
            return 'str'

    def get_referenced_field_type(self, table_name: str, field_name: str) -> str:
        """Public reference used by Protobuf automatic type inference."""
        return self._get_referenced_field_type(table_name, field_name)
