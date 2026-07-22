# -*- coding: utf-8 -*-
"""
自定义小控件
- ElidedLabel: 文本过长时自动省略，完整内容放在 tooltip
- DragDropLineEdit: 支持直接拖入文件夹/文件的路径输入框
"""
import os

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStyle,
    QStyledItemDelegate, QVBoxLayout, QWidget
)
from i18n import tr


class ElidedLabel(QLabel):
    """文本超出宽度时按指定模式省略（默认中间省略，适合路径）"""

    def __init__(self, text='', mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._full_text = ''
        self.setText(text)

    def setText(self, text):  # noqa: N802 (Qt 命名习惯)
        self._full_text = text or ''
        self.setToolTip(self._full_text if self._full_text not in ('', '-') else '')
        self.update()

    def text(self):  # noqa: N802
        return self._full_text

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(self._full_text, self._mode, max(self.width() - 4, 0))
        painter.drawText(self.rect(), int(Qt.AlignLeft | Qt.AlignVCenter), elided)
        painter.end()


class DragDropLineEdit(QLineEdit):
    """支持拖入文件夹（或文件）直接填充路径的输入框，拖入时显示虚线高亮"""

    def __init__(self, parent=None, accept_files=False):
        super().__init__(parent)
        self._accept_files = accept_files
        self.setAcceptDrops(True)
        self.setProperty('dragHover', False)

    def _extract_path(self, mime):
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isdir(path):
                return path
            if self._accept_files and os.path.isfile(path):
                return path
        return None

    def _set_hover(self, on):
        if self.property('dragHover') == on:
            return
        self.setProperty('dragHover', on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):  # noqa: N802
        if self._extract_path(event.mimeData()) is not None:
            event.acceptProposedAction()
            self._set_hover(True)
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):  # noqa: N802
        self._set_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        path = self._extract_path(event.mimeData())
        if path is not None:
            self.setText(os.path.normpath(path))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
        self._set_hover(False)


class ProjectCardDelegate(QStyledItemDelegate):
    """项目卡片绘制委托：图标 + 名称/描述 + 右侧 "···" 提示。

    不使用子控件（setItemWidget 场景下字体渲染异常），
    全部通过 QPainter 绘制，保证在任何显示环境下渲染一致。
    """

    MORE_WIDTH = 34

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.colors = colors
        self._icon_cache = {}

    def sizeHint(self, option, index):
        return QSize(280, 54)

    def _project_pixmap(self, project):
        """项目图标：自定义图片或默认文件夹 SVG（全部带缓存）"""
        import icons
        path = getattr(project, 'icon_path', '') or ''
        if path and os.path.exists(path):
            key = path
            if key not in self._icon_cache:
                pix = QPixmap(path)
                if not pix.isNull():
                    pix = pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._icon_cache[key] = pix
            return self._icon_cache[key]
        # 默认图标也缓存，避免每次 paint 重新渲染 SVG
        key = '__default__'
        if key not in self._icon_cache:
            self._icon_cache[key] = icons.get_pixmap('folder', self.colors['accent'], 18)
        return self._icon_cache[key]

    def paint(self, painter, option, index):
        project = index.data(Qt.UserRole)

        # 只让样式表画选中/悬停背景，默认文本清空
        self.initStyleOption(option, index)
        option.text = ''
        option.icon = QIcon()
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        if project is None:
            return

        import styles
        accent_soft = QColor(styles._rgba(self.colors['accent'], 0.15))
        text_light = QColor(self.colors['text_light'])
        text_dim = QColor(self.colors['text_dim'])

        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 图标底盒
        box = QRectF(rect.left() + 10, rect.center().y() - 18, 36, 36)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent_soft)
        painter.drawRoundedRect(box, 8, 8)

        # 图标
        pix = self._project_pixmap(project)
        pw = pix.width() / pix.devicePixelRatio()
        ph = pix.height() / pix.devicePixelRatio()
        painter.drawPixmap(
            int(box.center().x() - pw / 2), int(box.center().y() - ph / 2), pix
        )

        text_left = rect.left() + 56
        text_width = rect.width() - 56 - self.MORE_WIDTH - 8

        # 名称
        name_font = QFont(option.font)
        name_font.setPointSizeF(10)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(text_light)
        name = painter.fontMetrics().elidedText(project.name, Qt.ElideRight, int(text_width))
        painter.drawText(
            QRectF(text_left, rect.top() + 8, text_width, 20),
            int(Qt.AlignLeft | Qt.AlignVCenter), name
        )

        # 描述
        desc_font = QFont(option.font)
        desc_font.setPointSizeF(8)
        painter.setFont(desc_font)
        painter.setPen(text_dim)
        desc_text = project.description or tr('main.no_description')
        desc = painter.fontMetrics().elidedText(desc_text, Qt.ElideRight, int(text_width))
        painter.drawText(
            QRectF(text_left, rect.top() + 28, text_width, 18),
            int(Qt.AlignLeft | Qt.AlignVCenter), desc
        )

        # "···" 提示
        more_font = QFont(option.font)
        more_font.setPointSizeF(12)
        more_font.setBold(True)
        painter.setFont(more_font)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.setPen(text_light if hovered else text_dim)
        painter.drawText(
            QRectF(rect.right() - self.MORE_WIDTH, rect.top(), self.MORE_WIDTH - 8, rect.height()),
            int(Qt.AlignCenter), '···'
        )

        painter.restore()
