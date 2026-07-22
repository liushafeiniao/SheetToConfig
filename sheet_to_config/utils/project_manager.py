# -*- coding: utf-8 -*-
"""
项目管理模块
处理项目的增删改查
"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from sheet_to_config.app_paths import local_data_path
from sheet_to_config.i18n import tr


class Project:
    """项目数据类"""

    def __init__(self, data: dict):
        self.id = data.get('id', str(uuid.uuid4()))
        self.name = data.get('name', '')
        self.table_path = data.get('tablePath', '')
        self.export_tool_path = data.get('exportToolPath', '')
        self.client_path = data.get('clientPath', '')
        self.server_path = data.get('serverPath', '')
        self.csharp_path = data.get('csharpPath', '')
        self.asset_root = data.get('assetRoot', '')
        self.shared_path = data.get('sharedPath', '')
        self.created_at = data.get('createdAt', datetime.now().strftime('%Y-%m-%d'))
        self.description = data.get('description', '')
        self.sort_order = data.get('sortOrder', 0)  # 排序字段，数字越小越靠前
        self.icon_path = data.get('iconPath', '')  # 项目图标路径

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'tablePath': self.table_path,
            'exportToolPath': self.export_tool_path,
            'clientPath': self.client_path,
            'serverPath': self.server_path,
            'csharpPath': self.csharp_path,
            'assetRoot': self.asset_root,
            'sharedPath': self.shared_path,
            'createdAt': self.created_at,
            'description': self.description,
            'sortOrder': self.sort_order,
            'iconPath': self.icon_path
        }

    def validate(self, check_path_exists: bool = True) -> tuple[bool, str]:
        """
        验证项目配置
        :param check_path_exists: 是否检查路径是否存在（编辑时设为False，避免网络盘等问题）
        """
        if not self.name:
            return False, tr('project.required', field=tr('dialog.project_name'))
        if not self.table_path:
            return False, tr('project.required', field=tr('main.table_path'))
        # 导表工具已集成，不再需要验证外部工具路径
        if not self.client_path:
            return False, tr('project.required', field=tr('main.client_path'))
        if not self.server_path:
            return False, tr('project.required', field=tr('main.server_path'))
        # 同步目录改为可选项，不再强制校验
        # （原“共享目录不能为空”校验已移除）

        # 验证路径是否存在（仅在新增项目时检查）
        if check_path_exists:
            if not os.path.exists(self.table_path):
                return False, tr('project.table_path_missing', path=self.table_path)
            # 导表工具已集成，不再需要验证外部工具路径

        return True, ""


class ProjectManager:
    """项目管理器"""

    def __init__(self, projects_file: Optional[str] = None):
        self.projects_file = projects_file or str(local_data_path('projects.json'))
        self.projects: List[Project] = []
        self.theme_config = {
            'current_theme': 'cyber_blue',
            'custom_colors': None
        }
        self.load()

    def load(self):
        """从文件加载项目和主题配置"""
        if not os.path.exists(self.projects_file):
            self.projects = []
            return

        try:
            with open(self.projects_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.projects = [Project(p) for p in data.get('projects', [])]
                
                # 加载主题配置
                theme_data = data.get('theme', {})
                self.theme_config['current_theme'] = theme_data.get('current_theme', 'cyber_blue')
                self.theme_config['custom_colors'] = theme_data.get('custom_colors', None)
            
            # 为旧项目设置默认 sort_order
            need_save = False
            for i, project in enumerate(self.projects):
                if project.sort_order == 0:
                    project.sort_order = (i + 1) * 10
                    need_save = True
            
            if need_save:
                self.save()
        except Exception as e:
            print(tr('project.load_failed', detail=e))
            self.projects = []

    def save(self):
        """保存项目和主题配置到文件"""
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.projects_file))
            os.makedirs(parent_dir, exist_ok=True)
            data = {
                'projects': [p.to_dict() for p in self.projects],
                'theme': self.theme_config
            }
            with open(self.projects_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(tr('project.save_config_failed', detail=e))
            return False
    
    def get_theme_config(self) -> dict:
        """获取主题配置"""
        return self.theme_config.copy()
    
    def save_theme_config(self, current_theme: str, custom_colors: dict = None):
        """保存主题配置"""
        self.theme_config['current_theme'] = current_theme
        self.theme_config['custom_colors'] = custom_colors
        return self.save()

    def add_project(self, project: Project) -> tuple[bool, str]:
        """添加项目"""
        valid, msg = project.validate()
        if not valid:
            return False, msg

        # 检查名称是否重复
        for p in self.projects:
            if p.name == project.name:
                return False, tr('project.name_exists', name=project.name)

        # 设置排序顺序为最大值+1
        if self.projects:
            max_order = max(p.sort_order for p in self.projects)
            project.sort_order = max_order + 10
        else:
            project.sort_order = 10

        self.projects.append(project)
        if self.save():
            return True, tr('project.added')
        return False, tr('project.save_failed')

    def update_project(self, project: Project) -> tuple[bool, str]:
        """更新项目"""
        # 编辑时跳过路径检查，允许用户修改其他字段
        valid, msg = project.validate(check_path_exists=False)
        if not valid:
            return False, msg

        # 查找并更新项目
        for i, p in enumerate(self.projects):
            if p.id == project.id:
                self.projects[i] = project
                if self.save():
                    return True, tr('project.updated')
                return False, tr('project.save_failed')

        return False, tr('project.not_found')

    def delete_project(self, project_id: str) -> tuple[bool, str]:
        """删除项目"""
        for i, p in enumerate(self.projects):
            if p.id == project_id:
                self.projects.pop(i)
                if self.save():
                    return True, tr('project.deleted')
                return False, tr('project.save_failed')

        return False, tr('project.not_found')

    def get_project(self, project_id: str) -> Optional[Project]:
        """获取单个项目"""
        for p in self.projects:
            if p.id == project_id:
                return p
        return None

    def get_all_projects(self, sorted_by_order: bool = True) -> List[Project]:
        """获取所有项目"""
        if sorted_by_order:
            # 按 sort_order 排序，相同则按创建时间
            return sorted(self.projects, key=lambda p: (p.sort_order, p.created_at))
        return self.projects
    
    def move_project(self, project_id: str, direction: str) -> tuple[bool, str]:
        """
        移动项目位置
        :param project_id: 项目ID
        :param direction: 'up' 或 'down'
        """
        # 获取排序后的项目列表
        sorted_projects = self.get_all_projects(sorted_by_order=True)
        
        # 找到当前项目索引
        current_idx = None
        for i, p in enumerate(sorted_projects):
            if p.id == project_id:
                current_idx = i
                break
        
        if current_idx is None:
            return False, tr('project.not_found')
        
        if direction == 'up':
            if current_idx == 0:
                return False, tr('project.already_first')
            target_idx = current_idx - 1
        elif direction == 'down':
            if current_idx == len(sorted_projects) - 1:
                return False, tr('project.already_last')
            target_idx = current_idx + 1
        else:
            return False, tr('project.invalid_direction')
        
        # 交换 sort_order
        current_project = sorted_projects[current_idx]
        target_project = sorted_projects[target_idx]
        
        # 交换排序值
        current_project.sort_order, target_project.sort_order = target_project.sort_order, current_project.sort_order
        
        if self.save():
            return True, tr('project.moved')
        return False, tr('project.save_failed')

    def reorder_projects(self, ordered_ids: List[str]) -> tuple[bool, str]:
        """
        按给定 ID 顺序重排项目（列表拖拽排序后调用）
        :param ordered_ids: 按新顺序排列的项目 ID 列表
        """
        id_to_project = {p.id: p for p in self.projects}
        order = 10
        for pid in ordered_ids:
            project = id_to_project.get(pid)
            if project is not None:
                project.sort_order = order
                order += 10
        # 未包含在列表中的项目排到末尾，防止数据丢失
        for p in self.projects:
            if p.id not in ordered_ids:
                p.sort_order = order
                order += 10
        if self.save():
            return True, tr('project.order_saved')
        return False, tr('project.save_failed')

    def search_projects(self, keyword: str) -> List[Project]:
        """搜索项目"""
        projects = self.get_all_projects()
        if not keyword:
            return projects

        keyword = keyword.lower()
        result = []
        for p in projects:
            if (keyword in p.name.lower() or
                keyword in p.table_path.lower() or
                keyword in p.description.lower()):
                result.append(p)
        return result

    def export_config(self, export_path: str) -> tuple[bool, str]:
        """导出配置到指定文件"""
        try:
            data = {
                'projects': [p.to_dict() for p in self.projects],
                'exportedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'version': '1.0'
            }
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True, tr('project.config_exported', path=export_path)
        except Exception as e:
            return False, tr('project.config_export_failed', detail=e)

    def import_config(self, import_path: str, merge: bool = False) -> tuple[bool, str]:
        """
        从指定文件导入配置
        :param import_path: 导入文件路径
        :param merge: 是否合并（True=合并，False=覆盖）
        """
        try:
            if not os.path.exists(import_path):
                return False, tr('project.import_missing', path=import_path)

            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            imported_projects = [Project(p) for p in data.get('projects', [])]

            if merge:
                # 合并模式：添加不存在的项目，更新已存在的项目
                count = 0
                for imp_proj in imported_projects:
                    found = False
                    for i, existing_proj in enumerate(self.projects):
                        if existing_proj.id == imp_proj.id:
                            # 更新已存在的项目
                            self.projects[i] = imp_proj
                            count += 1
                            found = True
                            break

                    if not found:
                        # 检查名称是否重复
                        name_exists = any(p.name == imp_proj.name for p in self.projects)
                        if not name_exists:
                            self.projects.append(imp_proj)
                            count += 1

                self.save()
                return True, tr('project.config_merged', count=count)
            else:
                # 覆盖模式：完全替换
                self.projects = imported_projects
                self.save()
                return True, tr('project.config_imported', count=len(imported_projects))

        except Exception as e:
            return False, tr('project.config_import_failed', detail=e)
