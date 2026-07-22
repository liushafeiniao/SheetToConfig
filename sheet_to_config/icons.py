# -*- coding: utf-8 -*-
"""
SVG 图标工厂
所有图标为线性风格（24x24 viewBox），随主题色着色，替代 emoji，
保证在任何机器上渲染一致。
"""
from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS = {
    # 应用标志：表格网格
    'app': (
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<line x1="3" y1="9" x2="21" y2="9"/>'
        '<line x1="3" y1="15" x2="21" y2="15"/>'
        '<line x1="9" y1="3" x2="9" y2="21"/>'
        '<line x1="15" y1="3" x2="15" y2="21"/>'
    ),
    'plus': '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    'search': '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    'edit': (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
        '<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    ),
    'trash': (
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/>'
    ),
    # 导表：向上导出
    'export': (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" y1="3" x2="12" y2="15"/>'
    ),
    # 传共享：分享节点
    'share': (
        '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/>'
        '<circle cx="18" cy="19" r="3"/>'
        '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>'
        '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>'
    ),
    'info': (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="16" x2="12" y2="12"/>'
        '<line x1="12" y1="8" x2="12.01" y2="8"/>'
    ),
    # 主题：水滴
    'theme': '<path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>',
    'language': (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M3 12h18M12 3c2.4 2.4 3.6 5.4 3.6 9s-1.2 6.6-3.6 9c-2.4-2.4-3.6-5.4-3.6-9S9.6 5.4 12 3z"/>'
    ),
    'clear': (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
    ),
    'copy': (
        '<rect x="9" y="9" width="13" height="13" rx="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    ),
    'folder': (
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
    ),
    'up': '<polyline points="18 15 12 9 6 15"/>',
    'down': '<polyline points="6 9 12 15 18 9"/>',
    'check': '<polyline points="20 6 9 17 4 12"/>',
}


def get_pixmap(name, color='#e8f5f0', size=16):
    """渲染指定图标为 QPixmap（2x 渲染保证高分屏清晰）"""
    body = _ICONS.get(name)
    if body is None:
        raise KeyError(f"未知图标: {name}")
    svg = _TEMPLATE.format(color=color, body=body)
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def get_icon(name, color='#e8f5f0', size=16):
    """渲染指定图标为 QIcon"""
    return QIcon(get_pixmap(name, color, size))


def available_icons():
    """返回全部图标名"""
    return sorted(_ICONS.keys())
