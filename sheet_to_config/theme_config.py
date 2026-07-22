# -*- coding: utf-8 -*-
"""
主题配置模块
管理主题预设、自定义主题配置保存/加载
"""
import json
import os
import tempfile

from sheet_to_config.app_paths import local_data_path
from sheet_to_config.i18n import tr

# 主题预设配置
THEME_PRESETS = {
    'cyber_blue': {
        'name': '赛博蓝',
        'bg_dark': '#1a1a2e',
        'bg_medium': '#16213e',
        'bg_light': '#0f3460',
        'accent': '#e94560',
        'accent_hover': '#ff6b81',
        'text_light': '#eaeaea',
        'text_dim': '#a0a0a0',
        'border': '#2d3561'
    },
    'forest_green': {
        'name': '森林绿',
        'bg_dark': '#1a2f1a',
        'bg_medium': '#1e3a2f',
        'bg_light': '#2d5a3d',
        'accent': '#4ade80',
        'accent_hover': '#86efac',
        'text_light': '#ecfdf5',
        'text_dim': '#a7f3d0',
        'border': '#3d6b4d'
    },
    'violet_dream': {
        'name': '紫罗兰',
        'bg_dark': '#2e1a3e',
        'bg_medium': '#3d1e52',
        'bg_light': '#5a2d7a',
        'accent': '#d946ef',
        'accent_hover': '#e879f9',
        'text_light': '#fae8ff',
        'text_dim': '#e9d5ff',
        'border': '#6b3d8b'
    },
    'obsidian_dark': {
        'name': '曜石黑',
        'bg_dark': '#0a0a0a',
        'bg_medium': '#171717',
        'bg_light': '#262626',
        'accent': '#f59e0b',
        'accent_hover': '#fbbf24',
        'text_light': '#fafafa',
        'text_dim': '#a3a3a3',
        'border': '#404040'
    },
    'amber_warm': {
        'name': '琥珀暖',
        'bg_dark': '#2a1a0a',
        'bg_medium': '#3d2612',
        'bg_light': '#5c3a1a',
        'accent': '#f97316',
        'accent_hover': '#fb923c',
        'text_light': '#fff7ed',
        'text_dim': '#fdba74',
        'border': '#7c4a2a'
    },
    'ocean_teal': {
        'name': '深海青',
        'bg_dark': '#0a2a2e',
        'bg_medium': '#123d42',
        'bg_light': '#1a5c63',
        'accent': '#2dd4bf',
        'accent_hover': '#5eead4',
        'text_light': '#f0fdfa',
        'text_dim': '#99f6e4',
        'border': '#2a7c83'
    },
    'server_room': {
        'name': '机房凌晨',
        'bg_dark': '#0D1117',
        'bg_medium': '#161B22',
        'bg_light': '#1F242C',
        'accent': '#58A6FF',
        'accent_hover': '#79B8FF',
        'text_light': '#C9D1D9',
        'text_dim': '#8B949E',
        'border': '#30363D'
    },
    'picunbg_teal': {
        'name': '青绿',
        'bg_dark': '#0a0f0d',
        'bg_medium': '#111815',
        'bg_light': '#1a211e',
        'accent': '#00d4aa',
        'accent_hover': '#66e5c5',
        'text_light': '#e8f5f0',
        'text_dim': '#8a9a93',
        'border': '#1f2a26'
    }
}

CONFIG_FILE = str(local_data_path('theme_config.json'))


def load_theme_config():
    """加载主题配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config.setdefault('bg_image', None)
            return config
        except Exception:
            pass
    return {'current_theme': 'picunbg_teal', 'custom_colors': None, 'bg_image': None}


def save_theme_config(current_theme, custom_colors=None, bg_image=None):
    """保存主题配置（bg_image 为自定义背景图路径，None 表示无）"""
    config = {
        'current_theme': current_theme,
        'custom_colors': custom_colors,
        'bg_image': bg_image
    }
    try:
        os.makedirs(os.path.dirname(os.path.abspath(CONFIG_FILE)), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存主题配置失败: {e}")


def get_current_theme_colors():
    """获取当前主题颜色"""
    config = load_theme_config()
    theme_id = config.get('current_theme', 'picunbg_teal')
    custom_colors = config.get('custom_colors')
    
    if theme_id == 'custom' and custom_colors:
        return custom_colors
    
    return THEME_PRESETS.get(theme_id, THEME_PRESETS['picunbg_teal']).copy()


def get_all_theme_names():
    """获取所有主题名称"""
    return {k: tr(f'theme.{k}') for k in THEME_PRESETS}


def localized_theme_name(theme_id: str) -> str:
    """Return the display name for a theme without changing its stable ID."""
    if theme_id == 'custom':
        return tr('theme.custom')
    theme = THEME_PRESETS.get(theme_id, {})
    return tr(f'theme.{theme_id}') if theme else theme_id


_BG_CACHE_PATH = os.path.join(
    tempfile.gettempdir(), 'SheetToConfig_bg_cache.png'
)
_BG_MAX_WIDTH = 1600


def get_scaled_bg_image(path):
    """返回缩放后的背景图路径（带磁盘缓存）。

    大图直接作为 QSS border-image 会导致每次重绘都全尺寸缩放，
    界面明显卡顿甚至"未响应"。缩放到 1600px 宽后渲染开销可忽略。
    缓存按源文件路径 + 修改时间校验，源图变化时自动重建。
    """
    if not path or not os.path.exists(path):
        return path
    try:
        from PyQt5.QtGui import QImage, QImageReader

        reader = QImageReader(path)
        src_size = reader.size()
        if src_size.width() <= _BG_MAX_WIDTH:
            return path  # 足够小，直接用原图

        # 缓存有效性：源路径 + 源修改时间记录在同名 .key 文件
        key_path = _BG_CACHE_PATH + '.key'
        key = f'{os.path.abspath(path)}|{os.path.getmtime(path)}'
        if os.path.exists(_BG_CACHE_PATH) and os.path.exists(key_path):
            try:
                with open(key_path, 'r', encoding='utf-8') as f:
                    if f.read() == key:
                        return _BG_CACHE_PATH
            except OSError:
                pass

        img = reader.read()
        if img.isNull():
            return path
        scaled = img.scaledToWidth(
            _BG_MAX_WIDTH, 1  # Qt.SmoothTransformation == 1
        )
        if scaled.save(_BG_CACHE_PATH, 'PNG'):
            with open(key_path, 'w', encoding='utf-8') as f:
                f.write(key)
            return _BG_CACHE_PATH
    except Exception:
        pass
    return path
