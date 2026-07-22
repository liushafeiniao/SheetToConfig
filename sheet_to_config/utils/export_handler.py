# -*- coding: utf-8 -*-
"""
导出处理模块
处理表格导出操作
"""
import os
import traceback
from threading import Thread
from typing import Callable, Optional
from sheet_to_config.utils.exporter import ExcelConverter
from sheet_to_config.i18n import get_locale, tr


class ExportHandler:
    """导出处理器（集成版）"""

    def __init__(self, project, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化导出处理器
        :param project: 项目对象
        :param log_callback: 日志回调函数
        """
        self.project = project
        self.log_callback = log_callback
        self._running = False
        self.converter = ExcelConverter(self._relay_converter_log)
        self.last_result = None

    def _log(self, message: str):
        """输出日志"""
        if not message:
            return
        if self.log_callback:
            self.log_callback(message)

    def _relay_converter_log(self, message: str):
        """Keep raw exporter failures out of localized UI logs.

        Failures are emitted below from structured issues, keyed by their
        stable issue code. Successful artifact lines contain only filenames
        and format markers and can pass through unchanged.
        """
        text = str(message or '')
        if '[ERROR]' in text:
            return
        if text.startswith('Warning: assetRoot is not configured'):
            key = (
                'log.asset_root_fallback'
                if 'legacy client output directory' in text
                else 'log.asset_root_disabled'
            )
            self._log(f"⚠ {tr(key)}")
            return
        self._log(text)

    @staticmethod
    def _localized_issue_message(issue: dict) -> str:
        code = str(issue.get('code') or 'UNKNOWN')
        key = f"issue.{code.lower()}"
        value = issue.get('rawValue')
        rendered = tr(
            key,
            code=code,
            field=str(issue.get('field') or '-'),
            value='-' if value is None else str(value),
        )
        if rendered == key:
            rendered = tr('issue.default', code=code)
        detail = str(issue.get('message') or '').strip()
        if detail and detail != rendered:
            return f"{rendered} | {detail}"
        return rendered

    def export(self, mode: str = '1', filename: str = '',
               allow_breaking_proto_change: bool = False,
               export_pb: bool = True, validation_only: bool = False) -> bool:
        """
        执行导出操作
        :param mode: 导出模式
                    '1' - 导所有配置文件（客户端+服务器）
                    '2' - 导客户端所有配置文件
                    '3' - 导服务器所有配置文件
                    '4' - 导指定配置文件
        :param filename: 指定文件名（仅 mode='4' 时使用）
        :return: 是否成功
        """
        if self._running:
            self._log(tr('log.export_running'))
            return False

        self._running = True
        try:
            # 检查表格目录是否存在
            if not os.path.exists(self.project.table_path):
                self._log(tr('log.table_dir_missing', path=self.project.table_path))
                return False

            # 映射模式
            mode_map = {'1': 'cs', '2': 'c', '3': 's', '4': 'cs'}
            export_mode = mode_map.get(mode, 'cs')

            mode_names = {
                '1': tr('log.mode_all'),
                '2': tr('log.mode_client'),
                '3': tr('log.mode_server'),
                '4': tr('log.mode_specific', name=filename),
            }

            # 简化的日志头部
            self._log(tr(
                'log.validating' if validation_only else 'log.exporting',
                name=self.project.name,
            ))
            self._log(tr('log.export_mode', mode=mode_names.get(mode, mode)))
            self._log("─" * 40)

            # 创建输出目录
            if not validation_only and self.project.client_path:
                os.makedirs(self.project.client_path, exist_ok=True)
            if not validation_only and self.project.server_path:
                os.makedirs(self.project.server_path, exist_ok=True)
            if not validation_only and self.project.csharp_path:
                os.makedirs(self.project.csharp_path, exist_ok=True)

            # 执行导出
            result = self.converter.export_all(
                table_dir=self.project.table_path,
                client_path=self.project.client_path or '',
                server_path=self.project.server_path or '',
                mode=export_mode,
                filename=filename if mode == '4' else None,
                allow_breaking_proto_change=allow_breaking_proto_change,
                csharp_path=self.project.csharp_path or '',
                export_pb=export_pb,
                validation_only=validation_only,
                asset_root=getattr(self.project, 'asset_root', '') or '',
                locale=get_locale(),
            )
            self.last_result = result

            for issue in result.get('issues', []):
                location = issue.get('path') or issue.get('file') or tr('log.export_task')
                message = self._localized_issue_message(issue)
                self._log(f"  ✗ [{issue.get('code')}] {location}: {message}")
            for platform, changes in result.get('changes', {}).items():
                for action, label_key in (
                    ('added', 'log.change_added'), ('modified', 'log.change_modified'), ('removed', 'log.change_removed')
                ):
                    paths = changes.get(action, [])
                    if paths:
                        self._log(tr('log.changes', platform=platform, action=tr(label_key), paths=', '.join(paths)))

            # 统计结果
            total = result['count']
            success = result['success_count']
            fail = result['fail_count']

            self._log("─" * 40)
            if result['success']:
                action = tr('log.action_validate' if validation_only else 'log.action_export')
                self._log(f"✓ {tr('log.export_summary_ok', action=action, total=total, success=success)}")
            else:
                action = tr('log.action_validate' if validation_only else 'log.action_export')
                self._log(f"✗ {tr('log.export_summary_failed', action=action, total=total, success=success, fail=fail)}")

            return result['success']

        finally:
            self._running = False

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    def stop(self):
        """停止导出"""
        self._running = False
        self._log(tr('log.export_stopped'))


class ExportHandlerAsync:
    """异步导出处理器（使用线程）"""

    def __init__(self, project, log_callback: Optional[Callable[[str], None]] = None,
                 complete_callback: Optional[Callable[[bool], None]] = None):
        """
        初始化异步导出处理器
        :param project: 项目对象
        :param log_callback: 日志回调函数
        :param complete_callback: 完成回调函数
        """
        self.project = project
        self.log_callback = log_callback
        self.complete_callback = complete_callback
        self.handler = ExportHandler(project, log_callback)
        self.thread = None

    def export_async(self, mode: str = '1', filename: str = '',
                     allow_breaking_proto_change: bool = False,
                     export_pb: bool = True, validation_only: bool = False):
        """异步执行导出"""
        if self.thread and self.thread.is_alive():
            return False

        def run():
            try:
                success = self.handler.export(
                    mode, filename, allow_breaking_proto_change, export_pb,
                    validation_only,
                )
            except Exception:
                self.handler._log(tr('log.export_unhandled', detail=traceback.format_exc()))
                success = False
            if self.complete_callback:
                self.complete_callback(success)

        self.thread = Thread(target=run, daemon=True)
        self.thread.start()
        return True

    def is_running(self) -> bool:
        """是否正在运行"""
        return self.handler.is_running()

    def stop(self):
        """停止导出"""
        self.handler.stop()
