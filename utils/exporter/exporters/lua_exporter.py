# -*- coding: utf-8 -*-
"""
Lua 格式导出器
支持自动分块（避免 Lua 常量限制）和访问函数生成
"""
import os
import re
from typing import List, Any, Dict
from ..core import WorkSheet


class LuaExporter:
    """Lua 格式导出器"""

    # Lua 函数常量限制（略小于 65536 以留安全余量）
    LUA_CONSTANT_LIMIT = 60000

    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def _log(self, message: str):
        # 日志由 converter 统一处理
        pass

    def _format_lua_value(self, value: Any) -> str:
        """格式化 Lua 值"""
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            # 转义 Lua 字符串
            escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{escaped}"'
        if isinstance(value, list):
            items = [self._format_lua_value(v) for v in value]
            return "{" + ", ".join(items) + "}"
        if isinstance(value, dict):
            pairs = []
            for k, v in value.items():
                pairs.append(f'["{str(k)}"] = {self._format_lua_value(v)}')
            return "{" + ", ".join(pairs) + "}"
        return str(value)

    def _estimate_constant_count(self, data: dict) -> int:
        """估算数据占用的 Lua 常量数量"""
        count = 0
        for k, v in data.items():
            count += 1  # key
            if isinstance(v, dict):
                count += self._estimate_constant_count(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, (dict, list)):
                        count += self._estimate_constant_count(item) if isinstance(item, dict) else len(item)
                    else:
                        count += 1
            else:
                count += 1
        return count

    def _generate_safe_var_name(self, name: str) -> str:
        """生成安全的 Lua 变量名"""
        # 移除特殊字符，只保留字母、数字和下划线
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # 确保不以数字开头
        if safe_name and safe_name[0].isdigit():
            safe_name = '_' + safe_name
        return safe_name

    def export(self, worksheet: WorkSheet, output_path: str, var_name: str = None, mode: str = 'cs') -> bool:
        """
        导出为 Lua 格式
        :param worksheet: 工作表数据
        :param output_path: 输出文件路径（不含扩展名）
        :param var_name: 变量名（默认使用文件名）
        :param mode: 导出模式 c=客户端, s=服务端, cs=两者
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if not var_name:
                var_name = os.path.basename(output_path)

            # 生成安全的变量名
            safe_var_name = self._generate_safe_var_name(var_name)

            # 收集所有数据行
            data_rows = []
            for row in worksheet.rows:
                key = row.get("id") or row.get("ID") or row.get("key")
                if key is not None:
                    value_dict = row.to_dict(mode)
                    if value_dict:  # 只添加非空数据
                        data_rows.append((key, value_dict))

            # 估算总常量数
            total_constants = sum(self._estimate_constant_count(row_data) for _, row_data in data_rows)

            # 判断是否需要分块
            need_chunking = total_constants > self.LUA_CONSTANT_LIMIT

            if need_chunking:
                return self._export_chunked(data_rows, output_path, safe_var_name, mode)
            else:
                return self._export_single(data_rows, output_path, safe_var_name, mode)

        except Exception as e:
            return False

    def _export_single(self, data_rows: List[tuple], output_path: str, var_name: str, mode: str) -> bool:
        """导出为单个 Lua 表（不分块）"""
        lines = []
        lines.append(f"local {var_name} = {{")

        for key, row_data in data_rows:
            key_str = f'["{str(key)}"]'
            value_str = self._dict_to_lua_str(row_data, indent=1)
            lines.append(f"    {key_str} = {value_str},")

        lines.append("}")
        lines.append("")

        # 添加访问函数
        lines.extend(self._generate_access_functions(var_name))

        # 写入文件
        if not output_path.endswith('.lua'):
            file_path = f"{output_path}.lua"
        else:
            file_path = output_path

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return True

    def _export_chunked(self, data_rows: List[tuple], output_path: str, var_name: str, mode: str) -> bool:
        """导出为分块的 Lua 表（避免常量限制）"""
        lines = []
        lines.append(f"-- {var_name} 配置表（自动分块）")
        lines.append("")

        # 分块存储
        chunks = []
        current_chunk = {}
        current_constants = 0

        for key, row_data in data_rows:
            row_constants = self._estimate_constant_count(row_data)

            # 如果当前块已满，创建新块
            if current_chunk and current_constants + row_constants > self.LUA_CONSTANT_LIMIT:
                chunks.append(current_chunk)
                current_chunk = {}
                current_constants = 0

            current_chunk[key] = row_data
            current_constants += row_constants

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        # 生成各块函数
        for i, chunk in enumerate(chunks):
            chunk_func_name = f"_{var_name}_chunk_{i}"
            lines.append(f"local function {chunk_func_name}()")
            lines.append(f"    return {{")

            for key, row_data in chunk.items():
                key_str = f'["{str(key)}"]'
                value_str = self._dict_to_lua_str(row_data, indent=2)
                lines.append(f"        {key_str} = {value_str},")

            lines.append("    }")
            lines.append("end")
            lines.append("")

        # 合并所有块的主表
        lines.append(f"local {var_name} = {{}}")
        for i in range(len(chunks)):
            chunk_func_name = f"_{var_name}_chunk_{i}"
            lines.append(f"for k, v in pairs({chunk_func_name}()) do {var_name}[k] = v end")

        lines.append("")

        # 添加访问函数
        lines.extend(self._generate_access_functions(var_name))

        # 写入文件
        if not output_path.endswith('.lua'):
            file_path = f"{output_path}.lua"
        else:
            file_path = output_path

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return True

    def _generate_access_functions(self, var_name: str) -> List[str]:
        """生成访问函数"""
        lines = []
        lines.append(f"-- 访问函数")
        lines.append(f"local _{var_name}_cache = nil")
        lines.append(f"local _{var_name}_keys = nil")
        lines.append("")

        # GetAll 函数
        lines.append(f"function {var_name}.GetAll()")
        lines.append(f"    if _{var_name}_cache == nil then")
        lines.append(f"        _{var_name}_cache = {{}}")
        lines.append(f"        for k, v in pairs({var_name}) do")
        lines.append(f"            if type(v) == 'table' and v.id ~= nil then")
        lines.append(f"                _{var_name}_cache[k] = v")
        lines.append(f"            end")
        lines.append(f"        end")
        lines.append(f"    end")
        lines.append(f"    return _{var_name}_cache")
        lines.append("end")
        lines.append("")

        # GetIds 函数
        lines.append(f"function {var_name}.GetIds()")
        lines.append(f"    if _{var_name}_keys == nil then")
        lines.append(f"        _{var_name}_keys = {{}}")
        lines.append(f"        for k, _ in pairs({var_name}.GetAll()) do")
        lines.append(f"            table.insert(_{var_name}_keys, k)")
        lines.append(f"        end")
        lines.append(f"    end")
        lines.append(f"    return _{var_name}_keys")
        lines.append("end")
        lines.append("")

        # GetValueByID 函数
        lines.append(f"function {var_name}.GetValueByID(id)")
        lines.append(f"    return {var_name}[tostring(id)] or {var_name}[id]")
        lines.append("end")
        lines.append("")

        # ExistID 函数
        lines.append(f"function {var_name}.ExistID(id)")
        lines.append(f"    return {var_name}[tostring(id)] ~= nil or {var_name}[id] ~= nil")
        lines.append("end")
        lines.append("")

        # 返回主表
        lines.append(f"return {var_name}")

        return lines

    def _dict_to_lua_str(self, data: dict, indent: int = 0) -> str:
        """将字典转换为 Lua 字符串"""
        if not data:
            return "{}"

        pairs = []
        for k, v in data.items():
            if isinstance(v, dict):
                v_str = self._dict_to_lua_str(v, indent + 1)
            elif isinstance(v, list):
                v_str = self._list_to_lua_str(v, indent + 1)
            else:
                v_str = self._format_lua_value(v)
            pairs.append(f'["{str(k)}"] = {v_str}')

        prefix = "    " * indent
        return "{" + ", ".join(pairs) + "}"

    def _list_to_lua_str(self, data: list, indent: int = 0) -> str:
        """将列表转换为 Lua 字符串"""
        if not data:
            return "{}"

        items = [self._format_lua_value(v) for v in data]
        return "{" + ", ".join(items) + "}"
