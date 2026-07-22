# -*- coding: utf-8 -*-
"""
核心数据结构
定义工作表和行的数据封装
支持四行表头格式：
  第一行：字段名
  第二行：字段类型
  第三行：导出端 (C/S/X/CS)
  第四行：字段说明
"""
from collections import OrderedDict
from typing import Any, List, Optional, Dict


class FieldInfo:
    """字段信息"""

    def __init__(self, name: str = '', field_type: str = '', platform: str = '', desc: str = ''):
        self.name = name          # 字段名
        self.field_type = field_type  # 字段类型
        self.platform = platform  # 导出端: C/S/X/CS
        self.desc = desc          # 字段说明

    def should_export(self, mode: str) -> bool:
        """
        判断字段是否应该导出
        :param mode: 导出模式 c=客户端, s=服务端, cs=两者
        """
        if not self.platform or self.platform == 'X':
            return False
        if self.platform == 'CS':
            return True
        if mode == 'cs':
            return True
        if mode == 'c' and self.platform == 'C':
            return True
        if mode == 's' and self.platform == 'S':
            return True
        return False


class Row:
    """行数据封装"""

    def __init__(self, data: List[Any], field_info: Dict[str, FieldInfo]):
        """
        初始化行数据
        :param data: 行数据列表
        :param field_info: 字段信息字典 {字段名: FieldInfo}
        """
        self.data = data or []
        self.field_info = field_info or {}
        self._index = {name: i for i, name in enumerate(field_info.keys())}

    def get(self, field_name: str, default: Any = None) -> Any:
        """
        获取字段值
        :param field_name: 字段名
        :param default: 默认值
        """
        idx = self._index.get(field_name)
        if idx is not None and 0 <= idx < len(self.data):
            value = self.data[idx]
            if value is None:
                return default
            return value
        return default

    def get_int(self, field_name: str, default: int = 0) -> int:
        """获取整数值"""
        val = self.get(field_name)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_str(self, field_name: str, default: str = '') -> str:
        """获取字符串值"""
        val = self.get(field_name)
        if val is None:
            return default
        return str(val).strip()

    def to_dict(self, mode: str = 'cs') -> dict:
        """
        转换为字典
        :param mode: 导出模式，用于筛选字段
        """
        result = OrderedDict()
        for name in self._index.keys():
            info = self.field_info.get(name)
            if info and info.should_export(mode):
                result[name] = self.get(name)
        return result


class WorkSheet:
    """工作表数据封装"""

    def __init__(self, name: str):
        """
        初始化工作表
        :param name: 工作表名称
        """
        self.name = name
        self.field_info: Dict[str, FieldInfo] = {}  # 字段信息
        self.rows: List[Row] = []
        self._column_index: Dict[str, int] = {}  # 字段名到列索引的映射

    def add_row(self, data: List[Any]):
        """
        添加一行数据
        :param data: 行数据列表
        """
        row = Row(data, self.field_info)
        self.rows.append(row)

    def set_field_info(self, field_info: Dict[str, FieldInfo], column_index: Dict[str, int] = None):
        """
        设置字段信息
        :param field_info: 字段信息字典
        :param column_index: 字段名到列索引的映射
        """
        self.field_info = field_info
        if column_index:
            self._column_index = column_index
        else:
            # 自动生成列索引
            self._column_index = {name: i for i, name in enumerate(field_info.keys())}
        
        # 重新创建行对象以使用新的字段信息
        old_rows = self.rows
        self.rows = []
        for row_data in [r.data for r in old_rows]:
            self.add_row(row_data)

    def set_headers(self, headers: List[str]):
        """
        设置简单表头（兼容单行表头格式）
        :param headers: 列名列表
        """
        field_info = {}
        column_index = {}
        for i, name in enumerate(headers):
            field_info[name] = FieldInfo(name=name, platform='CS')
            column_index[name] = i
        self.set_field_info(field_info, column_index)

    def get_cell(self, row_idx: int, field_name: str) -> Any:
        """
        获取单元格数据
        :param row_idx: 行索引
        :param field_name: 字段名
        """
        if 0 <= row_idx < len(self.rows):
            return self.rows[row_idx].get(field_name)
        return None

    def get_cell_by_index(self, row_idx: int, col_idx: int) -> Any:
        """
        通过列索引获取单元格数据
        :param row_idx: 行索引
        :param col_idx: 列索引
        """
        if 0 <= row_idx < len(self.rows):
            row_data = self.rows[row_idx].data
            if 0 <= col_idx < len(row_data):
                return row_data[col_idx]
        return None

    def get_column_index(self, field_name: str) -> int:
        """
        获取字段的列索引
        :param field_name: 字段名
        :return: 列索引，未找到返回-1
        """
        return self._column_index.get(field_name, -1)

    def find_rows(self, field_name: str, value: Any) -> List[Row]:
        """
        查找符合条件的行
        :param field_name: 字段名
        :param value: 字段值
        """
        result = []
        for row in self.rows:
            if row.get(field_name) == value:
                result.append(row)
        return result

    def find_row(self, field_name: str, value: Any) -> Optional[Row]:
        """
        查找第一个符合条件的行
        :param field_name: 字段名
        :param value: 字段值
        """
        for row in self.rows:
            if row.get(field_name) == value:
                return row
        return None

    def row_count(self) -> int:
        """行数"""
        return len(self.rows)

    def column_count(self) -> int:
        """列数"""
        return len(self.field_info)
