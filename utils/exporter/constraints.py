"""
约束验证模块

提供配置数据的约束验证功能
"""

import math
import re
from typing import Any, Dict, List


class ConstraintError(Exception):
    """约束验证错误"""
    pass


class ConstraintValidator:
    """约束验证器"""
    
    def __init__(self):
        self._validators = {
            'len': self._validate_len,
            'len2': self._validate_len2,
            'len3': self._validate_len3,
            'equalLen': self._validate_equal_len,
            'equalLen2': self._validate_equal_len2,
            'coexist': self._validate_coexist,
            'leastOne': self._validate_least_one,
            'notEmpty': self._validate_not_empty,
            'required': self._validate_not_empty,
            'range': self._validate_range,
            'regex': self._validate_regex,
            'unique': self._validate_unique,
        }

    def validate_definition(self, constraint_name: str, params: List[str]) -> None:
        """Reject malformed constraints while parsing the four-line header."""
        if constraint_name not in self._validators:
            raise ConstraintError(f"未知约束: {constraint_name}")
        exact = {
            'required': 0, 'notEmpty': 0, 'equalLen': 1,
            'equalLen2': 1, 'coexist': 1, 'range': 2,
            'regex': 1, 'unique': 0,
        }
        if constraint_name in exact and len(params) != exact[constraint_name]:
            raise ConstraintError(
                f"{constraint_name}参数数量错误: 需要{exact[constraint_name]}个，实际{len(params)}个"
            )
        if constraint_name in ('len', 'len2', 'len3') and not 1 <= len(params) <= 2:
            raise ConstraintError(f"{constraint_name}需要1到2个参数")
        if constraint_name == 'leastOne' and not params:
            raise ConstraintError("leastOne需要至少一个字段")
        if constraint_name in ('len', 'len2', 'len3'):
            try:
                values = [int(value) for value in params]
            except ValueError as exc:
                raise ConstraintError(f"{constraint_name}参数必须是整数") from exc
            if any(value < 0 for value in values):
                raise ConstraintError(f"{constraint_name}参数不能为负数")
            if len(values) == 2 and values[0] > values[1]:
                raise ConstraintError(f"{constraint_name}最小值不能大于最大值")
        if constraint_name == 'range':
            try:
                bounds = [float(value) for value in params]
            except ValueError as exc:
                raise ConstraintError("range参数必须是数字") from exc
            if not all(math.isfinite(value) for value in bounds) or bounds[0] > bounds[1]:
                raise ConstraintError("range范围无效")
        if constraint_name == 'regex':
            try:
                re.compile(params[0])
            except re.error as exc:
                raise ConstraintError(f"regex表达式无效: {exc}") from exc
    
    def validate(self, constraint_name: str, params: List[str],
                field_name: str, field_value: Any,
                row_data: Dict, row_raw: Dict) -> None:
        """验证约束"""
        validator = self._validators.get(constraint_name)
        if not validator:
            raise ConstraintError(f"未知约束: {constraint_name}")
        
        validator(params, field_name, field_value, row_data, row_raw)
    
    def _get_element_count(self, value: Any) -> int:
        """获取元素数量（支持任意维度列表和单个值）"""
        if isinstance(value, list):
            return len(value)
        # 单个非空值算作1个元素
        if value is not None and value != "":
            return 1
        return 0
    
    def _validate_len(self, params: List[str], field_name: str, field_value: Any,
                     row_data: Dict, row_raw: Dict) -> None:
        """列表长度范围验证: len(min,max)"""
        if not isinstance(field_value, list):
            raise ConstraintError(f"'{field_name}'需要是列表")
        
        length = len(field_value)
        
        if len(params) >= 1:
            min_len = int(params[0])
            if length < min_len:
                raise ConstraintError(f"'{field_name}'长度{length}，至少需要{min_len}个")
        
        if len(params) >= 2:
            max_len = int(params[1])
            if length > max_len:
                raise ConstraintError(f"'{field_name}'长度{length}，最多{max_len}个")
    
    def _validate_len2(self, params: List[str], field_name: str, field_value: Any,
                      row_data: Dict, row_raw: Dict) -> None:
        """2D列表元素长度验证: len2(min,max)"""
        if not isinstance(field_value, list):
            raise ConstraintError(f"'{field_name}'需要是列表")
        
        min_len = int(params[0]) if len(params) >= 1 else None
        max_len = int(params[1]) if len(params) >= 2 else None
        
        for i, item in enumerate(field_value):
            if not isinstance(item, list):
                raise ConstraintError(f"'{field_name}'第{i+1}项不是列表")
            
            item_len = len(item)
            
            if min_len is not None and item_len < min_len:
                raise ConstraintError(f"'{field_name}'第{i+1}项只有{item_len}个，至少需要{min_len}个")
            
            if max_len is not None and item_len > max_len:
                raise ConstraintError(f"'{field_name}'第{i+1}项有{item_len}个，最多{max_len}个")
    
    def _validate_len3(self, params: List[str], field_name: str, field_value: Any,
                      row_data: Dict, row_raw: Dict) -> None:
        """3D列表元素长度验证: len3(min,max)"""
        if not isinstance(field_value, list):
            raise ConstraintError(f"'{field_name}'需要是列表")
        
        min_len = int(params[0]) if len(params) >= 1 else None
        max_len = int(params[1]) if len(params) >= 2 else None
        
        for i, item in enumerate(field_value):
            if not isinstance(item, list):
                raise ConstraintError(f"'{field_name}'第{i+1}项不是2D列表")
            
            for j, sub_item in enumerate(item):
                if not isinstance(sub_item, list):
                    raise ConstraintError(f"'{field_name}'第{i+1}项第{j+1}个子项不是列表")
                
                item_len = len(sub_item)
                
                if min_len is not None and item_len < min_len:
                    raise ConstraintError(f"'{field_name}'第{i+1}项第{j+1}组只有{item_len}个，至少需要{min_len}个")
                
                if max_len is not None and item_len > max_len:
                    raise ConstraintError(f"'{field_name}'第{i+1}项第{j+1}组有{item_len}个，最多{max_len}个")
    
    def _validate_equal_len(self, params: List[str], field_name: str, field_value: Any,
                           row_data: Dict, row_raw: Dict) -> None:
        """
        验证与另一字段长度相等: equalLen(otherField)
        支持不同维度列表间的长度比较（比较元素数量）
        规则：
        - 如果当前字段为空（0个），跳过验证（视为通过）
        - 如果双方都为0，通过
        - 如果数量不等，报错
        """
        if not params:
            raise ConstraintError("equalLen需要指定目标字段")

        target_field = params[0]

        # 检查目标字段是否存在（检查原始数据字段名）
        if target_field not in row_raw:
            raise ConstraintError(f"'{field_name}'要求与'{target_field}'长度相同，但'{target_field}'字段不存在")

        # 统一获取元素数量（支持任意维度）
        current_count = self._get_element_count(field_value)
        
        # 优先从转换后的数据获取目标字段
        target_value = row_data.get(target_field)
        if target_value is None:
            # 目标字段还未转换，从原始数据获取
            raw_val = row_raw.get(target_field)
            if raw_val is not None and raw_val != "":
                target_value = raw_val
            else:
                target_value = []
        target_count = self._get_element_count(target_value)

        # 规则：如果当前字段为空（0个），跳过验证
        if current_count == 0:
            return
        
        # 当前字段有值，必须和目标字段数量相同
        if current_count != target_count:
            raise ConstraintError(
                f"'{field_name}'有{current_count}个，'{target_field}'有{target_count}个，数量必须相同"
            )
    
    def _validate_equal_len2(self, params: List[str], field_name: str, field_value: Any,
                            row_data: Dict, row_raw: Dict) -> None:
        """
        验证与另一字段的2D长度相等: equalLen2(otherField)
        规则：如果当前字段为空（0个元素），跳过验证
        """
        if not params:
            raise ConstraintError("equalLen2需要指定目标字段")

        target_field = params[0]

        # 检查目标字段是否存在
        if target_field not in row_raw:
            raise ConstraintError(f"'{field_name}'要求与'{target_field}'的2D长度相同，但'{target_field}'字段不存在")

        # 如果当前字段为空，跳过验证
        if not isinstance(field_value, list) or len(field_value) == 0:
            return

        # 优先从转换后的数据获取
        target_value = row_data.get(target_field)
        if target_value is None and target_field in row_raw:
            target_value = row_raw.get(target_field)

        if not isinstance(field_value, list):
            raise ConstraintError(f"'{field_name}'需要是列表")

        if not isinstance(target_value, list):
            raise ConstraintError(f"'{target_field}'需要是列表")

        if len(field_value) != len(target_value):
            raise ConstraintError(
                f"'{field_name}'外层有{len(field_value)}项，'{target_field}'外层有{len(target_value)}项"
            )

        # 比较每个子列表的长度
        for i, (item, target_item) in enumerate(zip(field_value, target_value)):
            if not isinstance(item, list) or not isinstance(target_item, list):
                raise ConstraintError(f"'{field_name}'第{i+1}项不是列表")

            if len(item) != len(target_item):
                raise ConstraintError(
                    f"'{field_name}'第{i+1}项有{len(item)}个，'{target_field}'对应项有{len(target_item)}个"
                )
    
    def _validate_coexist(self, params: List[str], field_name: str, field_value: Any,
                         row_data: Dict, row_raw: Dict) -> None:
        """验证两字段同时存在或同时为空: coexist(otherField)"""
        if not params:
            raise ConstraintError("coexist需要指定目标字段")
        
        target_field = params[0]
        target_value = row_raw.get(target_field, "")
        
        # 判断当前字段是否为空
        current_empty = (field_value is None or field_value == "" or
                        (isinstance(field_value, list) and len(field_value) == 0))
        
        # 判断目标字段是否为空（原始值）
        target_empty = (target_value is None or target_value == "" or
                       str(target_value).strip() == "")
        
        if current_empty != target_empty:
            target_status = "为空" if target_empty else "有值"
            current_status = "为空" if current_empty else "有值"
            raise ConstraintError(
                f"'{field_name}'{current_status}，但'{target_field}'{target_status}，必须同时有值或同时为空"
            )
    
    def _validate_least_one(self, params: List[str], field_name: str, field_value: Any,
                           row_data: Dict, row_raw: Dict) -> None:
        """验证至少一个字段非空: leastOne(field1,field2,...)"""
        if not params:
            raise ConstraintError("leastOne需要指定至少一个字段")
        
        # 检查所有指定字段
        fields_to_check = params
        has_non_empty = False
        
        for field in fields_to_check:
            value = row_raw.get(field, "")
            if value is not None and str(value).strip() != "":
                has_non_empty = True
                break
        
        if not has_non_empty:
            field_list = ", ".join(fields_to_check)
            raise ConstraintError(f"'{field_list}'至少需要填一个")
    
    def _validate_not_empty(self, params: List[str], field_name: str, field_value: Any,
                           row_data: Dict, row_raw: Dict) -> None:
        """Validate the original cell, before defaults turn blanks into values."""
        raw_value = row_raw.get(field_name)
        is_empty = (
            raw_value is None
            or (isinstance(raw_value, str) and raw_value.strip() == "")
            or (isinstance(raw_value, (list, dict)) and len(raw_value) == 0)
        )
        
        if is_empty:
            raise ConstraintError(f"'{field_name}'不能为空")

    def _validate_range(self, params: List[str], field_name: str, field_value: Any,
                        row_data: Dict, row_raw: Dict) -> None:
        try:
            value = float(field_value)
            minimum, maximum = (float(item) for item in params)
        except (TypeError, ValueError) as exc:
            raise ConstraintError(f"'{field_name}'必须是数字才能检查范围") from exc
        if not minimum <= value <= maximum:
            raise ConstraintError(
                f"'{field_name}'值{field_value}不在闭区间[{params[0]}, {params[1]}]范围内"
            )

    def _validate_regex(self, params: List[str], field_name: str, field_value: Any,
                        row_data: Dict, row_raw: Dict) -> None:
        if re.fullmatch(params[0], str(field_value)) is None:
            raise ConstraintError(f"'{field_name}'格式不符合正则表达式 {params[0]}")

    def _validate_unique(self, params: List[str], field_name: str, field_value: Any,
                         row_data: Dict, row_raw: Dict) -> None:
        # Table-level uniqueness is checked after every row has been converted.
        return None
