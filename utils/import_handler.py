# -*- coding: utf-8 -*-
"""
导入处理模块
处理表格导入共享操作
"""
import os
import shutil
from threading import Thread
from typing import Callable, Optional
from pathlib import Path
from i18n import tr


class ImportHandler:
    """导入处理器"""

    def __init__(self, project, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化导入处理器
        :param project: 项目对象
        :param log_callback: 日志回调函数
        """
        self.project = project
        self.log_callback = log_callback
        self._running = False

    def _log(self, message: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message)

    def import_shared(self) -> bool:
        """
        执行导入共享操作
        从项目的 table_path 复制 xlsx 文件到 shared_path
        :return: 是否成功
        """
        if self._running:
            self._log(tr('log.sync_running'))
            return False

        self._running = True
        try:
            self._log(tr('log.syncing', name=self.project.name))
            self._log(tr('log.source_dir', path=self.project.table_path))
            self._log(tr('log.target_dir', path=self.project.shared_path))

            # 检查源目录是否存在
            if not os.path.exists(self.project.table_path):
                self._log(tr('log.sync_source_missing_path', path=self.project.table_path))
                return False

            return self._import_direct()

        finally:
            self._running = False

    def _import_direct(self) -> bool:
        """直接复制 xlsx 文件"""
        try:
            # 创建目标目录
            os.makedirs(self.project.shared_path, exist_ok=True)

            # 查找所有 xlsx 文件
            table_dir = Path(self.project.table_path)
            xlsx_files = list(table_dir.rglob('*.xlsx'))

            if not xlsx_files:
                self._log(tr('log.xlsx_not_found', path=self.project.table_path))
                return False

            self._log(tr('log.xlsx_found', count=len(xlsx_files)))

            # 复制文件
            copied_count = 0
            for xlsx_file in xlsx_files:
                if xlsx_file.name.startswith('~$'):
                    continue  # 跳过临时文件

                try:
                    dest_file = os.path.join(self.project.shared_path, xlsx_file.name)
                    shutil.copy2(xlsx_file, dest_file)
                    self._log(f"  ✓ {xlsx_file.name}")
                    copied_count += 1
                except Exception as e:
                    self._log(tr('log.copy_failed', name=xlsx_file.name, detail=e))

            if copied_count > 0:
                self._log(tr('log.sync_copied_count', count=copied_count))
                return True
            else:
                self._log(tr('log.no_files_copied'))
                return False

        except Exception as e:
            self._log(tr('log.sync_failed', detail=e))
            return False

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    def stop(self):
        """停止导入"""
        self._running = False
        self._log(tr('log.sync_stopped'))


class ImportHandlerAsync:
    """异步导入处理器（使用线程）"""

    def __init__(self, project,
                 log_callback: Optional[Callable[[str], None]] = None,
                 complete_callback: Optional[Callable[[bool], None]] = None):
        """
        初始化异步导入处理器
        :param project: 项目对象
        :param log_callback: 日志回调函数
        :param complete_callback: 完成回调函数
        """
        self.project = project
        self.log_callback = log_callback
        self.complete_callback = complete_callback
        self.handler = ImportHandler(project, log_callback)
        self.thread = None

    def import_async(self):
        """异步执行导入"""
        if self.thread and self.thread.is_alive():
            return False

        def run():
            success = self.handler.import_shared()
            if self.complete_callback:
                self.complete_callback(success)

        self.thread = Thread(target=run, daemon=True)
        self.thread.start()
        return True

    def is_running(self) -> bool:
        """是否正在运行"""
        return self.handler.is_running()

    def stop(self):
        """停止导入"""
        self.handler.stop()
