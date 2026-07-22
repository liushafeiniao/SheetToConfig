# -*- coding: utf-8 -*-
"""
JSON 格式导出器
"""
import json
import os
from typing import Dict, Any
from ..core import WorkSheet


class JsonExporter:
    """JSON 格式导出器"""

    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def _log(self, message: str):
        # 日志由 converter 统一处理，这里不再输出
        pass

    def export(self, worksheet: WorkSheet, output_path: str, mode: str = 'cs') -> bool:
        """
        导出为 JSON 格式
        :param worksheet: 工作表数据
        :param output_path: 输出文件路径（不含扩展名）
        :param mode: 导出模式 c=客户端, s=服务端, cs=两者
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 转换为字典格式
            result = {}
            for row in worksheet.rows:
                key = row.get("id") or row.get("ID") or row.get("key")
                if key:
                    result[str(key)] = row.to_dict(mode)

            # 写入文件（如果output_path已经包含.json扩展名，不再重复添加）
            if not output_path.endswith('.json'):
                file_path = f"{output_path}.json"
            else:
                file_path = output_path
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return True

        except Exception:
            return False

    def export_multi(self, worksheets: Dict[str, WorkSheet], output_path: str, mode: str = 'cs') -> bool:
        """
        导出多个工作表到单个 JSON 文件
        :param worksheets: 工作表字典 {文件名: WorkSheet}
        :param output_path: 输出文件路径
        :param mode: 导出模式
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            result = {}
            for file_name, ws in worksheets.items():
                data = {}
                for row in ws.rows:
                    key = row.get("id") or row.get("ID") or row.get("key")
                    if key:
                        data[str(key)] = row.to_dict(mode)
                result[file_name] = data

            file_path = f"{output_path}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False
