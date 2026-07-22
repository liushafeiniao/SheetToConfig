# -*- coding: utf-8 -*-
"""
SheetToConfig 样式模块
全应用唯一的 QSS 样式来源，所有样式由主题色驱动。
主窗口与对话框统一调用 get_stylesheet(colors)。
"""

# 默认配色（青绿主题），与 theme_config.THEME_PRESETS['picunbg_teal'] 一致
COLORS = {
    'bg_dark': '#0a0f0d',        # 主背景
    'bg_medium': '#111815',      # 卡片背景
    'bg_light': '#1a211e',       # 按钮/次级背景
    'accent': '#00d4aa',         # 主强调色
    'accent_hover': '#66e5c5',   # 悬停态
    'text_light': '#e8f5f0',     # 主文字
    'text_dim': '#8a9a93',       # 次级文字
    'border': '#1f2a26',         # 边框/分隔线
}

ERROR = '#ff4757'
WARNING = '#f0a500'


def _rgba(hex_color, alpha):
    """#rrggbb -> rgba(r, g, b, a)"""
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {alpha})'


def get_stylesheet(colors=None, bg_image=None):
    """按主题色生成完整 QSS；colors 缺省时使用默认青绿主题。
    bg_image 为窗口底图路径；设置后面板自动变为半透明以透出底图。"""
    c = dict(COLORS)
    if colors:
        c.update({k: v for k, v in colors.items() if k in c or k == 'name'})

    accent_soft = _rgba(c['accent'], 0.15)
    accent_hover_bg = _rgba(c['accent'], 0.18)
    accent_badge = _rgba(c['accent'], 0.40)
    error_soft = _rgba(ERROR, 0.15)
    error_badge = _rgba(ERROR, 0.50)
    overlay_bg = _rgba(c['accent'], 0.08)

    # 有底图时：主窗口铺图，面板/控件背景半透明
    if bg_image:
        img_url = bg_image.replace('\\', '/')
        window_bg = f"border-image: url('{img_url}') 0 0 0 0 stretch stretch;"
        panel_bg = _rgba(c['bg_medium'], 0.86)
        card_bg = _rgba(c['bg_medium'], 0.86)
        sunken_bg = _rgba(c['bg_dark'], 0.78)   # 输入框/日志等"凹陷"区域
        btn_bg = _rgba(c['bg_light'], 0.88)
        menu_bg = _rgba(c['bg_medium'], 0.96)
    else:
        window_bg = f"background-color: {c['bg_dark']};"
        panel_bg = c['bg_medium']
        card_bg = c['bg_medium']
        sunken_bg = c['bg_dark']
        btn_bg = c['bg_light']
        menu_bg = c['bg_medium']

    return f"""
    /* ==================== 基础 ==================== */
    QMainWindow {{
        {window_bg}
    }}

    QDialog, QMessageBox {{
        background-color: {c['bg_dark']};
    }}

    QWidget {{
        color: {c['text_light']};
        font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        font-size: 13px;
    }}

    QLabel {{
        background-color: transparent;
    }}

    /* ==================== 面板与卡片 ==================== */
    QFrame#leftPanel {{
        background-color: {panel_bg};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}

    QFrame#card {{
        background-color: transparent;
        border: none;
    }}

    QFrame#innerPanel {{
        background-color: transparent;
    }}

    QWidget#detailRow {{
        border-bottom: 1px solid {c['border']};
    }}

    /* ==================== 标签 ==================== */
    QLabel#cardTitle {{
        color: {c['text_light']};
        font-size: 14px;
        font-weight: 600;
        border-left: 3px solid {c['accent']};
        padding-left: 8px;
    }}

    QLabel#listSection {{
        color: {c['text_dim']};
        font-size: 11px;
    }}

    QLabel#appTitle {{
        font-size: 17px;
        font-weight: bold;
    }}

    QLabel#versionBadge {{
        color: {c['accent']};
        font-size: 11px;
        padding: 1px 8px;
        border: 1px solid {accent_badge};
        border-radius: 9px;
    }}

    QLabel#fieldLabel {{
        color: {c['text_dim']};
    }}

    QLabel#fieldValue {{
        color: {c['text_light']};
    }}

    QLabel#projectName {{
        color: {c['text_light']};
        font-size: 22px;
        font-weight: bold;
    }}

    QLabel#activeBadge {{
        color: {c['accent']};
        font-size: 11px;
        padding: 2px 10px;
        border: 1px solid {accent_badge};
        border-radius: 10px;
        background-color: {accent_soft};
    }}

    QLabel#itemName {{
        color: {c['text_light']};
        font-size: 13px;
        font-weight: 600;
    }}

    QLabel#itemDesc {{
        color: {c['text_dim']};
        font-size: 11px;
    }}

    QLabel#itemIconBox {{
        background-color: {accent_soft};
        border-radius: 8px;
    }}

    QLabel#detailIconBox {{
        background-color: {panel_bg};
        border-radius: 8px;
    }}

    QLabel#dropOverlay {{
        background-color: {overlay_bg};
        border: 2px dashed {c['accent']};
        border-radius: 12px;
        color: {c['accent']};
        font-size: 18px;
        font-weight: 600;
    }}

    /* ==================== 项目列表 ==================== */
    QListWidget#projectList {{
        background-color: transparent;
        border: none;
        outline: none;
    }}

    QListWidget#projectList::item {{
        background-color: transparent;
        border-radius: 8px;
        padding: 10px 12px;
        margin: 4px 6px 4px 0;
        color: {c['text_light']};
    }}

    QListWidget#projectList::item:hover {{
        background-color: rgba(255, 255, 255, 0.05);
    }}

    QListWidget#projectList::item:selected {{
        background-color: {accent_soft};
    }}

    QListWidget#projectList::item:selected:!active {{
        background-color: {accent_soft};
    }}

    /* ==================== 按钮 ==================== */
    QPushButton {{
        background-color: {btn_bg};
        color: {c['text_light']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px 16px;
        outline: none;
    }}

    QPushButton:hover {{
        background-color: {accent_hover_bg};
        border-color: {c['accent']};
    }}

    QPushButton:pressed {{
        background-color: {accent_soft};
    }}

    QPushButton:disabled {{
        background-color: {c['bg_medium']};
        color: {c['text_dim']};
        border-color: {c['border']};
    }}

    QPushButton#primary {{
        background-color: {c['accent']};
        color: {c['bg_dark']};
        border-color: {c['accent']};
        font-weight: 600;
    }}

    QPushButton#primary:hover {{
        background-color: {c['accent_hover']};
        border-color: {c['accent_hover']};
    }}

    QPushButton#primary:pressed {{
        background-color: {c['accent']};
    }}

    QPushButton#primary:disabled {{
        background-color: {c['bg_medium']};
        color: {c['text_dim']};
        border-color: {c['border']};
    }}

    QPushButton#danger {{
        background-color: transparent;
        color: {ERROR};
        border-color: {error_badge};
    }}

    QPushButton#danger:hover {{
        background-color: {error_soft};
        border-color: {ERROR};
    }}

    QPushButton#danger:disabled {{
        color: {c['text_dim']};
        border-color: {c['border']};
        background-color: {c['bg_medium']};
    }}

    QPushButton#iconBtn {{
        background-color: transparent;
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px;
    }}

    QPushButton#iconBtn:hover {{
        background-color: {accent_hover_bg};
        border-color: {c['accent']};
    }}

    QPushButton#linkBtn {{
        background-color: transparent;
        border: none;
        color: {c['accent']};
        padding: 4px 8px;
    }}

    QPushButton#linkBtn:hover {{
        color: {c['accent_hover']};
        background-color: transparent;
    }}

    QPushButton#moreBtn {{
        background-color: transparent;
        border: none;
        border-radius: 4px;
        color: {c['text_dim']};
        font-size: 15px;
        font-weight: bold;
        padding: 0px;
    }}

    QPushButton#moreBtn:hover {{
        background-color: rgba(255, 255, 255, 0.08);
        color: {c['text_light']};
    }}

    /* 语言切换按钮（QToolButton） */
    QToolButton {{
        background-color: {btn_bg};
        color: {c['text_light']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 12px;
    }}

    QToolButton:hover {{
        background-color: {accent_hover_bg};
        border-color: {c['accent']};
    }}

    QToolButton::menu-indicator {{
        image: none;
        width: 0px;
    }}

    /* ==================== 页签 ==================== */
    QTabWidget::pane {{
        border: none;
        border-top: 1px solid {c['border']};
    }}

    QTabBar::tab {{
        background: transparent;
        color: {c['text_dim']};
        padding: 8px 16px;
        border: none;
        border-bottom: 2px solid transparent;
    }}

    QTabBar::tab:selected {{
        color: {c['text_light']};
        border-bottom: 2px solid {c['accent']};
        font-weight: 600;
    }}

    QTabBar::tab:hover {{
        color: {c['text_light']};
    }}

    /* ==================== 输入框 ==================== */
    QLineEdit {{
        background-color: {sunken_bg};
        color: {c['text_light']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 8px 12px;
        selection-background-color: {c['accent']};
        selection-color: {c['bg_dark']};
    }}

    QLineEdit:focus {{
        border: 1px solid {c['accent']};
    }}

    QLineEdit:disabled {{
        background-color: {c['bg_medium']};
        color: {c['text_dim']};
    }}

    QLineEdit[dragHover="true"] {{
        border: 2px dashed {c['accent']};
        background-color: {overlay_bg};
    }}

    /* ==================== 日志 ==================== */
    QTextEdit#logText {{
        background-color: {sunken_bg};
        color: {c['text_light']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px;
        font-family: "Consolas", "Monaco", monospace;
        font-size: 12px;
        selection-background-color: {c['accent']};
        selection-color: {c['bg_dark']};
    }}

    /* ==================== 右键菜单 ==================== */
    QMenu {{
        background-color: {menu_bg};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px;
    }}

    QMenu::item {{
        padding: 8px 28px 8px 12px;
        border-radius: 4px;
        color: {c['text_light']};
    }}

    QMenu::item:selected {{
        background-color: {accent_soft};
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {c['border']};
        margin: 6px 10px;
    }}

    /* ==================== 工具提示 / 状态栏 ==================== */
    QToolTip {{
        background-color: {menu_bg};
        color: {c['text_light']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 6px 8px;
    }}

    QStatusBar {{
        background-color: transparent;
        color: {c['text_dim']};
        font-size: 12px;
        border-top: 1px solid {c['border']};
    }}

    /* ==================== 消息框 ==================== */
    QMessageBox QLabel {{
        color: {c['text_light']};
    }}

    QMessageBox QPushButton {{
        min-width: 80px;
    }}

    /* ==================== 滚动条 ==================== */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 10px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c['border']};
        border-radius: 5px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c['accent']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 10px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c['border']};
        border-radius: 5px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {c['accent']};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """


def get_accent_color():
    """返回默认主题强调色"""
    return COLORS['accent']


def get_bg_color():
    """返回默认主题背景色"""
    return COLORS['bg_dark']
