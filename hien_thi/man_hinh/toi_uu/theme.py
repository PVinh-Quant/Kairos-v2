"""toi_uu/theme.py — Bảng màu Theme + helper CSS/badge dùng chung cho màn Tối ưu."""
import sys
import os
import json
import time

import numpy as np

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData, QRectF, QPointF, QDate
from PyQt6.QtGui import (
    QColor, QDrag, QPainter, QPen, QBrush, QFont,
    QPainterPath, QLinearGradient, QFontMetrics,
)

from hien_thi.giao_dien.theme import Theme


def _make_badge_pixmap(text):
    """Ảnh xem trước khi kéo (badge bo góc viền Accent) — dùng chung cho ModuleItem."""
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import QRect
    font = QFont("Segoe UI", 9, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    w = max(fm.horizontalAdvance(text) + 24, 70)
    h = 24
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    pr = QPainter(pm)
    pr.setRenderHint(QPainter.RenderHint.Antialiasing)
    pr.setBrush(QBrush(QColor(14, 14, 14, 210)))
    pr.setPen(QPen(QColor(Theme.ACCENT), 1.5))
    pr.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)
    pr.setPen(QColor(Theme.TEXT_MAIN))
    pr.setFont(font)
    pr.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, text)
    pr.end()
    return pm, w, h


def _compact_spin_css():
    return (
        f"QAbstractSpinBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 3px; padding: 1px 4px; font-size: 10px; }}"
        f"QAbstractSpinBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
        f"QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; height: 0; border: none; }}"
    )


def _compact_combo_css():
    return (
        f"QComboBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 3px; padding: 1px 4px; font-size: 10px; }}"
        f"QComboBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
        f"QComboBox::drop-down {{ width: 14px; border: none; }}"
        f"QComboBox QAbstractItemView {{ background: {Theme.CARD}; color: {Theme.TEXT_MAIN}; selection-background-color: {Theme.GRID}; border: 1px solid {Theme.BORDER}; }}"
    )
def _elide(text, px, bold=True, size=12):
    """Cắt chuỗi cho vừa px theo font Segoe UI (thêm dấu …)."""
    f = QFont("Segoe UI")
    f.setPixelSize(size)
    f.setBold(bold)
    return QFontMetrics(f).elidedText(str(text), Qt.TextElideMode.ElideRight, px)


def _pill_css(fs=9):
    """Nhãn pill nhỏ nền vàng nhạt (đếm symbol / tag)."""
    return (
        "QLabel { color: %s; background: rgba(200,170,110,0.16); border: none; "
        "border-radius: 8px; font-size: %dpx; font-weight: bold; padding: 1px 7px; }" % (Theme.ACCENT, fs)
    )


def _icon_btn_css(hover_color):
    """Nút icon nhỏ (✎ / ×) — hover đổi màu + nền mờ."""
    return (
        f"QPushButton {{ color: {Theme.TEXT_SUB}; background: transparent; border: none; border-radius: 4px; }}"
        f"QPushButton:hover {{ color: {hover_color}; background: {Theme.GRID}; }}"
    )


def _regime_toggle_css():
    """Nút bật/tắt 1 trạng thái thị trường (checkable): tắt = xám, bật = xanh."""
    return (
        "QPushButton { color: %s; background: transparent; border: 1px solid %s; "
        "border-radius: 4px; font-size: 9px; padding: 2px 4px; text-align: left; }"
        "QPushButton:hover { border-color: %s; }"
        "QPushButton:checked { color: %s; border-color: %s; background: rgba(8,153,129,0.16); font-weight: bold; }"
        % (Theme.TEXT_SUB, Theme.BORDER, Theme.ACCENT, Theme.WIN, Theme.WIN)
    )


__all__ = ["Theme", "_make_badge_pixmap", "_compact_spin_css", "_compact_combo_css",
           "_elide", "_pill_css", "_icon_btn_css", "_regime_toggle_css"]
