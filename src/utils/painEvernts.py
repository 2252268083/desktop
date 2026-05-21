# paintEvents.py
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QBitmap
from PyQt5.QtWidgets import QWidget


def set_rounded_corners(widget, radius=15, bg_color=None):
    """
    为无边框窗口设置圆角遮罩（不影响透明度调节）
    :param widget: 目标窗口 (QWidget / QDialog)
    :param radius: 圆角半径（像素）
    :param bg_color: 保留参数，暂未使用
    """
    widget.setAttribute(Qt.WA_TranslucentBackground, True)#窗口允许背景透明

    def update_mask():
        if widget.width() <= 0 or widget.height() <= 0:
            return#如果窗口宽高还没准备好，就直接返回
        # 创建与窗口大小一致的位图，用于生成遮罩
        bitmap = QBitmap(widget.size())
        # 先用Qt.color0填充整个位图，该颜色对应遮罩中的"透明/不可见区域"
        bitmap.fill(Qt.color0)
        # 在位图上创建绘图对象，准备绘制可见区域
        painter = QPainter(bitmap)
        # 开启抗锯齿，让圆角边缘更平滑
        painter.setRenderHint(QPainter.Antialiasing)
        # 设置画刷为Qt.color1，该颜色对应遮罩中的"不透明/可见区域"
        painter.setBrush(Qt.color1)
        # 禁用画笔，避免绘制多余的边框线条
        painter.setPen(Qt.NoPen)
        # 在整个窗口范围内绘制带圆角的矩形，这个区域会作为窗口的可见部分
        painter.drawRoundedRect(QRect(0, 0, widget.width(), widget.height()), radius, radius)
        # 结束绘图操作，释放资源
        painter.end()
        # 将生成的位图设置为窗口的遮罩，实现圆角效果
        widget.setMask(bitmap)

    original_resize = widget.resizeEvent

    def on_resize(event):
        update_mask()
        if original_resize:
            original_resize(event)

    widget.resizeEvent = on_resize
    update_mask()