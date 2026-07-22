# -*- coding: utf-8 -*-
"""
SheetToConfig 多项目表格管理工具
主程序（PyQt5 版本）
"""
import sys
import os
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QMessageBox, QFileDialog, QFrame, QAbstractItemView, QAction, QSizePolicy,
    QToolButton, QMenu
)
from PyQt5 import QtCore, QtGui
import re
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPixmap

import icons
from version import __version__, APP_TITLE
from styles import get_stylesheet
from widgets import ElidedLabel, ProjectCardDelegate
from utils.project_manager import Project, ProjectManager
from utils.export_handler import ExportHandlerAsync
from utils.import_handler import ImportHandlerAsync
from utils.os_integration import open_local_path
# SVN功能已禁用
# from utils.svn_handler import SVNHandlerAsync
from theme_config import (
    THEME_PRESETS, load_theme_config, save_theme_config,
    get_current_theme_colors, get_scaled_bg_image, localized_theme_name
)
from dialogs import (
    ProjectEditDialog, ThemeDialog, ImportOptionDialog,
    ExportOptionDialog, AboutDialog
)
from i18n import LANGUAGE_NAMES, SUPPORTED_LOCALES, get_locale, language_name, set_locale, tr

LOG_ERROR = '#ff4757'
LOG_WARNING = '#f0a500'

# 日志行解析：[HH:MM:SS] [可选项目名] 正文
LOG_LINE_RE = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s*(?:\[([^\]]+)\]\s*)?(.*)$')
# 正文开头的 emoji 标记（显示时用统一状态图标替代）
EMOJI_PREFIX_RE = re.compile(
    r'^[\s🀀-🫿☀-➿⬀-⯿️←-⇿]+'
)
LOG_LEVEL_RE = re.compile(r'\[(ERROR|WARNING|SUCCESS|INFO)\]\s*')


class SheetToConfigWindow(QMainWindow):
    """主窗口"""

    # 导出在 Python 后台线程执行。任何界面写入都必须通过信号回到主线程，
    # 否则 QTextEdit 等 Qt 控件会随机崩溃或使 EXE 直接退出。
    export_log_requested = QtCore.pyqtSignal(str, str)
    export_finished = QtCore.pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.project_manager = ProjectManager()
        self.current_project = None
        self.current_handler = None
        self.export_in_progress = False
        self.last_export_filename = ""
        self.export_log_requested.connect(self._append_export_log)
        self.export_finished.connect(self.on_export_complete)

        # 项目日志存储 - 每个项目独立日志
        self.project_logs = {}  # {project_id: [log_messages]}
        self.current_log_messages = []  # 当前显示的日志消息

        # 加载主题
        self.load_theme()

        self.init_ui()
        self.load_projects()

    def load_theme(self):
        """加载主题配置"""
        config = load_theme_config()
        self.current_theme_id = config.get('current_theme', 'picunbg_teal')
        self.custom_colors = config.get('custom_colors')
        # 背景图缩放后渲染，避免大图 border-image 每次重绘全尺寸缩放导致卡顿
        self.bg_image = get_scaled_bg_image(config.get('bg_image'))

        if self.current_theme_id == 'custom' and self.custom_colors:
            self.colors = self.custom_colors.copy()
        else:
            self.colors = THEME_PRESETS.get(
                self.current_theme_id,
                THEME_PRESETS['picunbg_teal']
            ).copy()
        self.colors['name'] = localized_theme_name(self.current_theme_id)

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"{APP_TITLE} · {tr('app.window_subtitle')} v{__version__}")
        self.setMinimumSize(1280, 800)
        self.setWindowIcon(icons.get_icon('app', self.colors['accent'], 32))

        # 接受文件/文件夹拖入
        self.setAcceptDrops(True)

        # 应用样式（唯一来源：styles.get_stylesheet）
        self.apply_styles()

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        central_widget.setLayout(main_layout)

        # 左侧：项目列表
        left_widget = self._create_left_panel()
        main_layout.addWidget(left_widget, 0)

        # 右侧：项目详情和操作
        right_widget = self._create_right_panel()
        main_layout.addWidget(right_widget, 1)

        # 拖放提示遮罩（默认隐藏）
        self.drop_overlay = QLabel(tr('main.drop_overlay'), central_widget)
        self.drop_overlay.setObjectName("dropOverlay")
        self.drop_overlay.setAlignment(Qt.AlignCenter)
        self.drop_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.drop_overlay.hide()

        # 状态栏提示
        self.statusBar().showMessage(tr('main.status'))

    def resizeEvent(self, event):
        """保持拖放遮罩铺满窗口"""
        super().resizeEvent(event)
        if hasattr(self, 'drop_overlay') and self.drop_overlay.isVisible():
            self.drop_overlay.setGeometry(self.centralWidget().rect())

    # ==================== 左侧面板 ====================

    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(320)

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.get_pixmap('app', self.colors['accent'], 22))
        logo.setFixedSize(24, 24)
        title = QLabel(tr('app.title'))
        title.setObjectName("appTitle")
        version = QLabel(f"v{__version__}")
        version.setObjectName("versionBadge")

        header.addWidget(logo)
        header.addSpacing(4)
        header.addWidget(title)
        header.addWidget(version)
        header.addStretch()
        layout.addLayout(header)

        # 新建项目按钮
        self.add_btn = QPushButton(f"  {tr('main.new_project')}")
        self.add_btn.setObjectName("primary")
        self.add_btn.setIcon(icons.get_icon('plus', self.colors['bg_dark'], 15))
        self.add_btn.setFixedHeight(42)
        self.add_btn.clicked.connect(self.add_project)
        layout.addWidget(self.add_btn)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr('main.search'))
        self.search_input.setFixedHeight(36)
        search_action = QAction(self.search_input)
        search_action.setIcon(icons.get_icon('search', self.colors['text_dim'], 14))
        self.search_input.addAction(search_action, QLineEdit.LeadingPosition)
        self.search_input.textChanged.connect(self.on_search)
        layout.addWidget(self.search_input)

        # 分组小标题
        section = QLabel(tr('main.project_list'))
        section.setObjectName("listSection")
        layout.addWidget(section)

        # 项目列表（支持拖拽排序 + 右键菜单）
        self.project_list = QListWidget()
        self.project_list.setObjectName("projectList")
        self.project_list.setFrameShape(QFrame.NoFrame)
        self.project_list.setWordWrap(True)
        self.project_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.project_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.project_list.setDefaultDropAction(Qt.MoveAction)
        self.project_list.setDropIndicatorShown(True)
        self.project_list.setToolTip(tr('main.status'))
        self.project_list.setItemDelegate(ProjectCardDelegate(self.colors, self.project_list))
        self.project_list.viewport().installEventFilter(self)
        self.project_list.itemClicked.connect(self.on_project_selected)
        self.project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self.show_project_menu)
        self.project_list.model().rowsMoved.connect(self.on_rows_moved)
        layout.addWidget(self.project_list)

        return panel

    # ==================== 右侧面板 ====================

    def _create_right_panel(self):
        """创建右侧面板（开敞布局：无嵌套卡片，靠留白与分隔线分区）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(18)
        layout.setContentsMargins(8, 0, 0, 0)

        # ===== 顶部：项目名 + 当前项目徽章 + 关于/主题 =====
        header = QHBoxLayout()
        header.setSpacing(10)

        self.detail_icon = QLabel()
        self.detail_icon.setFixedSize(30, 30)
        self.detail_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_icon.setPixmap(icons.get_pixmap('folder', self.colors['accent'], 22))

        self.detail_name = QLabel(tr('main.select_project'))
        self.detail_name.setObjectName("projectName")

        self.active_badge = QLabel(tr('main.current_project'))
        self.active_badge.setObjectName("activeBadge")
        self.active_badge.hide()

        header.addWidget(self.detail_icon)
        header.addWidget(self.detail_name)
        header.addWidget(self.active_badge)
        header.addStretch()

        # 关于按钮
        self.about_btn = QPushButton(f"  {tr('main.about')}")
        self.about_btn.setIcon(icons.get_icon('info', self.colors['text_light'], 14))
        self.about_btn.setFixedHeight(32)
        self.about_btn.clicked.connect(self.show_about)
        header.addWidget(self.about_btn)

        # 主题按钮
        self.theme_btn = QPushButton(f"  {tr('main.theme')}")
        self.theme_btn.setIcon(icons.get_icon('theme', self.colors['text_light'], 14))
        self.theme_btn.setFixedHeight(32)
        self.theme_btn.clicked.connect(self.change_theme)
        header.addWidget(self.theme_btn)

        self.language_btn = QToolButton()
        self.language_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.language_btn.setIcon(icons.get_icon('language', self.colors['text_light'], 14))
        self.language_btn.setText(language_name(get_locale()))
        self.language_btn.setToolTip(tr('main.language'))
        self.language_btn.setPopupMode(QToolButton.InstantPopup)
        language_menu = QMenu(self.language_btn)
        for locale_id in SUPPORTED_LOCALES:
            action = language_menu.addAction(LANGUAGE_NAMES[locale_id])
            action.setCheckable(True)
            action.setChecked(locale_id == get_locale())
            action.triggered.connect(lambda checked=False, value=locale_id: self.change_language(value))
        self.language_btn.setMenu(language_menu)
        header.addWidget(self.language_btn)

        layout.addLayout(header)

        # ===== 项目详情（可伸缩：点击箭头折叠/展开） =====
        detail_section = QVBoxLayout()
        detail_section.setSpacing(0)

        detail_header = QHBoxLayout()
        detail_title = QLabel(tr('main.project_details'))
        detail_title.setObjectName("cardTitle")
        detail_header.addWidget(detail_title)
        detail_header.addStretch()

        self.detail_toggle_btn = QPushButton(f"  {tr('dialog.collapse')}")
        self.detail_toggle_btn.setIcon(icons.get_icon('up', self.colors['text_dim'], 13))
        self.detail_toggle_btn.setToolTip(tr('main.collapse_details'))
        self.detail_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.detail_toggle_btn.setFixedHeight(28)
        self.detail_toggle_btn.clicked.connect(self.toggle_detail_section)
        detail_header.addWidget(self.detail_toggle_btn)

        detail_section.addLayout(detail_header)
        detail_section.addSpacing(4)

        self.detail_container = QWidget()
        detail_rows = QVBoxLayout(self.detail_container)
        detail_rows.setSpacing(0)
        detail_rows.setContentsMargins(0, 0, 0, 0)

        detail_labels = [
            tr('main.table_path'), tr('main.client_path'), tr('main.server_path'),
            tr('main.csharp_path'), tr('main.asset_root'), tr('main.shared_path'),
            tr('main.description'),
        ]
        metrics = QtGui.QFontMetrics(QApplication.font())
        self._detail_label_width = max(
            96, *(metrics.horizontalAdvance(text) + 12 for text in detail_labels)
        )

        self._create_detail_row(detail_rows, tr('main.table_path'), "detail_table", "table_path")
        self._create_detail_row(detail_rows, tr('main.client_path'), "detail_client", "client_path")
        self._create_detail_row(detail_rows, tr('main.server_path'), "detail_server", "server_path")
        self._create_detail_row(detail_rows, tr('main.csharp_path'), "detail_csharp", "csharp_path")
        self._create_detail_row(detail_rows, tr('main.asset_root'), "detail_asset", "asset_root")
        self._create_detail_row(detail_rows, tr('main.shared_path'), "detail_shared", "shared_path", with_sync=True)
        self._create_detail_row(detail_rows, tr('main.description'), "detail_desc")

        detail_section.addWidget(self.detail_container)
        layout.addLayout(detail_section)

        # ===== 主操作按钮（通栏等大） =====
        op_layout = QHBoxLayout()
        op_layout.setSpacing(12)

        self.export_btn = QPushButton(f"  {tr('main.export')}")
        self.export_btn.setObjectName("primary")
        self.export_btn.setIcon(icons.get_icon('export', self.colors['bg_dark'], 16))
        self.export_btn.setFixedHeight(48)
        self.export_btn.clicked.connect(self.export_project)
        self.export_btn.setEnabled(False)
        op_layout.addWidget(self.export_btn, 1)

        layout.addLayout(op_layout)

        # ===== 操作日志 =====
        log_section = QVBoxLayout()
        log_section.setSpacing(6)

        log_header = QHBoxLayout()
        log_title = QLabel(tr('main.operation_log'))
        log_title.setObjectName("cardTitle")
        log_header.addWidget(log_title)
        log_header.addStretch()

        self.clear_log_btn = QPushButton(tr('main.clear'))
        self.clear_log_btn.setObjectName("linkBtn")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_header.addWidget(self.clear_log_btn)

        self.copy_log_btn = QPushButton(tr('main.copy'))
        self.copy_log_btn.setObjectName("linkBtn")
        self.copy_log_btn.clicked.connect(self.copy_log)
        log_header.addWidget(self.copy_log_btn)

        log_section.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(160)
        log_section.addWidget(self.log_text)

        layout.addLayout(log_section, 1)

        return panel

    def _create_detail_row(self, parent, label_text, attr_name, path_attr=None, with_sync=False):
        """创建详情行：细分隔线 + 复制按钮（路径行另有打开文件夹按钮，同步目录行另有同步按钮）"""
        row_widget = QWidget()
        row_widget.setObjectName("detailRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(self._detail_label_width)

        value = ElidedLabel("-")
        value.setObjectName("fieldValue")
        setattr(self, attr_name, value)

        copy_btn = QPushButton()
        copy_btn.setObjectName("iconBtn")
        copy_btn.setIcon(icons.get_icon('copy', self.colors['text_dim'], 14))
        copy_btn.setFixedSize(30, 30)
        copy_btn.setToolTip(tr('main.copy'))
        copy_btn.clicked.connect(lambda checked, attr=attr_name: self.copy_detail_value(attr))

        row.addWidget(label)
        row.addWidget(value, 1)

        if with_sync:
            # 同步按钮：与同步目录同一行，放在图标按钮前面保持对齐
            self.import_btn = QPushButton(f"  {tr('main.share')}")
            self.import_btn.setObjectName("primary")
            self.import_btn.setIcon(icons.get_icon('share', self.colors['bg_dark'], 14))
            self.import_btn.setFixedSize(96, 30)
            self.import_btn.clicked.connect(self.import_project)
            self.import_btn.setEnabled(False)
            row.addWidget(self.import_btn)

        row.addWidget(copy_btn)

        if path_attr:
            open_btn = QPushButton()
            open_btn.setObjectName("iconBtn")
            open_btn.setIcon(icons.get_icon('folder', self.colors['text_dim'], 14))
            open_btn.setFixedSize(30, 30)
            open_btn.setToolTip(tr('main.open_folder'))
            open_btn.clicked.connect(lambda checked, attr=path_attr: self.open_folder(attr))
            row.addWidget(open_btn)

        parent.addWidget(row_widget)

    def toggle_detail_section(self):
        """折叠/展开项目详情"""
        collapsed = self.detail_container.isVisible()
        self.detail_container.setVisible(not collapsed)
        self.detail_toggle_btn.setIcon(
            icons.get_icon('down' if collapsed else 'up', self.colors['text_dim'], 13)
        )
        self.detail_toggle_btn.setText(
            f"  {tr('dialog.expand') if collapsed else tr('dialog.collapse')}"
        )

    def copy_detail_value(self, attr_name):
        """复制详情行的值到剪贴板"""
        label = getattr(self, attr_name, None)
        if label is None:
            return
        text = label.text()
        if not text or text == '-':
            return
        QApplication.clipboard().setText(text)
        self.log(tr('log.copied', value=text))

    def apply_styles(self):
        """应用样式（唯一来源）"""
        self.setStyleSheet(get_stylesheet(self.colors, self.bg_image))

    # ==================== 项目列表 ====================

    def _add_project_item(self, project):
        """添加一个项目卡片到列表（绘制由 ProjectCardDelegate 完成）"""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, project)
        item.setSizeHint(QtCore.QSize(280, 54))
        self.project_list.addItem(item)

    def load_projects(self, select_id=None):
        """加载项目列表"""
        self.project_list.clear()
        projects = self.project_manager.get_all_projects()

        for project in projects:
            self._add_project_item(project)

        # 恢复选中项
        if select_id:
            for i in range(self.project_list.count()):
                item = self.project_list.item(i)
                if item.data(Qt.UserRole).id == select_id:
                    self.project_list.setCurrentItem(item)
                    break

        self.log(tr('log.projects_loaded', count=len(projects)))

    def on_search(self):
        """搜索项目（搜索时禁用拖拽排序，避免顺序错乱）"""
        keyword = self.search_input.text().lower()
        projects = self.project_manager.search_projects(keyword)

        self.project_list.clear()
        for project in projects:
            self._add_project_item(project)

        # 搜索过滤状态下拖拽排序没有意义，直接禁用
        self.project_list.setDragDropMode(
            QAbstractItemView.NoDragDrop if keyword else QAbstractItemView.InternalMove
        )

    def on_rows_moved(self, parent, start, end, destination, row):
        """拖拽排序完成后持久化新顺序"""
        ids = []
        for i in range(self.project_list.count()):
            project = self.project_list.item(i).data(Qt.UserRole)
            if project:
                ids.append(project.id)
        success, msg = self.project_manager.reorder_projects(ids)
        if success:
            self.log(tr('log.order_updated'))

    def show_project_menu(self, pos):
        """项目列表右键菜单"""
        item = self.project_list.itemAt(pos)
        if not item:
            return
        # 右键时先选中该项
        self.project_list.setCurrentItem(item)
        self.on_project_selected(item)
        self._project_menu().exec_(self.project_list.viewport().mapToGlobal(pos))

    def _show_item_menu(self, project, global_pos):
        """项目卡片"···"区域菜单"""
        self._select_project(project.id)
        self._project_menu().exec_(global_pos)

    def eventFilter(self, obj, event):
        """拦截项目卡片右侧"···"区域的点击"""
        if obj is self.project_list.viewport() and event.type() == QtCore.QEvent.MouseButtonRelease:
            item = self.project_list.itemAt(event.pos())
            if item is not None:
                rect = self.project_list.visualItemRect(item)
                if event.pos().x() >= rect.right() - ProjectCardDelegate.MORE_WIDTH:
                    self._show_item_menu(item.data(Qt.UserRole), event.globalPos())
                    return True
        return super().eventFilter(obj, event)

    def _project_menu(self):
        """构建项目操作菜单"""
        menu_actions = [
            ('edit', tr('menu.edit'), self.edit_project),
            ('up', tr('menu.up'), lambda: self.move_current_project('up')),
            ('down', tr('menu.down'), lambda: self.move_current_project('down')),
            ('folder', tr('menu.open_table'), lambda: self.open_folder('table_path')),
            None,  # 分隔线
            ('trash', tr('menu.delete'), self.delete_project),
        ]
        return self._build_icon_menu(menu_actions)

    def _select_project(self, project_id):
        """按 ID 选中项目"""
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            if item.data(Qt.UserRole).id == project_id:
                self.project_list.setCurrentItem(item)
                self.on_project_selected(item)
                break

    def _build_icon_menu(self, actions):
        """构建带图标的右键菜单"""
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        for entry in actions:
            if entry is None:
                menu.addSeparator()
                continue
            icon_name, text, handler = entry
            color = LOG_ERROR if icon_name == 'trash' else self.colors['text_light']
            action = QAction(icons.get_icon(icon_name, color, 14), text, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        return menu

    def move_current_project(self, direction):
        """上移/下移当前项目"""
        if not self.current_project:
            return
        success, msg = self.project_manager.move_project(self.current_project.id, direction)
        if success:
            self.load_projects(select_id=self.current_project.id)
            self.log(tr('log.project_moved_up' if direction == 'up' else 'log.project_moved_down'))
        else:
            self.log(tr('log.warning_detail', detail=msg))

    def on_project_selected(self, item):
        """选择项目"""
        # 先保存当前项目日志（如果有）
        if self.current_project:
            old_project_id = self.current_project.id
            if old_project_id not in self.project_logs:
                self.project_logs[old_project_id] = []
            self.project_logs[old_project_id] = self.current_log_messages.copy()

        # 切换到新项目
        self.current_project = item.data(Qt.UserRole)
        self.update_detail()
        self.enable_buttons()
        self.switch_project_log()

    # ==================== 项目详情 ====================

    def update_detail(self):
        """更新项目详情"""
        if not self.current_project:
            return

        # 更新名称
        self.detail_name.setText(self.current_project.name)

        # 更新图标与徽章
        self.active_badge.show()
        if hasattr(self.current_project, 'icon_path') and self.current_project.icon_path and os.path.exists(self.current_project.icon_path):
            pixmap = QPixmap(self.current_project.icon_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.detail_icon.setPixmap(scaled)
        else:
            self.detail_icon.setPixmap(
                icons.get_pixmap('folder', self.colors['accent'], 22)
            )

        # 更新路径
        self.detail_table.setText(self.current_project.table_path)
        self.detail_client.setText(self.current_project.client_path)
        self.detail_server.setText(self.current_project.server_path)
        self.detail_csharp.setText(getattr(self.current_project, 'csharp_path', '') or "-")
        self.detail_asset.setText(getattr(self.current_project, 'asset_root', '') or "-")
        self.detail_shared.setText(self.current_project.shared_path)
        self.detail_desc.setText(self.current_project.description or "-")

    def enable_buttons(self):
        """启用按钮（编辑/删除已移至项目卡片菜单）"""
        enabled = self.current_project is not None and not self.export_in_progress
        self.export_btn.setEnabled(enabled)
        self.import_btn.setEnabled(enabled)

    # ==================== 项目增删改 ====================

    def add_project(self):
        """添加项目"""
        dialog = ProjectEditDialog(self, colors=self.colors)
        if dialog.exec_():
            data = dialog.get_data()
            project = Project(data)
            success, msg = self.project_manager.add_project(project)
            if success:
                self.load_projects()
                self.log(tr('log.success_detail', detail=msg))
            else:
                QMessageBox.warning(self, tr('log.add_failed'), msg)

    def edit_project(self):
        """编辑项目"""
        if not self.current_project:
            return

        dialog = ProjectEditDialog(self, self.current_project, self.colors)
        if dialog.exec_():
            data = dialog.get_data()
            project = Project(data)
            success, msg = self.project_manager.update_project(project)
            if success:
                self.current_project = project
                self.load_projects(select_id=project.id)
                self.update_detail()
                self.log(tr('log.success_detail', detail=msg))
            else:
                QMessageBox.warning(self, tr('log.update_failed'), msg)

    def delete_project(self):
        """删除项目"""
        if not self.current_project:
            return

        if self._ask_question(
            'dialog.confirm_delete_title', 'dialog.confirm_delete_project',
            name=self.current_project.name,
        ):
            success, msg = self.project_manager.delete_project(self.current_project.id)
            if success:
                self.current_project = None
                self.load_projects()
                self.reset_detail()
                self.log(tr('log.success_detail', detail=msg))
            else:
                QMessageBox.warning(self, tr('log.delete_failed'), msg)

    def reset_detail(self):
        """重置详情显示"""
        self.detail_name.setText(tr('main.select_project'))
        self.active_badge.hide()
        self.detail_icon.setPixmap(icons.get_pixmap('folder', self.colors['accent'], 22))
        self.detail_table.setText("-")
        self.detail_client.setText("-")
        self.detail_server.setText("-")
        self.detail_csharp.setText("-")
        self.detail_asset.setText("-")
        self.detail_shared.setText("-")
        self.detail_desc.setText("-")

        self.export_btn.setEnabled(False)
        self.import_btn.setEnabled(False)

    # ==================== 导出 / 传共享 ====================

    def export_project(self):
        """导出项目"""
        if not self.current_project:
            return
        if self.export_in_progress:
            self.log(tr('log.export_running'), level='warning')
            return

        # 显示导出选项对话框
        dialog = ExportOptionDialog(self, self.last_export_filename, self.colors)
        if dialog.exec_():
            (
                option, filename, allow_breaking_proto_change, validation_only
            ) = dialog.get_result()

            if option == "4":
                self.last_export_filename = filename

            # 后台线程只发信号，实际写入 Qt 控件在主线程完成。
            project_name = self.current_project.name

            def log_with_project(message):
                self.export_log_requested.emit(str(message), project_name)

            self.export_in_progress = True
            self.enable_buttons()
            try:
                handler = ExportHandlerAsync(
                    self.current_project,
                    log_callback=log_with_project,
                    complete_callback=self.export_finished.emit
                )
                self.current_handler = handler
                started = handler.export_async(
                    mode=option,
                    filename=filename,
                    allow_breaking_proto_change=allow_breaking_proto_change,
                    export_pb=True,
                    validation_only=validation_only,
                )
                if not started:
                    raise RuntimeError(tr('log.export_running'))
            except Exception as exc:
                self.export_in_progress = False
                self.current_handler = None
                self.enable_buttons()
                self.log(tr('log.export_unhandled', detail=exc), level='error')

    def import_project(self):
        """传共享"""
        if not self.current_project:
            return

        # 显示传共享选项对话框
        dialog = ImportOptionDialog(self, self.colors)
        if dialog.exec_():
            option = dialog.get_result()

            if option == "4":  # 取消
                return

            self.log("=" * 50)
            self.log(tr('log.syncing', name=self.current_project.name))

            # 根据选项处理
            if option == "2":  # 修改源路径
                new_path = QFileDialog.getExistingDirectory(
                    self, tr('dialog.choose_sync_source')
                )
                if new_path:
                    if not self._update_current_project_path('tablePath', new_path):
                        return
            elif option == "3":  # 修改目标路径
                new_path = QFileDialog.getExistingDirectory(
                    self, tr('dialog.choose_sync_target')
                )
                if new_path:
                    if not self._update_current_project_path('sharedPath', new_path):
                        return

            # 同步目录为可选，若未设置则提示选择目标文件夹
            if not self.current_project.shared_path:
                new_path = QFileDialog.getExistingDirectory(
                    self, tr('dialog.choose_sync_target_required')
                )
                if new_path:
                    if not self._update_current_project_path('sharedPath', new_path):
                        return
                else:
                    self.log(tr('log.sync_missing'), include_project_name=True)
                    return

            # 执行复制
            try:
                if os.path.exists(self.current_project.table_path):
                    if not os.path.exists(self.current_project.shared_path):
                        os.makedirs(self.current_project.shared_path)

                    # 复制文件
                    for item in os.listdir(self.current_project.table_path):
                        # 跳过临时文件（Excel打开时生成的~$文件）
                        if item.startswith('~$'):
                            continue
                        src = os.path.join(self.current_project.table_path, item)
                        dst = os.path.join(self.current_project.shared_path, item)
                        if os.path.isfile(src):
                            shutil.copy2(src, dst)
                            self.log(tr('log.file_copied', name=item), include_project_name=True)

                    self.log(tr('log.sync_done'), include_project_name=True)
                else:
                    self.log(tr('log.sync_source_missing'), include_project_name=True)
            except Exception as e:
                self.log(
                    tr('log.sync_failed', detail=str(e)),
                    include_project_name=True, level='error',
                )

    def _update_current_project_path(self, key, value):
        """Persist a path change before using it for a sync operation."""
        data = self.current_project.to_dict()
        data[key] = value
        updated = Project(data)
        success, message = self.project_manager.update_project(updated)
        if not success:
            QMessageBox.warning(self, tr('log.update_failed'), message)
            return False
        self.current_project = updated
        item = self.project_list.currentItem()
        if item is not None:
            item.setData(Qt.UserRole, updated)
        self.update_detail()
        return True

    # SVN功能已禁用
    # def svn_operation(self):
    #     """SVN操作"""
    #     if not self.current_project:
    #         return
    #
    #     self.log("=" * 50)
    #     self.log(f"📋 SVN操作: {self.current_project.name}")
    #
    #     handler = SVNHandlerAsync(
    #         self.current_project,
    #         log_callback=self.log,
    #         complete_callback=self.on_svn_complete
    #     )
    #     self.current_handler = handler
    #     handler.svn_async()

    def on_export_complete(self, success):
        """导出完成"""
        self.export_in_progress = False
        self.current_handler = None
        self.enable_buttons()
        if success:
            self.log(tr('log.export_done'), level='success')
        else:
            self.log(tr('log.export_failed'), level='error')

    def _append_export_log(self, message, project_name):
        """Append background export output from the GUI thread only."""
        self.log(f"[{project_name}] {message}")

    # SVN功能已禁用
    # def on_svn_complete(self, success):
    #     """SVN完成"""
    #     if success:
    #         self.log("✅ SVN操作完成")
    #     else:
    #         self.log("❌ SVN操作失败")

    # ==================== 文件拖放 ====================

    def dragEnterEvent(self, event):
        """拖入文件/文件夹时显示提示遮罩"""
        if self._extract_drop_dir(event.mimeData()):
            event.acceptProposedAction()
            self.drop_overlay.setGeometry(self.centralWidget().rect())
            self.drop_overlay.show()
            self.drop_overlay.raise_()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """拖出窗口时隐藏遮罩"""
        self.drop_overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """放下文件夹：设为当前项目的表格目录"""
        self.drop_overlay.hide()
        path = self._extract_drop_dir(event.mimeData())
        if not path:
            return
        event.acceptProposedAction()

        if not self.current_project:
            self.log(tr('log.select_project_first'))
            return

        if not self._ask_question(
            'dialog.set_table_dir_title', 'dialog.set_table_dir_detail',
            name=self.current_project.name, path=path,
        ):
            return

        data = self.current_project.to_dict()
        data['tablePath'] = path
        new_project = Project(data)
        success, msg = self.project_manager.update_project(new_project)
        if success:
            self.current_project = new_project
            self.load_projects(select_id=new_project.id)
            self.update_detail()
            self.log(tr('log.table_path_updated', path=path))
        else:
            QMessageBox.warning(self, tr('log.update_failed'), msg)

    @staticmethod
    def _extract_drop_dir(mime):
        """从拖放数据中提取目录：文件夹直接用，Excel 文件取其所在目录"""
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isdir(path):
                return os.path.normpath(path)
            if os.path.isfile(path) and path.lower().endswith(('.xlsx', '.xlsm', '.xls')):
                return os.path.normpath(os.path.dirname(path))
        return None

    # ==================== 主题 / 关于 ====================

    def change_theme(self):
        """切换主题"""
        dialog = ThemeDialog(self, self.current_theme_id, self.colors, self.bg_image)
        if dialog.exec_():
            theme_id, custom_colors, bg_image = dialog.get_result()

            self.current_theme_id = theme_id
            self.custom_colors = custom_colors
            self.bg_image = bg_image

            # 保存配置
            save_theme_config(theme_id, custom_colors, bg_image)

            # 重新加载主题
            self.load_theme()

            self._rebuild_ui_preserving_state()

            self.log(
                tr('log.theme_changed', name=localized_theme_name(theme_id)),
                level='success',
            )

    def _ask_question(self, title_key, message_key, **params):
        """Show a catalog-backed confirmation with translated button labels."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(tr(title_key))
        box.setText(tr(message_key, **params))
        yes_button = box.addButton(tr('dialog.yes'), QMessageBox.AcceptRole)
        no_button = box.addButton(tr('dialog.no'), QMessageBox.RejectRole)
        box.setDefaultButton(no_button)
        box.exec_()
        return box.clickedButton() is yes_button

    def change_language(self, locale_id):
        """Persist a locale and rebuild the main window while preserving selection/logs."""
        if locale_id == get_locale():
            return
        try:
            set_locale(locale_id)
        except OSError as exc:
            QMessageBox.warning(
                self, tr('dialog.language_save_failed_title'),
                tr('dialog.language_save_failed', detail=exc),
            )
            return
        self.load_theme()
        self._rebuild_ui_preserving_state()

    def _rebuild_ui_preserving_state(self):
        """Recreate translated/themed widgets without leaving hidden state behind."""
        selected_id = self.current_project.id if self.current_project else None
        search_text = self.search_input.text() if hasattr(self, 'search_input') else ''
        if selected_id:
            self.project_logs[selected_id] = self.current_log_messages.copy()
        self.current_project = None
        self.init_ui()
        self.load_projects()
        self.search_input.setText(search_text)
        self.on_search()
        if selected_id:
            self._select_project(selected_id)
        else:
            self.current_log_messages = []
            self.refresh_log_display()

    def show_about(self):
        """显示关于对话框"""
        dialog = AboutDialog(self, self.colors)
        dialog.exec_()

    # ==================== 日志 ====================

    def clear_log(self):
        """清空日志"""
        self.current_log_messages.clear()
        if self.current_project:
            project_id = self.current_project.id
            if project_id in self.project_logs:
                self.project_logs[project_id].clear()
        self.log_text.clear()

    def copy_log(self):
        """复制日志"""
        clipboard = QApplication.clipboard()
        clipboard.setText('\n'.join(self.current_log_messages))
        self.log(tr('log.log_copied'))

    def open_folder(self, attr_name):
        """打开文件夹"""
        if not self.current_project:
            return
        path = getattr(self.current_project, attr_name, None)
        if path and os.path.exists(path):
            try:
                if not open_local_path(os.path.normpath(path)):
                    raise OSError("the desktop environment rejected the open request")
                self.log(tr('log.folder_opened', path=path))
            except Exception as e:
                self.log(tr('log.folder_open_failed', detail=str(e)))
        else:
            self.log(tr('log.path_missing', path=path))

    def _log_level(self, message):
        """Prefer stable status markers; localized-word checks are legacy fallback."""
        marker = LOG_LEVEL_RE.search(message)
        if marker:
            return marker.group(1).lower()
        if '[ERROR]' in message or '❌' in message or '✗' in message or '失败' in message:
            return 'error'
        if '[WARNING]' in message or '⚠' in message or '警告' in message:
            return 'warning'
        if '[OK]' in message or '✅' in message or '✓' in message or '成功' in message or '完成' in message:
            return 'success'
        stripped = message.replace('[', '').replace(']', '')
        if stripped.strip() and set(stripped.split(']')[-1].strip()) <= {'='}:
            return 'dim'
        return 'info'

    def _append_colored_log(self, message):
        """日志按级别着色显示，前缀统一状态图标"""
        level = self._log_level(message)
        color = {
            'error': LOG_ERROR,
            'warning': LOG_WARNING,
            'success': self.colors['accent'],
            'dim': self.colors['text_dim'],
            'info': self.colors['text_light'],
        }[level]
        symbol = {
            'error': '✕', 'warning': '⚠', 'success': '✓', 'info': '→', 'dim': '',
        }[level]

        def esc(s):
            return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # 拆出时间戳和可选项目名；正文中已有的 emoji 标记由状态图标替代
        m = LOG_LINE_RE.match(message)
        if m:
            ts, proj, rest = m.groups()
            rest = EMOJI_PREFIX_RE.sub('', rest).strip()
        else:
            ts, proj, rest = None, None, message
        rest = LOG_LEVEL_RE.sub('', rest).strip()

        parts = []
        if ts:
            parts.append(f'<span style="color:{self.colors["text_dim"]};">[{ts}]</span>')
        if proj:
            parts.append(f'<span style="color:{self.colors["text_dim"]};">[{esc(proj)}]</span>')
        if symbol:
            parts.append(f'<span style="color:{color};"><b>{symbol}</b></span>')
        parts.append(f'<span style="color:{color};">{esc(rest)}</span>')
        self.log_text.append(' '.join(parts))

    def log(self, message, include_project_name=False, level=None):
        """输出日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        level_marker = f"[{str(level).upper()}] " if level else ""

        # 如果需要包含项目名称且当前有项目
        if include_project_name and self.current_project:
            formatted_message = (
                f"[{timestamp}] [{self.current_project.name}] {level_marker}{message}"
            )
        else:
            formatted_message = f"[{timestamp}] {level_marker}{message}"

        # 添加到当前日志消息列表
        self.current_log_messages.append(formatted_message)

        # 如果有当前项目，保存到项目日志中
        if self.current_project:
            project_id = self.current_project.id
            if project_id not in self.project_logs:
                self.project_logs[project_id] = []
            self.project_logs[project_id].append(formatted_message)

        # 显示在界面上
        self._append_colored_log(formatted_message)

        # 自动滚动到底部（保持最新日志可见）
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def switch_project_log(self):
        """切换项目日志显示"""
        if not self.current_project:
            return

        project_id = self.current_project.id

        # 切换到新项目的日志（不保存，已在 on_project_selected 中保存）
        if project_id in self.project_logs:
            self.current_log_messages = self.project_logs[project_id].copy()
        else:
            self.current_log_messages = []

        # 重新显示日志
        self.refresh_log_display()

    def refresh_log_display(self):
        """刷新日志显示"""
        self.log_text.clear()
        for message in self.current_log_messages:
            self._append_colored_log(message)

        # 滚动到底部显示最新日志
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = SheetToConfigWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
