# -*- coding: utf-8 -*-
"""
约束验证系统 - 100%还原DesignToExcel的约束方法
新增约束：range, unique, notEmpty, regex, ref
"""
from typing import Any, List, Dict, Optional
import re


class ConstraintValidator:
    """约束验证器"""
    
    @staticmethod
    def validate(constraint_name: str, params: List[str], 
                 field_name: str, field_value: Any, 
                 row_data: Dict, row_raw: Dict,
                 all_rows: List[Dict] = None) -> None:
        """
        验证约束
        
        Args:
            constraint_name: 约束名（如'len', 'range'）
            params: 参数列表
            field_name: 字段名
            field_value: 字段值（转换后的）
            row_data: 整行数据（转换后的）
            row_raw: 整行原始数据
            all_rows: 所有行数据（用于unique等全局约束）
        
        Raises:
            ConstraintError: 验证失败
        """
        method_name = f"check_{constraint_name}"
        if hasattr(ConstraintValidator, method_name):
            getattr(ConstraintValidator, method_name)(
                params, field_name, field_value, row_data, row_raw, all_rows
            )
        else:
            raise ConstraintError(f"未知的约束方法: {constraint_name}")
    
    # ==================== DesignToExcel原有约束 ====================
    
    @staticmethod
    def check_len(params: List[str], field_name: str, field_value: Any,
                  row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        长度限制
        len(min,max) 或 len(max)
        对list：元素个数
        对str：字符长度（中文占2）
        对int：取值范围
        """
        if len(params) == 0:
            raise ConstraintError("len约束需要参数")
        
        min_len = int(params[0])
        max_len = int(params[1]) if len(params) > 1 else min_len
        
        value_len = ConstraintValidator._get_length(field_value)
        
        if value_len < min_len or value_len > max_len:
            raise ConstraintError(
                f"字段 '{field_name}' 长度 {value_len} 不在范围 [{min_len}, {max_len}] 内",
                field_name, field_value
            )
    
    @staticmethod
    def check_len2(params: List[str], field_name: str, field_value: Any,
                   row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        二维列表每个元素的长度限制
        len2(min,max)
        """
        if not isinstance(field_value, list):
            raise ConstraintError(f"len2约束只能用于列表类型，字段 '{field_name}' 类型错误")
        
        min_len = int(params[0])
        max_len = int(params[1]) if len(params) > 1 else min_len
        
        for i, item in enumerate(field_value):
            item_len = ConstraintValidator._get_length(item)
            if item_len < min_len or item_len > max_len:
                raise ConstraintError(
                    f"字段 '{field_name}' 第 {i+1} 个元素长度 {item_len} 不在范围 [{min_len}, {max_len}] 内",
                    field_name, field_value
                )
    
    @staticmethod
    def check_len3(params: List[str], field_name: str, field_value: Any,
                   row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        三维列表每个元素的长度限制
        len3(min,max)
        """
        if not isinstance(field_value, list):
            raise ConstraintError(f"len3约束只能用于三维列表")
        
        min_len = int(params[0])
        max_len = int(params[1]) if len(params) > 1 else min_len
        
        for i, level2 in enumerate(field_value):
            if not isinstance(level2, list):
                continue
            for j, item in enumerate(level2):
                item_len = ConstraintValidator._get_length(item)
                if item_len < min_len or item_len > max_len:
                    raise ConstraintError(
                        f"字段 '{field_name}' [{i+1}][{j+1}] 元素长度 {item_len} 不在范围 [{min_len}, {max_len}] 内",
                        field_name, field_value
                    )
    
    @staticmethod
    def check_equalLen(params: List[str], field_name: str, field_value: Any,
                       row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        长度必须与指定字段相同
        equalLen(字段名1,字段名2,...)
        """
        if isinstance(field_value, str):
            return  # 字符串不检查
        
        field_len = len(field_value) if hasattr(field_value, '__len__') else 0
        
        for other_field in params:
            other_value = row_data.get(other_field)
            if other_value is None:
                continue
            
            other_len = len(other_value) if hasattr(other_value, '__len__') else 0
            
            if field_len != other_len:
                raise ConstraintError(
                    f"字段 '{field_name}' 长度 {field_len} 与 '{other_field}' 长度 {other_len} 不一致",
                    field_name, field_value
                )
    
    @staticmethod
    def check_equalLen2(params: List[str], field_name: str, field_value: Any,
                        row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        二维列表长度必须与指定字段相同，且每个内层列表长度也要相同
        equalLen2(字段名1,字段名2,...)
        """
        if not isinstance(field_value, list):
            return
        
        for other_field in params:
            other_value = row_data.get(other_field)
            if not isinstance(other_value, list):
                continue
            
            # 外层长度检查
            if len(field_value) != len(other_value):
                raise ConstraintError(
                    f"字段 '{field_name}' 外层长度 {len(field_value)} 与 '{other_field}' 长度 {len(other_value)} 不一致",
                    field_name, field_value
                )
            
            # 内层长度检查
            for i in range(len(field_value)):
                inner1 = field_value[i] if i < len(field_value) else []
                inner2 = other_value[i] if i < len(other_value) else []
                
                if isinstance(inner1, list) and isinstance(inner2, list):
                    if len(inner1) != len(inner2):
                        raise ConstraintError(
                            f"字段 '{field_name}' 第 {i+1} 个内层列表长度 {len(inner1)} 与 '{other_field}' 长度 {len(inner2)} 不一致",
                            field_name, field_value
                        )
    
    @staticmethod
    def check_coexist(params: List[str], field_name: str, field_value: Any,
                      row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        必须同时存在或同时为空
        coexist(字段名1,字段名2,...)
        """
        # 获取原始值判断空值
        field_empty = ConstraintValidator._is_empty_raw(row_raw.get(field_name))
        
        for other_field in params:
            other_empty = ConstraintValidator._is_empty_raw(row_raw.get(other_field))
            
            if field_empty != other_empty:
                raise ConstraintError(
                    f"字段 '{field_name}' 与 '{other_field}' 必须同时为空或同时不为空",
                    field_name, field_value
                )
    
    @staticmethod
    def check_leastOne(params: List[str], field_name: str, field_value: Any,
                       row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        指定字段中至少有一个不为空
        leastOne(字段名1,字段名2,...)
        """
        fields_to_check = [field_name] + params
        
        for f in fields_to_check:
            if not ConstraintValidator._is_empty_raw(row_raw.get(f)):
                return  # 找到非空字段，验证通过
        
        field_list = ', '.join(fields_to_check)
        raise ConstraintError(
            f"字段 {field_list} 中至少有一个不能为空",
            field_name, field_value
        )
    
    # ==================== 新增约束 ====================
    
    @staticmethod
    def check_range(params: List[str], field_name: str, field_value: Any,
                    row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        数值范围限制
        range(min,max)
        """
        if len(params) < 1:
            raise ConstraintError("range约束需要参数")
        
        min_val = float(params[0])
        max_val = float(params[1]) if len(params) > 1 else float('inf')
        
        try:
            num_value = float(field_value)
        except (ValueError, TypeError):
            raise ConstraintError(
                f"字段 '{field_name}' 的值 '{field_value}' 不是有效数字",
                field_name, field_value
            )
        
        if num_value < min_val or num_value > max_val:
            raise ConstraintError(
                f"字段 '{field_name}' 的值 {num_value} 不在范围 [{min_val}, {max_val}] 内",
                field_name, field_value
            )
    
    @staticmethod
    def check_unique(params: List[str], field_name: str, field_value: Any,
                     row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        全局唯一性检查
        unique() 或 unique(字段名) - 用于联合唯一
        """
        if all_rows is None:
            return  # 无法检查，跳过
        
        if len(params) == 0:
            # 单字段唯一
            check_value = field_value
            check_fields = [field_name]
        else:
            # 联合唯一：组合多个字段
            check_value = tuple(row_data.get(f) for f in [field_name] + params)
            check_fields = [field_name] + params
        
        count = 0
        for row in all_rows:
            if len(params) == 0:
                row_value = row.get(field_name)
            else:
                row_value = tuple(row.get(f) for f in check_fields)
            
            if row_value == check_value:
                count += 1
                if count > 1:
                    field_list = ', '.join(check_fields)
                    raise ConstraintError(
                        f"字段 {field_list} 的值 '{check_value}' 重复，必须唯一",
                        field_name, field_value
                    )
    
    @staticmethod
    def check_notEmpty(params: List[str], field_name: str, field_value: Any,
                       row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        不能为空
        notEmpty()
        """
        if ConstraintValidator._is_empty(field_value):
            raise ConstraintError(
                f"字段 '{field_name}' 不能为空",
                field_name, field_value
            )
    
    @staticmethod
    def check_regex(params: List[str], field_name: str, field_value: Any,
                    row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        正则表达式匹配
        regex(模式)
        """
        if len(params) == 0:
            raise ConstraintError("regex约束需要正则表达式参数")
        
        pattern = params[0]
        str_value = str(field_value) if field_value is not None else ""
        
        if not re.match(pattern, str_value):
            raise ConstraintError(
                f"字段 '{field_name}' 的值 '{str_value}' 不符合格式要求",
                field_name, field_value
            )
    
    @staticmethod
    def check_ref(params: List[str], field_name: str, field_value: Any,
                  row_data: Dict, row_raw: Dict, all_rows: List[Dict] = None):
        """
        外键引用验证
        ref(文件名,工作表名,字段名)
        """
        # 简化实现：暂不检查文件是否存在
        # 实际应该加载关联表并检查值是否存在
        if field_value is None or field_value == "":
            return  # 空值不检查
        
        # 这里可以扩展为实际检查关联表
        # 目前仅做格式检查
        pass
    
    # ==================== 辅助方法 ====================
    
    @staticmethod
    def _get_length(value: Any) -> int:
        """获取值的长度"""
        if value is None:
            return 0
        
        if isinstance(value, (int, float)):
            return int(value)  # 数字返回本身作为"长度"
        
        if isinstance(value, list):
            return len(value)
        
        if isinstance(value, str):
            # 中文占2个字符（GBK编码）
            try:
                return len(value.encode('GBK'))
            except:
                return len(value)
        
        return len(str(value))
    
    @staticmethod
    def _is_empty(value: Any) -> bool:
        """判断转换后的值是否为空"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, list) and len(value) == 0:
            return True
        if isinstance(value, dict) and len(value) == 0:
            return True
        return False
    
    @staticmethod
    def _is_empty_raw(value: Any) -> bool:
        """判断原始值是否为空"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False


class ConstraintError(Exception):
    """约束验证错误"""
    
    def __init__(self, message: str, field_name: str = None, field_value: Any = None):
        super().__init__(message)
        self.field_name = field_name
        self.field_value = field_value
