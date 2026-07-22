# -*- coding: utf-8 -*-
"""
对话框模块
包含所有对话框：项目编辑、主题选择、传共享、导出选项、关于
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QTextEdit, QScrollArea, QFrame, QFileDialog, QMessageBox,
    QWidget, QButtonGroup, QRadioButton, QCheckBox, QTabWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5 import QtCore
from PyQt5.QtGui import QFont, QPixmap
from PyQt5 import QtCore
from theme_config import THEME_PRESETS, save_theme_config
import icons
from widgets import DragDropLineEdit
from i18n import tr
from styles import ERROR as DANGER_COLOR, _rgba


class ProjectEditDialog(QDialog):
    """项目编辑对话框"""
    
    def __init__(self, parent=None, project=None, colors=None):
        super().__init__(parent)
        self.project = project
        self.colors = colors or THEME_PRESETS['picunbg_teal'].copy()
        self.setWindowTitle(tr('dialog.project_title'))
        self.setMinimumSize(700, 620)
        self.result_data = None
        # 移除问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()
        if project:
            self.load_project()
    
    def init_ui(self):
        self.setStyleSheet(self._get_dialog_style())
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题（居中）
        title = QLabel(tr('dialog.project_title'))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {self.colors['accent']};")
        layout.addWidget(title)
        
        # 表单区域
        form_widget = QWidget()
        form_widget.setStyleSheet(f"background: {self.colors['bg_medium']}; border-radius: 8px;")
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 15, 15, 15)
        
        # 项目名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr('dialog.project_name_placeholder'))
        form_layout.addRow(self._required_label(tr('dialog.project_name')), self.name_edit)
        
        # 项目图标
        icon_layout = QHBoxLayout()
        self.icon_path_edit = DragDropLineEdit(accept_files=True)
        self.icon_path_edit.setPlaceholderText(tr('dialog.icon_placeholder'))
        icon_btn = QPushButton(tr('dialog.browse'))
        icon_btn.clicked.connect(self.select_icon)
        icon_clear_btn = QPushButton(tr('dialog.clear'))
        icon_clear_btn.clicked.connect(self.clear_icon)
        icon_layout.addWidget(self.icon_path_edit)
        icon_layout.addWidget(icon_btn)
        icon_layout.addWidget(icon_clear_btn)
        form_layout.addRow(tr('dialog.icon'), icon_layout)
        
        # 图标预览
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(64, 64)
        self._set_icon_preview_empty()
        self.icon_preview.setAlignment(Qt.AlignCenter)
        form_layout.addRow(tr('dialog.icon_preview'), self.icon_preview)
        
        # 表格目录
        table_layout = QHBoxLayout()
        self.table_path_edit = DragDropLineEdit()
        self.table_path_edit.setPlaceholderText(tr('dialog.folder_placeholder'))
        table_btn = QPushButton(tr('dialog.browse'))
        table_btn.clicked.connect(self.select_table_path)
        table_layout.addWidget(self.table_path_edit)
        table_layout.addWidget(table_btn)
        form_layout.addRow(self._required_label(tr('main.table_path')), table_layout)
        
        # 客户端路径
        client_layout = QHBoxLayout()
        self.client_path_edit = DragDropLineEdit()
        self.client_path_edit.setPlaceholderText(tr('dialog.folder_placeholder'))
        client_btn = QPushButton(tr('dialog.browse'))
        client_btn.clicked.connect(self.select_client_path)
        client_layout.addWidget(self.client_path_edit)
        client_layout.addWidget(client_btn)
        form_layout.addRow(self._required_label(tr('main.client_path')), client_layout)
        
        # 服务端路径
        server_layout = QHBoxLayout()
        self.server_path_edit = DragDropLineEdit()
        self.server_path_edit.setPlaceholderText(tr('dialog.folder_placeholder'))
        server_btn = QPushButton(tr('dialog.browse'))
        server_btn.clicked.connect(self.select_server_path)
        server_layout.addWidget(self.server_path_edit)
        server_layout.addWidget(server_btn)
        form_layout.addRow(self._required_label(tr('main.server_path')), server_layout)

        csharp_layout = QHBoxLayout()
        self.csharp_path_edit = DragDropLineEdit()
        self.csharp_path_edit.setPlaceholderText(tr('dialog.csharp_placeholder'))
        csharp_btn = QPushButton(tr('dialog.browse'))
        csharp_btn.clicked.connect(self.select_csharp_path)
        csharp_layout.addWidget(self.csharp_path_edit)
        csharp_layout.addWidget(csharp_btn)
        form_layout.addRow(tr('main.csharp_path'), csharp_layout)

        asset_layout = QHBoxLayout()
        self.asset_root_edit = DragDropLineEdit()
        self.asset_root_edit.setPlaceholderText(tr('dialog.asset_placeholder'))
        asset_btn = QPushButton(tr('dialog.browse'))
        asset_btn.clicked.connect(self.select_asset_root)
        asset_layout.addWidget(self.asset_root_edit)
        asset_layout.addWidget(asset_btn)
        form_layout.addRow(tr('main.asset_root'), asset_layout)
        
        # 同步目录（可选）
        shared_layout = QHBoxLayout()
        self.shared_path_edit = DragDropLineEdit()
        self.shared_path_edit.setPlaceholderText(tr('dialog.shared_placeholder'))
        shared_btn = QPushButton(tr('dialog.browse'))
        shared_btn.clicked.connect(self.select_shared_path)
        shared_layout.addWidget(self.shared_path_edit)
        shared_layout.addWidget(shared_btn)
        form_layout.addRow(tr('main.shared_path'), shared_layout)
        
        # 描述
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(tr('dialog.description_placeholder'))
        form_layout.addRow(tr('main.description'), self.desc_edit)
        
        layout.addWidget(form_widget)
        
        # 按钮（仅确定，居中；关闭窗口即取消）
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton(tr('dialog.confirm'))
        self.ok_btn.setObjectName("primary")
        self.ok_btn.setFixedWidth(160)
        self.ok_btn.clicked.connect(self.on_ok)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _get_dialog_style(self):
        return f"""
        QDialog {{ background-color: {self.colors['bg_dark']}; }}
        QLabel {{ color: {self.colors['text_light']}; font-size: 13px; }}
        QLineEdit {{
            background-color: {self.colors['bg_dark']};
            color: {self.colors['text_light']};
            border: 1px solid {self.colors['border']};
            border-radius: 6px;
            padding: 8px 12px;
            min-height: 18px;
        }}
        QLineEdit:focus {{ border: 2px solid {self.colors['accent']}; }}
        QLineEdit[dragHover="true"] {{
            border: 2px dashed {self.colors['accent']};
            background-color: {self.colors['bg_medium']};
        }}
        QPushButton {{
            background-color: {self.colors['bg_light']};
            color: {self.colors['text_light']};
            border: 1px solid {self.colors['border']};
            border-radius: 6px;
            padding: 8px 16px;
            min-height: 32px;
        }}
        QPushButton:hover {{ background-color: {self.colors['accent']}; color: {self.colors['bg_dark']}; }}
        QPushButton#primary {{
            background-color: {self.colors['accent']};
            color: {self.colors['bg_dark']};
            font-weight: bold;
        }}
        """
    
    def select_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('dialog.choose_icon'), "", tr('dialog.image_filter'))
        if path:
            self.icon_path_edit.setText(path)
            self.update_icon_preview(path)
    
    def clear_icon(self):
        self.icon_path_edit.clear()
        self.icon_preview.clear()
        self._set_icon_preview_empty()
        self.icon_preview.setText(tr('dialog.no_icon'))

    def _set_icon_preview_empty(self):
        """图标预览空态：虚线边框"""
        self.icon_preview.setStyleSheet(
            f"background: {self.colors['bg_dark']}; "
            f"border: 1px dashed {self.colors['border']}; border-radius: 4px; "
            f"color: {self.colors['text_dim']};"
        )

    def update_icon_preview(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.icon_preview.setStyleSheet(
                f"background: {self.colors['bg_dark']}; "
                f"border: 1px solid {self.colors['border']}; border-radius: 4px;"
            )
            scaled = pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_preview.setPixmap(scaled)
    
    def select_table_path(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_table_dir'))
        if path:
            self.table_path_edit.setText(path)
    
    def select_client_path(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_client_dir'))
        if path:
            self.client_path_edit.setText(path)
    
    def select_server_path(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_server_dir'))
        if path:
            self.server_path_edit.setText(path)

    def select_csharp_path(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_csharp_dir'))
        if path:
            self.csharp_path_edit.setText(path)

    def select_asset_root(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_asset_dir'))
        if path:
            self.asset_root_edit.setText(path)
    
    def select_shared_path(self):
        path = QFileDialog.getExistingDirectory(self, tr('dialog.choose_shared_dir'))
        if path:
            self.shared_path_edit.setText(path)
    
    def load_project(self):
        """加载项目数据"""
        if self.project:
            self.name_edit.setText(self.project.name)
            self.table_path_edit.setText(self.project.table_path)
            self.client_path_edit.setText(self.project.client_path)
            self.server_path_edit.setText(self.project.server_path)
            self.csharp_path_edit.setText(getattr(self.project, 'csharp_path', ''))
            self.asset_root_edit.setText(getattr(self.project, 'asset_root', ''))
            self.shared_path_edit.setText(self.project.shared_path)
            self.desc_edit.setText(self.project.description or "")
            # 加载图标
            if hasattr(self.project, 'icon_path') and self.project.icon_path:
                self.icon_path_edit.setText(self.project.icon_path)
                self.update_icon_preview(self.project.icon_path)
    
    def _required_label(self, text):
        """必填字段标签：字段名 + 主题色星号"""
        lbl = QLabel(f'{text}<span style="color:{self.colors["accent"]}; font-weight:bold;"> *</span>:')
        return lbl

    def on_ok(self):
        """确定按钮"""
        data = {
            'name': self.name_edit.text().strip(),
            'tablePath': self.table_path_edit.text().strip(),
            'clientPath': self.client_path_edit.text().strip(),
            'serverPath': self.server_path_edit.text().strip(),
            'csharpPath': self.csharp_path_edit.text().strip(),
            'assetRoot': self.asset_root_edit.text().strip(),
            'sharedPath': self.shared_path_edit.text().strip(),
            'description': self.desc_edit.text().strip(),
            'iconPath': self.icon_path_edit.text().strip()
        }
        
        # 验证必填项
        required = {
            'name': tr('dialog.project_name'),
            'tablePath': tr('main.table_path'),
            'clientPath': tr('main.client_path'),
            'serverPath': tr('main.server_path'),
        }
        for field, label in required.items():
            if not data[field]:
                QMessageBox.warning(self, tr('dialog.input_error'), tr('dialog.required_field', field=label))
                return
        
        if self.project:
            data['id'] = self.project.id
            data['createdAt'] = self.project.created_at
        
        self.result_data = data
        self.accept()
    
    def get_data(self):
        return self.result_data


class ThemeCard(QFrame):
    """预设主题卡片：主题渐变底 + 名称 + 配色圆点，点击选中"""

    def __init__(self, theme_id, on_select, parent=None):
        super().__init__(parent)
        self.theme_id = theme_id
        self._on_select = on_select
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self._on_select(self.theme_id)
        super().mouseReleaseEvent(event)


class ThemeDialog(QDialog):
    """主题选择对话框（重构版：免滚动紧凑卡片 + 统一确定/取消）"""

    def __init__(self, parent=None, current_theme='picunbg_teal', colors=None, bg_image=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.colors = colors or THEME_PRESETS['picunbg_teal'].copy()
        self.selected_theme = current_theme
        self.custom_colors = None
        self.result_bg_image = bg_image
        self.setWindowTitle(tr('dialog.theme_title'))
        self.setMinimumSize(700, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.theme_cards = {}
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(self._get_dialog_style())
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题（居中）
        title = QLabel(tr('dialog.theme_title'))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {self.colors['accent']};")
        layout.addWidget(title)

        # ===== 预设主题：分区容器 + 4 列卡片，免滚动 =====
        preset_section = QFrame()
        preset_section.setObjectName("themeSection")
        preset_layout = QVBoxLayout(preset_section)
        preset_layout.setContentsMargins(14, 12, 14, 14)
        preset_layout.setSpacing(10)

        preset_title = QLabel(tr('dialog.theme_presets'))
        preset_title.setObjectName("sectionTitle")
        preset_layout.addWidget(preset_title)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (theme_id, theme) in enumerate(THEME_PRESETS.items()):
            card = self._create_theme_card(theme_id, theme)
            grid.addWidget(card, i // 4, i % 4)
        preset_layout.addLayout(grid)
        layout.addWidget(preset_section)

        # ===== 自定义配色（分区容器，可折叠，默认收起） =====
        custom_section = QFrame()
        custom_section.setObjectName("themeSection")
        custom_v = QVBoxLayout(custom_section)
        custom_v.setContentsMargins(14, 12, 14, 14)
        custom_v.setSpacing(10)

        custom_header = QHBoxLayout()
        custom_title = QLabel(tr('dialog.custom_colors'))
        custom_title.setObjectName("sectionTitle")
        custom_header.addWidget(custom_title)
        custom_header.addStretch()

        self.custom_toggle = QPushButton(f"▸ {tr('dialog.expand')}")
        self.custom_toggle.setObjectName("linkBtn")
        self.custom_toggle.setCursor(Qt.PointingHandCursor)
        self.custom_toggle.clicked.connect(self.toggle_custom_section)
        custom_header.addWidget(self.custom_toggle)
        custom_v.addLayout(custom_header)

        self.custom_container = QWidget()
        custom_layout = QVBoxLayout(self.custom_container)
        custom_layout.setContentsMargins(0, 2, 0, 0)
        custom_layout.setSpacing(8)

        self.color_inputs = {}
        color_items = [
            ('bg_dark', tr('dialog.color_bg_dark'), self.colors['bg_dark']),
            ('bg_medium', tr('dialog.color_bg_medium'), self.colors['bg_medium']),
            ('bg_light', tr('dialog.color_bg_light'), self.colors['bg_light']),
            ('accent', tr('dialog.color_accent'), self.colors['accent']),
            ('text_light', tr('dialog.color_text_light'), self.colors['text_light']),
            ('text_dim', tr('dialog.color_text_dim'), self.colors['text_dim']),
        ]
        color_grid = QGridLayout()
        color_grid.setSpacing(8)
        for i, (key, label, default) in enumerate(color_items):
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {self.colors['text_light']}; font-size: 12px;")
            input_field = QLineEdit(default)
            input_field.setFixedWidth(80)
            input_field.textChanged.connect(lambda text, k=key: self._on_color_input(k, text))
            preview = QFrame()
            preview.setFixedSize(18, 18)
            preview.setStyleSheet(
                f"background: {default}; border-radius: 9px; "
                f"border: 1px solid {self.colors['border']};"
            )
            cell_layout.addWidget(lbl)
            cell_layout.addStretch()
            cell_layout.addWidget(input_field)
            cell_layout.addWidget(preview)
            color_grid.addWidget(cell, i // 3, i % 3)
            self.color_inputs[key] = (input_field, preview)
        custom_layout.addLayout(color_grid)

        apply_custom_btn = QPushButton(tr('dialog.apply_custom'))
        apply_custom_btn.setObjectName("primary")
        apply_custom_btn.clicked.connect(self.apply_custom_theme)
        custom_layout.addWidget(apply_custom_btn)

        self.custom_container.setVisible(False)
        custom_v.addWidget(self.custom_container)
        layout.addWidget(custom_section)

        # ===== 窗口背景图（分区容器） =====
        bg_section = QFrame()
        bg_section.setObjectName("themeSection")
        bg_v = QVBoxLayout(bg_section)
        bg_v.setContentsMargins(14, 12, 14, 14)
        bg_v.setSpacing(10)

        bg_title = QLabel(tr('dialog.bg_image'))
        bg_title.setObjectName("sectionTitle")
        bg_v.addWidget(bg_title)

        bg_row = QHBoxLayout()
        bg_row.setSpacing(14)
        self.bg_preview = QLabel()
        self.bg_preview.setFixedSize(240, 135)
        self.bg_preview.setAlignment(Qt.AlignCenter)
        self._refresh_bg_preview()
        bg_row.addWidget(self.bg_preview)

        bg_btn_col = QVBoxLayout()
        bg_btn_col.setSpacing(8)
        bg_btn_col.addStretch()
        select_bg_btn = QPushButton(tr('dialog.choose_image'))
        select_bg_btn.setFixedWidth(110)
        select_bg_btn.clicked.connect(self.select_bg_image)
        clear_bg_btn = QPushButton(tr('dialog.clear_bg'))
        clear_bg_btn.setObjectName("danger")
        clear_bg_btn.setFixedWidth(110)
        clear_bg_btn.clicked.connect(self.clear_bg_image)
        bg_btn_col.addWidget(select_bg_btn)
        bg_btn_col.addWidget(clear_bg_btn)
        bg_btn_col.addStretch()
        bg_row.addLayout(bg_btn_col)
        bg_row.addStretch()
        bg_v.addLayout(bg_row)

        bg_hint = QLabel(tr('dialog.bg_hint'))
        bg_hint.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 11px;")
        bg_v.addWidget(bg_hint)
        layout.addWidget(bg_section)

        layout.addStretch()

        # ===== 确定（居中，无取消按钮；关闭窗口即放弃） =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(tr('dialog.confirm'))
        ok_btn.setObjectName("primary")
        ok_btn.setDefault(True)
        ok_btn.setFixedSize(200, 36)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _get_dialog_style(self):
        c = self.colors
        danger_soft = _rgba(DANGER_COLOR, 0.15)
        danger_badge = _rgba(DANGER_COLOR, 0.50)
        return f"""
        QDialog {{ background-color: {c['bg_dark']}; }}
        QLabel {{ color: {c['text_light']}; font-size: 13px; }}
        QLabel#sectionTitle {{
            color: {c['text_light']};
            font-size: 13px;
            font-weight: bold;
        }}
        QFrame#themeSection {{
            background-color: {c['bg_medium']};
            border: 1px solid {c['border']};
            border-radius: 10px;
        }}
        QLineEdit {{
            background-color: {c['bg_dark']};
            color: {c['text_light']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QLineEdit:focus {{ border: 1px solid {c['accent']}; }}
        QPushButton {{
            background-color: {c['bg_light']};
            color: {c['text_light']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{ border-color: {c['accent']}; }}
        QPushButton#primary {{
            background-color: {c['accent']};
            color: {c['bg_dark']};
            font-weight: bold;
        }}
        QPushButton#primary:hover {{
            background-color: {c['accent_hover']};
            border-color: {c['accent_hover']};
        }}
        QPushButton#danger {{
            background-color: transparent;
            color: {DANGER_COLOR};
            border-color: {danger_badge};
        }}
        QPushButton#danger:hover {{
            background-color: {danger_soft};
            border-color: {DANGER_COLOR};
        }}
        QPushButton#linkBtn {{
            background-color: transparent;
            border: none;
            color: {c['accent']};
            padding: 4px 8px;
        }}
        """

    def _create_theme_card(self, theme_id, theme):
        """主题卡片：主题渐变底 + 名称 + 三颗配色圆点，单击选中"""
        from theme_config import localized_theme_name
        card = ThemeCard(theme_id, self.select_theme)
        card.setObjectName("themeCard")
        card.setFixedSize(148, 64)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(localized_theme_name(theme_id))
        name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        top_row.addWidget(name_lbl)
        top_row.addStretch()
        check_lbl = QLabel('✓')
        check_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        top_row.addWidget(check_lbl)
        card_layout.addLayout(top_row)

        dots_row = QHBoxLayout()
        dots_row.setContentsMargins(0, 0, 0, 0)
        dots_row.setSpacing(6)
        dots = []
        for _ in range(3):
            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setAttribute(Qt.WA_TransparentForMouseEvents)
            dots_row.addWidget(dot)
            dots.append(dot)
        dots_row.addStretch()
        card_layout.addLayout(dots_row)

        card.name_label = name_lbl
        card.check_label = check_lbl
        card.dots = dots

        self._style_theme_card(card, theme_id, theme)
        self.theme_cards[theme_id] = (card, theme)
        return card

    def _style_theme_card(self, card, theme_id, theme):
        selected = theme_id == self.selected_theme
        accent = self.colors['accent']
        border_color = accent if selected else self.colors['border']
        border_width = 2 if selected else 1
        card.setStyleSheet(f"""
            QFrame#themeCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme['bg_medium']},
                    stop:1 {theme['bg_light']});
                border: {border_width}px solid {border_color};
                border-radius: 8px;
            }}
            QFrame#themeCard:hover {{ border: {border_width}px solid {accent}; }}
        """)
        card.name_label.setStyleSheet(
            f"color: {theme['text_light']}; font-size: 13px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        card.check_label.setStyleSheet(
            f"color: {accent}; font-size: 13px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        card.check_label.setVisible(selected)
        for dot, key in zip(card.dots, ('accent', 'bg_light', 'text_dim')):
            dot.setStyleSheet(
                f"background: {theme[key]}; border-radius: 5px; "
                f"border: 1px solid {theme['border']};"
            )

    def _refresh_theme_cards(self):
        for theme_id, (card, theme) in self.theme_cards.items():
            self._style_theme_card(card, theme_id, theme)

    def toggle_custom_section(self):
        """展开/收起自定义配色区"""
        visible = self.custom_container.isVisible()
        self.custom_container.setVisible(not visible)
        arrow = '▾' if not visible else '▸'
        text = tr('dialog.collapse') if not visible else tr('dialog.expand')
        self.custom_toggle.setText(f'{arrow} {text}')

    def select_theme(self, theme_id):
        """选中预设主题（不立即关闭，点确定生效）"""
        self.selected_theme = theme_id
        self.custom_colors = None
        self._refresh_theme_cards()

    def _on_color_input(self, key, text):
        """颜色输入时实时更新预览"""
        if self._is_valid_color(text.strip()):
            _, preview = self.color_inputs[key]
            preview.setStyleSheet(
                f"background: {text.strip()}; border-radius: 4px; "
                f"border: 1px solid {self.colors['border']};"
            )

    def apply_custom_theme(self):
        """应用自定义配色"""
        custom_theme = {'name': tr('theme.custom')}

        for key, (input_field, preview) in self.color_inputs.items():
            color = input_field.text().strip()
            if self._is_valid_color(color):
                custom_theme[key] = color
            else:
                QMessageBox.warning(self, tr('dialog.invalid_color'), tr('dialog.invalid_color_detail', key=key))
                return

        # 计算辅助色
        custom_theme['accent_hover'] = custom_theme['accent']
        custom_theme['border'] = custom_theme['bg_light']

        self.selected_theme = 'custom'
        self.custom_colors = custom_theme
        self._refresh_theme_cards()

    def _is_valid_color(self, color):
        """验证颜色格式"""
        import re
        return bool(re.match(r'^#[0-9A-Fa-f]{6}$', color))

    def select_bg_image(self):
        """选择背景图片"""
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dialog.choose_bg'), "", tr('dialog.image_filter')
        )
        if path:
            self.result_bg_image = path
            self._refresh_bg_preview()

    def clear_bg_image(self):
        """清除背景图片"""
        self.result_bg_image = None
        self._refresh_bg_preview()

    def _refresh_bg_preview(self):
        """刷新背景图预览（有图实线框，无图虚线空态）"""
        if self.result_bg_image:
            from theme_config import get_scaled_bg_image
            pixmap = QPixmap(get_scaled_bg_image(self.result_bg_image))
            if not pixmap.isNull():
                self.bg_preview.setStyleSheet(
                    f"background: {self.colors['bg_dark']}; "
                    f"border: 1px solid {self.colors['border']}; border-radius: 6px; "
                    f"color: {self.colors['text_dim']};"
                )
                scaled = pixmap.scaled(
                    236, 131, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.bg_preview.setPixmap(scaled)
                return
        self.bg_preview.clear()
        self.bg_preview.setStyleSheet(
            f"background: {self.colors['bg_dark']}; "
            f"border: 1px dashed {self.colors['border']}; border-radius: 6px; "
            f"color: {self.colors['text_dim']};"
        )
        self.bg_preview.setText(tr('dialog.no_bg'))

    def get_result(self):
        return self.selected_theme, self.custom_colors, self.result_bg_image


class ImportOptionDialog(QDialog):
    """传共享选项对话框（重构版：扁平选项按钮）"""

    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self.colors = colors or THEME_PRESETS['picunbg_teal'].copy()
        self.selected_option = None
        self.setWindowTitle(tr('dialog.import_title'))
        self.setMinimumSize(480, 340)
        # 移除问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(self._get_dialog_style())
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addSpacing(4)

        # 选项（扁平按钮，无内框）
        options = [
            ("1", tr('dialog.import_saved'), tr('dialog.import_saved_hint')),
            ("2", tr('dialog.import_source'), tr('dialog.import_source_hint')),
            ("3", tr('dialog.import_target'), tr('dialog.import_target_hint')),
        ]

        for value, text, desc in options:
            btn = self._create_option_button(value, text, desc)
            layout.addWidget(btn)

        layout.addStretch()
        self.setLayout(layout)

    def _get_dialog_style(self):
        return f"""
        QDialog {{ background-color: {self.colors['bg_dark']}; }}
        QLabel {{ color: {self.colors['text_light']}; }}
        QPushButton {{
            background-color: {self.colors['bg_light']};
            color: {self.colors['text_light']};
            border: 1px solid {self.colors['border']};
            border-radius: 6px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{ border-color: {self.colors['accent']}; }}
        """

    def _create_option_button(self, value, text, desc):
        """扁平选项按钮：左对齐标题 + 淡色描述"""
        btn = QPushButton(f"{text}\n{desc}")
        btn.setFixedHeight(56)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_medium']};
                color: {self.colors['text_light']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
                text-align: left;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {self.colors['accent']};
            }}
        """)
        btn.setToolTip(desc)
        btn.clicked.connect(lambda: self.select_option(value))
        return btn

    def select_option(self, value):
        """选择选项"""
        self.selected_option = value
        self.accept()

    def get_result(self):
        return self.selected_option


class ExportOptionDialog(QDialog):
    """导出选项对话框（去重标题、扁平选项、仅校验作为选项）"""

    def __init__(self, parent=None, last_filename="", colors=None):
        super().__init__(parent)
        self.colors = colors or THEME_PRESETS['picunbg_teal'].copy()
        self.last_filename = last_filename
        self.selected_option = None
        self.filename = ""
        self.validation_only = False
        self.breaking_proto_checkbox = QCheckBox(tr('dialog.allow_breaking_proto'))
        self.breaking_proto_checkbox.setChecked(False)
        self.breaking_proto_checkbox.setToolTip(tr('dialog.allow_breaking_proto_hint'))
        self.validation_only_checkbox = QCheckBox()
        self.validation_only_checkbox.setVisible(False)
        self.allow_breaking_proto_change = False
        self.setWindowTitle(tr('dialog.export_title'))
        self.setMinimumSize(480, 520)
        # 移除问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(self._get_dialog_style())
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addSpacing(4)

        # 选项（扁平按钮：标题 + 淡色描述，无内框）
        options = [
            ("1", tr('dialog.export_all'), tr('dialog.export_all_hint')),
            ("2", tr('dialog.export_client'), tr('dialog.export_client_hint')),
            ("3", tr('dialog.export_server'), tr('dialog.export_server_hint')),
            ("validate", tr('dialog.export_validate'), tr('dialog.export_validate_hint')),
        ]
        for value, text, desc in options:
            btn = self._create_option_button(value, text, desc)
            layout.addWidget(btn)

        # 分隔线
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(4)

        # 指定文件导出（扁平区，标题居中）
        specific_title = QLabel(tr('dialog.export_specific'))
        specific_title.setAlignment(Qt.AlignCenter)
        specific_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {self.colors['text_light']};"
        )
        layout.addWidget(specific_title)

        hint = QLabel(tr('dialog.export_filename_hint'))
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"font-size: 11px; color: {self.colors['text_dim']};")
        layout.addWidget(hint)

        input_layout = QHBoxLayout()
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText(tr('dialog.export_filename_placeholder'))
        if self.last_filename:
            self.filename_input.setText(self.last_filename)
        suffix = QLabel(".xlsx")
        suffix.setStyleSheet(f"color: {self.colors['text_dim']};")
        input_layout.addWidget(self.filename_input)
        input_layout.addWidget(suffix)
        layout.addLayout(input_layout)

        export_btn = QPushButton(tr('dialog.export_specific_button'))
        export_btn.setObjectName("primary")
        export_btn.clicked.connect(self.export_specific)
        layout.addWidget(export_btn)

        layout.addSpacing(4)
        layout.addWidget(self.breaking_proto_checkbox)

        layout.addStretch()
        self.setLayout(layout)

    def _get_dialog_style(self):
        return f"""
        QDialog {{ background-color: {self.colors['bg_dark']}; }}
        QLabel {{ color: {self.colors['text_light']}; }}
        QLineEdit {{
            background-color: {self.colors['bg_medium']};
            color: {self.colors['text_light']};
            border: 1px solid {self.colors['border']};
            border-radius: 6px;
            padding: 8px 12px;
        }}
        QLineEdit:focus {{
            border: 1px solid {self.colors['accent']};
        }}
        QCheckBox {{
            color: {self.colors['text_light']};
            spacing: 8px;
            padding: 4px 0;
        }}
        QPushButton#primary {{
            background-color: {self.colors['accent']};
            color: {self.colors['bg_dark']};
            border-radius: 6px;
            padding: 8px;
            font-weight: bold;
        }}
        QFrame#divider {{
            background-color: {self.colors['border']};
            border: none;
        }}
        """

    def _create_option_button(self, value, text, desc):
        """扁平选项按钮：左对齐标题 + 淡色描述，无内部嵌套部件"""
        btn = QPushButton(f"{text}\n{desc}")
        btn.setFixedHeight(56)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_medium']};
                color: {self.colors['text_light']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
                text-align: left;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {self.colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_light']};
            }}
        """)
        btn.setToolTip(desc)
        btn.clicked.connect(lambda: self.select_option(value))
        return btn

    def select_option(self, value):
        """选择选项"""
        self.validation_only = self.validation_only_checkbox.isChecked()
        if value == "validate":
            # 仅校验：按"全部"范围读取校验，不生成文件
            self.validation_only = True
            self.selected_option = "1"
        else:
            self.selected_option = value
        self.accept()

    def export_specific(self):
        """导出指定文件"""
        filename = self.filename_input.text().strip()
        if not filename:
            QMessageBox.warning(self, tr('dialog.input_error'), tr('dialog.filename_required'))
            return
        self.filename = filename
        self.selected_option = "4"
        self.accept()

    def get_result(self):
        self.allow_breaking_proto_change = self.breaking_proto_checkbox.isChecked()
        return (
            self.selected_option, self.filename,
            self.allow_breaking_proto_change, self.validation_only,
        )


class AboutDialog(QDialog):
    """关于对话框（页签版：关于 / 使用说明）"""

    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self.colors = colors or THEME_PRESETS['picunbg_teal'].copy()
        self.setWindowTitle(tr('about.title'))
        self.setMinimumSize(680, 620)
        # 移除问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(self._get_dialog_style())
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 页签
        tabs = QTabWidget()
        tabs.addTab(self._build_about_tab(), tr('about.title'))
        tabs.addTab(self._build_guide_tab(), tr('about.guide'))
        tabs.addTab(self._build_donate_tab(), tr('about.donate'))
        layout.addWidget(tabs)

        # 关闭按钮
        close_btn = QPushButton(tr('about.close'))
        close_btn.setObjectName("primary")
        close_btn.setFixedWidth(160)
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    # ==================== 关于页 ====================

    def _build_about_tab(self):
        import icons as _icons
        from version import __version__, APP_TITLE, GITHUB_URL, GITHUB_RELEASES_URL

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 16, 10, 10)

        # 头部：图标 + 名称 + 版本
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(_icons.get_pixmap('app', self.colors['accent'], 40))
        logo.setFixedSize(48, 48)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name = QLabel(APP_TITLE)
        name.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {self.colors['accent']};")
        version = QLabel(f"v{__version__}")
        version.setStyleSheet(f"font-size: 12px; color: {self.colors['text_dim']};")
        name_col.addWidget(name)
        name_col.addWidget(version)

        header.addWidget(logo)
        header.addLayout(name_col)
        header.addStretch()
        layout.addLayout(header)

        # 简介
        intro = QLabel(tr('about.intro'))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {self.colors['text_light']};")
        layout.addWidget(intro)

        layout.addWidget(self._make_divider())

        # GitHub 仓库
        gh_row = QHBoxLayout()
        gh_label = QLabel(tr('about.github'))
        gh_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        gh_link = QLabel(f'<a href="{GITHUB_URL}" style="color: {self.colors["accent"]};">{GITHUB_URL}</a>')
        gh_link.setOpenExternalLinks(True)
        gh_row.addWidget(gh_label)
        gh_row.addWidget(gh_link, 1)
        layout.addLayout(gh_row)

        # 检查更新按钮
        update_btn = QPushButton(f"  {tr('about.check_updates')}")
        update_btn.setIcon(_icons.get_icon('export', self.colors['text_light'], 14))
        update_btn.setToolTip(tr('about.update_tooltip'))
        update_btn.clicked.connect(lambda: self._open_url(GITHUB_RELEASES_URL))
        layout.addWidget(update_btn, 0, Qt.AlignLeft)

        # 更新方式说明
        update_hint = QLabel(tr('about.update_hint'))
        update_hint.setWordWrap(True)
        update_hint.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 11px;")
        layout.addWidget(update_hint)

        layout.addWidget(self._make_divider())

        # 开源协议
        license_label = QLabel(tr('about.license'))
        license_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        layout.addWidget(license_label)

        layout.addStretch()
        return page

    @staticmethod
    def _open_url(url):
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _build_donate_tab(self):
        """支持作者页：微信 / 支付宝收款码"""
        import os
        from version import resource_path

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 24, 10, 10)

        title = QLabel(tr('donate.title'))
        title.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {self.colors['accent']};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(tr('donate.hint'))
        hint.setStyleSheet(f"color: {self.colors['text_light']}; font-size: 12px;")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(8)

        qr_row = QHBoxLayout()
        qr_row.setSpacing(24)
        qr_row.addStretch()
        for name, file_name, caption_key in (
            (tr('donate.alipay'), "alipay.png", 'donate.alipay'),
            (tr('donate.wechat'), "wechat.png", 'donate.wechat'),
        ):
            col = QVBoxLayout()
            col.setSpacing(8)
            qr = QLabel()
            qr.setFixedSize(200, 200)
            qr.setAlignment(Qt.AlignCenter)
            path = resource_path(f"assets/donate/{file_name}")
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    qr.setPixmap(pix.scaled(196, 196, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if qr.pixmap() is None or qr.pixmap().isNull():
                qr.setText(tr('donate.missing'))
                qr.setStyleSheet(
                    f"background: {self.colors['bg_medium']}; "
                    f"border: 1px dashed {self.colors['border']}; border-radius: 8px; "
                    f"color: {self.colors['text_dim']};"
                )
            cap = QLabel(tr(caption_key))
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet(f"color: {self.colors['text_light']}; font-size: 13px;")
            col.addWidget(qr)
            col.addWidget(cap)
            qr_row.addLayout(col)
        qr_row.addStretch()
        layout.addLayout(qr_row)

        footer_text = tr('donate.footer')
        if footer_text != 'donate.footer':
            # 该 key 暂无其他语言翻译时跳过，避免显示原始 key
            footer = QLabel(footer_text)
            footer.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
            footer.setAlignment(Qt.AlignCenter)
            layout.addSpacing(10)
            layout.addWidget(footer)

        layout.addStretch()
        return page

    # ==================== 使用说明页 ====================

    def _build_guide_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        body = QVBoxLayout(container)
        body.setContentsMargins(18, 18, 18, 18)
        body.setSpacing(6)

        if tr('guide.s1_title') != 'guide.s1_title':
            # 结构化分节（中文小标题 + 强调条）；无分节文案的语言回退到整段文本
            i = 1
            while True:
                title_key = f'guide.s{i}_title'
                title_text = tr(title_key)
                if title_text == title_key:
                    break
                title_lbl = QLabel(title_text)
                title_lbl.setStyleSheet(
                    f"color: {self.colors['text_light']}; font-size: 14px; font-weight: bold; "
                    f"border-left: 3px solid {self.colors['accent']}; padding-left: 8px;"
                )
                body_lbl = QLabel(tr(f'guide.s{i}_body'))
                body_lbl.setWordWrap(True)
                body_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                body_lbl.setStyleSheet(
                    f"color: {self.colors['text_light']}; font-size: 12px; padding-left: 11px;"
                )
                body.addWidget(title_lbl)
                body.addWidget(body_lbl)
                body.addSpacing(14)
                i += 1
        else:
            content = QLabel(tr('guide.full_text'))
            content.setWordWrap(True)
            content.setTextInteractionFlags(Qt.TextSelectableByMouse)
            content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            content.setStyleSheet(
                f"color: {self.colors['text_light']}; font-size: 12px; "
                "padding: 2px; line-height: 1.4;"
            )
            body.addWidget(content)

        body.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        return page

    # ==================== 小部件 ====================

    def _make_divider(self):
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {self.colors['border']};")
        return divider

    def _add_section_title(self, parent, text):
        title = QLabel(text)
        title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {self.colors['accent']};
            padding: 6px 0 4px 0;
            border-bottom: 1px solid {self.colors['border']};
        """)
        parent.addWidget(title)

    def _add_text(self, parent, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {self.colors['text_light']}; font-size: 12px; background: transparent;")
        parent.addWidget(lbl)

    def _add_code_text(self, parent, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {self.colors['text_dim']};
            font-family: Consolas, Monaco, monospace;
            font-size: 11px;
            background: transparent;
            padding-left: 8px;
        """)
        parent.addWidget(lbl)

    def _get_dialog_style(self):
        return f"""
        QDialog {{ background-color: {self.colors['bg_dark']}; }}
        QLabel {{ color: {self.colors['text_light']}; font-size: 13px; background: transparent; }}
        QPushButton {{
            background-color: {self.colors['bg_light']};
            color: {self.colors['text_light']};
            border: 1px solid {self.colors['border']};
            border-radius: 6px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{ border-color: {self.colors['accent']}; }}
        QPushButton#primary {{
            background-color: {self.colors['accent']};
            color: {self.colors['bg_dark']};
            border: none;
            border-radius: 6px;
            padding: 10px 40px;
            font-weight: bold;
            font-size: 14px;
        }}
        QScrollArea {{ border: none; background: transparent; }}
        QTabWidget::pane {{
            border: 1px solid {self.colors['border']};
            border-radius: 8px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {self.colors['text_dim']};
            padding: 8px 20px;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:selected {{
            color: {self.colors['accent']};
            border-bottom: 2px solid {self.colors['accent']};
        }}
        QTabBar::tab:hover {{ color: {self.colors['text_light']}; }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
        }}
        QScrollBar::handle:vertical {{
            background: {self.colors['border']};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {self.colors['accent']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """
