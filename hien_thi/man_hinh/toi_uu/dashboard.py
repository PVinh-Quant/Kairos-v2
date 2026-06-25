"""toi_uu/dashboard.py — DashboardToiUu: vỏ màn Tối ưu (builder kéo-thả + thư viện)."""
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
    QLayout,
    QMenu,
    QInputDialog,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QMimeData, QRectF, QPointF, QDate,
    QSize, QRect, QPoint,
)
from PyQt6.QtGui import (
    QColor, QDrag, QPainter, QPen, QBrush, QFont,
    QPainterPath, QLinearGradient, QFontMetrics,
)
import numpy as np
from hien_thi.duong_dan import PROJECT_ROOT, ASSETS_DIR
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from toi_uu_hoa.kiem_dinh import danh_gia_guardrails, MIN_TRADES_OOS              
from toi_uu_hoa.dong_co_backtest import MIN_DAYS_TIN_CAY              
from .theme import *
from .dinh_nghia import *
from .tien_ich import *
from .bieu_do import *
from .worker import *
from .thanh_phan import *
from .data_pool import *
from .trang_chu import TrangChuMixin
from .thong_bao import hien_thong_bao


                                                                                       
NAV_AN_KHOI = {"realtime", "demo", "backtest", "vectorized"}
                                                                               
CHAY_CHUC_NANG = [
    ("realtime", "Realtime"),
    ("demo", "Demo"),
    ("backtest", "Backtest"),
    ("vectorized", "Biểu đồ nến"),
]


class FlowLayout(QLayout):
    """Layout cuộn-dòng (wrap) tự xếp các thẻ con từ trái→phải, xuống dòng khi hết chiều rộng.

    Dùng cho lưới thẻ responsive: thẻ giữ kích thước cố định, số cột tự co theo bề rộng.
    """

    def __init__(self, parent=None, margin=0, h_spacing=14, v_spacing=14):
        super().__init__(parent)
        self._items = []
        self._h_space = h_spacing
        self._v_space = v_spacing
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_height = 0
        right = rect.right() - m.right()
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            next_x = x + w + self._h_space
            if next_x - self._h_space > right and line_height > 0:
                x = rect.x() + m.left()
                y = y + line_height + self._v_space
                next_x = x + w + self._h_space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x = next_x
            line_height = max(line_height, h)
        return y + line_height - rect.y() + m.bottom()


class StrategyCard(QFrame):
    """Thẻ (chip) hiển thị 1 bộ tham số đã lưu — phong cách quant library, dark theme.

    Tín hiệu:
        clicked(card)        — single click: chọn / bỏ chọn
        doubleClicked(card)  — double click: mở vào builder
        menuRequested(card, global_pos) — chuột phải: context menu
    """

    clicked = pyqtSignal(object)
    doubleClicked = pyqtSignal(object)
    menuRequested = pyqtSignal(object, object)

    CARD_W = 188
    CARD_H = 142

                                                                             
    _STATUS = {
        "DEPLOY": ("PASS", "#22C55E"),
        "REJECT": ("REJECT", "#EF4444"),
    }
    _STATUS_DEFAULT = ("REVIEW", "#F59E0B")

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.ten = data["ten"]
        self._selected = False
        self._hover = False
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setObjectName("strategyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.menuRequested.emit(self, self.mapToGlobal(pos))
        )

                                                                                       
                                                           
        self._glow = None

        self._build_ui()
        self._apply_style()

                                                                              
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 11, 13, 10)
        lay.setSpacing(0)
        inner_w = self.CARD_W - 26

                                                                 
        name = QLabel()
        name_font = QFont()
        name_font.setPixelSize(13)
        name_font.setWeight(QFont.Weight.DemiBold)
        name.setFont(name_font)
        fm = QFontMetrics(name_font)
        name.setText(fm.elidedText(self.ten, Qt.TextElideMode.ElideRight, inner_w))
        name.setToolTip(self.ten)
        name.setStyleSheet(f"color: {Theme.TEXT_MAIN}; background: transparent;")
        lay.addWidget(name)

                                       
        combo = QLabel(self.data.get("combo_label", "") or "—")
        cf = QFont(); cf.setPixelSize(12)
        combo.setFont(cf)
        combo.setText(fm.elidedText(self.data.get("combo_label", "") or "—",
                                    Qt.TextElideMode.ElideRight, inner_w))
        combo.setStyleSheet(f"color: {Theme.TEXT_SUB}; background: transparent;")
        lay.addWidget(combo)

        lay.addSpacing(8)

                                               
        sh = self.data.get("oos_sharpe", 0.0)
        sh_txt = "—" if sh <= -9.99 else f"{sh:+.3f}"
        lay.addLayout(self._metric_row("Sharpe", sh_txt, Theme.ENTRY))
        lay.addLayout(self._metric_row("OOS/IS", f"{self.data.get('oos_is_ratio', 0.0):.2f}", Theme.TEXT_MAIN))

        lay.addStretch(1)

                                          
        label, color = self._STATUS.get(self.data.get("verdict", ""), self._STATUS_DEFAULT)
        status = QLabel(f"●  {label}")
        sff = QFont(); sff.setPixelSize(12); sff.setBold(True)
        status.setFont(sff)
        status.setStyleSheet(f"color: {color}; background: transparent;")
        lay.addWidget(status)

        lay.addSpacing(3)

                                                        
        ts = QLabel(f"🕒  {self._fmt_ngay(self.data.get('ngay_luu', ''))}")
        tf = QFont(); tf.setPixelSize(11)
        ts.setFont(tf)
        ts.setStyleSheet(f"color: {Theme.TEXT_SUB}; background: transparent;")
        lay.addWidget(ts)

                                                
        self._check = QLabel("✓", self)
        self._check.setFixedSize(18, 18)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setStyleSheet(
            f"color: #131722; background: {Theme.ACCENT}; border-radius: 9px;"
            f"font-size: 11px; font-weight: bold;"
        )
        self._check.move(self.CARD_W - 18 - 9, 9)
        self._check.hide()

    def _metric_row(self, label, value, value_color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(4)
        lb = QLabel(label)
        lf = QFont(); lf.setPixelSize(11)
        lb.setFont(lf)
        lb.setStyleSheet(f"color: {Theme.TEXT_SUB}; background: transparent;")
        val = QLabel(value)
        vf = QFont(); vf.setPixelSize(12); vf.setBold(True)
        val.setFont(vf)
        val.setStyleSheet(f"color: {value_color}; background: transparent;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lb)
        row.addStretch(1)
        row.addWidget(val)
        return row

    @staticmethod
    def _fmt_ngay(s):
        """'2026-06-22 11:19:00' → '22/06/26 11:19'."""
        try:
            d, t = s.split(" ")
            y, mo, da = d.split("-")
            hh, mm = t.split(":")[:2]
            return f"{da}/{mo}/{y[2:]} {hh}:{mm}"
        except Exception:
            return s or "—"

                                                                              
    def set_selected(self, on):
        self._selected = bool(on)
        self._check.setVisible(self._selected)
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            border = Theme.ACCENT
            self._set_glow(QColor(200, 170, 110, 150), 20)               
        elif self._hover:
            border = "#3A4252"
            self._set_glow(QColor(120, 130, 150, 90), 14)
        else:
            border = "#1F2937"
            self._set_glow(None, 0)
        self.setStyleSheet(
            f"QFrame#strategyCard {{ background: #0F1117; border: 1px solid {border};"
            f" border-radius: 12px; }}"
        )

    def _set_glow(self, color, blur):
        """Gắn/gỡ hiệu ứng glow theo nhu cầu; gỡ hẳn khi nhàn rỗi để nhẹ bộ nhớ/vẽ."""
        if color is None:
            if self._glow is not None:
                self.setGraphicsEffect(None)                    
                self._glow = None
            return
        if self._glow is None:
            self._glow = QGraphicsDropShadowEffect(self)
            self._glow.setOffset(0, 0)
            self.setGraphicsEffect(self._glow)
        self._glow.setColor(color)
        self._glow.setBlurRadius(blur)

                                                                              
    def enterEvent(self, event):
        self._hover = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self)
        super().mouseDoubleClickEvent(event)


class StylizedBrandLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(160)
        self.setFixedHeight(38)
        self.setStyleSheet("background: transparent; border: none;")

                                         
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

                                                                                                  
        self.brand = QLabel("KAIROS")
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        self.brand.setFont(font)
        self.brand.setStyleSheet(f"color: {Theme.ACCENT}; background: transparent; border: none;")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.brand)

                                                                
        self.subtitle = QLabel("Analytics System v2")
        font_sub = QFont("Segoe UI", 7, QFont.Weight.Bold)
        font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        self.subtitle.setFont(font_sub)
        self.subtitle.setStyleSheet("color: #787B86; background: transparent; border: none;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)

class HomeTile(QFrame):
    clicked = pyqtSignal()
    def __init__(self, ten, mota, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(85)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border: 1.5px solid {Theme.ACCENT};
                background-color: {Theme.GRID};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        lbl_ten = QLabel(ten)
        lbl_ten.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 14px; font-weight: bold; background: transparent; border: none;")

        lbl_mota = QLabel(mota)
        lbl_mota.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; border: none;")

        lay.addWidget(lbl_ten)
        lay.addWidget(lbl_mota)
        lay.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class SparklineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(30)                                                       
        self.points = [10, 15, 12, 18, 14, 22, 19, 28, 25, 35, 32, 45, 40, 52, 48, 60]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if not self.points:
                                                                                              
            painter.setPen(QPen(QColor(Theme.BORDER), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, int(h / 2), w, int(h / 2))
            painter.setPen(QColor("#555861"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu vốn (chạy realtime/demo để có)")
            return

        n = len(self.points)

        max_val = max(self.points)
        min_val = min(self.points)
        rng = (max_val - min_val) if max_val != min_val else 1
        
        path = QPainterPath()
        for i, val in enumerate(self.points):
            x = i * (w / (n - 1))
            y = h - 4 - ((val - min_val) / rng) * (h - 8)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
                
        gradient_path = QPainterPath(path)
        gradient_path.lineTo(w, h)
        gradient_path.lineTo(0, h)
        gradient_path.closeSubpath()
        
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor(200, 170, 110, 60))
        gradient.setColorAt(1, QColor(200, 170, 110, 0))
        painter.fillPath(gradient_path, QBrush(gradient))
        
        pen = QPen(QColor(Theme.ACCENT), 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

class PipelineProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        padding = w / 12
        step_w = w / 6
        
        painter.setPen(QPen(QColor("#2A2E39"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(int(padding), int(h/2), int(w - padding), int(h/2))
        
        painter.setPen(QPen(QColor(Theme.ACCENT), 2, Qt.PenStyle.SolidLine))
        painter.drawLine(int(padding), int(h/2), int(padding + 3 * step_w), int(h/2))
        
        for i in range(6):
            cx = padding + i * step_w
            cy = h / 2
            
            if i < 4:
                painter.setBrush(QColor(Theme.BG))
                painter.setPen(QPen(QColor(Theme.ACCENT), 2))
                painter.drawEllipse(QPointF(cx, cy), 6, 6)
                painter.setBrush(QColor(Theme.ACCENT))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(cx, cy), 3, 3)
            else:
                painter.setBrush(QColor(Theme.BG))
                painter.setPen(QPen(QColor("#555861"), 2))
                painter.drawEllipse(QPointF(cx, cy), 5, 5)


class CustomIconWidget(QWidget):
    def __init__(self, icon_type, bg_color, is_circle=False, size=32, border_style=None, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.bg_color = bg_color
        self.is_circle = is_circle
        self.icon_size = size
        self.border_style = border_style
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
                            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        
        if self.is_circle:
            painter.drawEllipse(QRectF(0, 0, w, h))
        else:
            painter.drawRoundedRect(QRectF(0, 0, w, h), 6, 6)
            
                                  
        if self.border_style == "active":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(Qt.GlobalColor.white), 2))
            if self.is_circle:
                painter.drawEllipse(QRectF(1, 1, w - 2, h - 2))
            else:
                painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 6, 6)
                
                                  
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(Qt.GlobalColor.white)))
        
        if self.icon_type == 'database':
            bar_w = w * 0.44
            bar_h = h * 0.11
            gap = h * 0.05
            
            total_h = 3 * bar_h + 2 * gap
            start_y = (h - total_h) / 2
            start_x = (w - bar_w) / 2
            
            for i in range(3):
                y = start_y + i * (bar_h + gap)
                painter.drawRoundedRect(QRectF(start_x, y, bar_w, bar_h), bar_h / 2, bar_h / 2)
                
        elif self.icon_type == 'features':
            font = QFont("Segoe UI", int(self.icon_size * 0.45), QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QPen(QColor(Qt.GlobalColor.white)))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Σ")
            
        elif self.icon_type == 'toi_uu':
            path = QPainterPath()
            start_x = w * 0.24
            end_x = w * 0.76
            center_y = h * 0.5
            amp = h * 0.16
            path.moveTo(start_x, center_y)
            import math
            for x_i in range(int(start_x), int(end_x) + 1):
                t = (x_i - start_x) / (end_x - start_x)
                angle = t * 2 * math.pi
                y_i = center_y - math.sin(angle) * amp
                path.lineTo(x_i, y_i)
            
            pen = QPen(QColor(Qt.GlobalColor.white), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
            
        elif self.icon_type == 'backtest':
            bar_w = w * 0.09
            gap = w * 0.06
            total_w = 3 * bar_w + 2 * gap
            start_x = (w - total_w) / 2
            base_y = h * 0.72
            
            h1 = h * 0.24
            h2 = h * 0.46
            h3 = h * 0.34
            
            painter.drawRoundedRect(QRectF(start_x, base_y - h1, bar_w, h1), 0.5, 0.5)
            painter.drawRoundedRect(QRectF(start_x + bar_w + gap, base_y - h2, bar_w, h2), 0.5, 0.5)
            painter.drawRoundedRect(QRectF(start_x + 2 * (bar_w + gap), base_y - h3, bar_w, h3), 0.5, 0.5)
            
        elif self.icon_type == 'chart':
            candle_w = w * 0.09
            gap = w * 0.07
            total_w = 3 * candle_w + 2 * gap
            start_x = (w - total_w) / 2
            center_y = h * 0.5
            
            candles = [
                (0, -h*0.09, h*0.19, -h*0.19, h*0.38),
                (1, -h*0.19, h*0.25, -h*0.28, h*0.50),
                (2, -h*0.09, h*0.16, -h*0.16, h*0.31),
            ]
            for idx, by, bh, wy, wh in candles:
                cx = start_x + idx * (candle_w + gap)
                painter.setPen(QPen(QColor(Qt.GlobalColor.white), 1.2))
                painter.drawLine(QPointF(cx + candle_w / 2, center_y + wy), QPointF(cx + candle_w / 2, center_y + wy + wh))
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(Qt.GlobalColor.white))
                painter.drawRect(QRectF(cx, center_y + by, candle_w, bh))
                
        elif self.icon_type == 'demo':
            path = QPainterPath()
            tri_w = w * 0.26
            tri_h = h * 0.30
            start_x = w * 0.40
            start_y = h * 0.5
            
            path.moveTo(start_x, start_y - tri_h / 2)
            path.lineTo(start_x + tri_w, start_y)
            path.lineTo(start_x, start_y + tri_h / 2)
            path.closeSubpath()
            
            painter.drawPath(path)
            
        elif self.icon_type == 'realtime':
            bar_w = w * 0.07
            gap = w * 0.05
            total_w = 4 * bar_w + 3 * gap
            start_x = (w - total_w) / 2
            base_y = h * 0.69
            
            for i in range(4):
                bar_h = h * (0.13 + i * 0.13)
                bx = start_x + i * (bar_w + gap)
                painter.drawRoundedRect(QRectF(bx, base_y - bar_h, bar_w, bar_h), 0.5, 0.5)


class ActionRow(QFrame):
    clicked = pyqtSignal()
    def __init__(self, title, desc, icon_type, icon_color, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: {Theme.GRID};
            }}
        """)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(12)
        
        icon = CustomIconWidget(icon_type=icon_type, bg_color=icon_color, is_circle=False, size=32, parent=self)
        
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 13px; font-weight: bold; background: transparent;")
        
        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet("color: #787B86; font-size: 10px; background: transparent;")
        
        text_box.addWidget(lbl_title)
        text_box.addWidget(lbl_desc)
        
        chevron = QLabel("→")
        chevron.setStyleSheet("color: #555861; font-size: 14px; background: transparent;")
        
        lay.addWidget(icon)
        lay.addLayout(text_box, 1)
        lay.addWidget(chevron)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class DashboardToiUu(TrangChuMixin, QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(f"background-color: {Theme.BG};")

        self.indicator_items = {}
        self._selected_indicator_key = None
        self.tf_columns = {}
        self.combo_specs = []                                                               
        self.combo_result = None
        self.combo_result_specs = []
        self.nav_btns = {}
        self.worker = None
        self.phien = None                                                                                
        self.active_modules = {}                                              
        self.module_zone = None                                                    
        self.module_items = {}                                       
        self.bo_du_lieu = doc_bo_du_lieu()                                     
        for _i, _it in enumerate(self.bo_du_lieu):
            _it.setdefault("id", f"ds_load_{_i}")
        self.active_dataset = None                                                         
        self.data_zone = None                                                    
        self.data_pool_layout = None                                    

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._build_header(root)

                                                                                            
        self._workspace = QSplitter(Qt.Orientation.Horizontal)
        self._workspace.setStyleSheet(f"QSplitter::handle {{ background-color: {Theme.BORDER}; }}")
        self._workspace.setHandleWidth(1)
        self._left_panel = self._build_left_panel()
        self._workspace.addWidget(self._left_panel)
        self._workspace.addWidget(self._build_right_panel())
        self._workspace.setStretchFactor(0, 0)
        self._workspace.setStretchFactor(1, 1)
        self._workspace.setSizes([230, 1000])

                                                                                        
                                                                                              
        self._man_con = {}
        self.outer_stack = QStackedWidget()
        self.outer_stack.addWidget(self._workspace)
        self._home_page = self._build_home_page()
        self.outer_stack.addWidget(self._home_page)
        root.addWidget(self.outer_stack, 1)

        self._build_statusbar(root)
        self.di_toi_man("home")
        self._render_grid()
        self._set_combo_metrics_placeholder()
        self._load_existing_results()
        self._init_modules_from_Q()
        self._render_modules()

                                                                              
    def _build_header(self, parent_layout):
        header = QFrame()
        header.setObjectName("header_frame")
        header.setFixedHeight(45)
        header.setStyleSheet(f"QFrame#header_frame {{ background: {Theme.CARD}; border: none; border-bottom: 1px solid {Theme.BORDER}; }}")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 4, 18, 4)
        lay.setSpacing(10)
                                                                                                                       
        brand = StylizedBrandLabel()
        lay.addWidget(brand)
        lay.addSpacing(22)

                                                                                        
                                                                                           
                                                                           
                                                  
                                                                                       
                                                                                            
        nav = [("home", "Trang chủ"), ("toi_uu", "Tối ưu")]
        van_hanh = []
        try:
            from hien_thi import danh_sach_man_hinh
            for mh in danh_sach_man_hinh():
                if mh["khoa"] == "toi_uu" or mh["khoa"] in NAV_AN_KHOI:
                    continue
                if mh["khoa"] == "thu_cong":
                    nav.append((mh["khoa"], mh["nhan"]))
                else:
                    van_hanh.append((mh["khoa"], mh["nhan"]))
            nav.append(("da_luu", "Đã lưu"))
            nav += van_hanh
        except Exception:                
            nav += [("thu_cong", "Chỉ báo thủ công"), ("da_luu", "Đã lưu"), ("cai_dat", "Cài đặt")]

        for khoa, name in nav:
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=khoa: self.di_toi_man(k))
            self.nav_btns[khoa] = btn
            lay.addWidget(btn)

        lay.addStretch()
        parent_layout.addWidget(header)

                                                                                
    def di_toi_man(self, khoa):
        """Điều hướng nav toàn cục.

        toi_uu/da_luu → 2 trang trong workspace tối ưu (builder/thư viện).
        home          → Trang chủ.
        còn lại       → màn vận hành (Realtime/Demo/Backtest/Biểu đồ nến), tạo lazy.
        """
        if khoa in ("toi_uu", "da_luu"):
            self._switch_page(0 if khoa == "toi_uu" else 1)
            return
        if khoa == "home":
            self.outer_stack.setCurrentWidget(self._home_page)
            self._lam_moi_trang_chu()
        else:
            w = self._man_con.get(khoa)
            if w is None:                                                                        
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import Qt
                self.lbl_status.setText(f"Đang mở {khoa}… (lần đầu hơi lâu do nạp dữ liệu)")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()                                                     
                try:
                    w = self._tao_man_con(khoa)
                finally:
                    QApplication.restoreOverrideCursor()
                self.lbl_status.setText("Sẵn sàng.")
            if w is None:
                self.lbl_status.setText(f"⚠ Không mở được màn: {khoa}")
                return
            self.outer_stack.setCurrentWidget(w)
        self._highlight_nav(khoa)

    def _tao_man_con(self, khoa):
        """Lazy tạo 1 màn vận hành qua registry (lay_lop) + tiêm bus phiên, cache lại."""
        try:
            from hien_thi import lay_lop
            w = lay_lop(khoa)()
        except Exception as e:                
            print(f"[toi_uu shell] Lỗi tạo màn {khoa}: {e}", flush=True)
            return None
        if getattr(self, "phien", None) is not None:
            w.phien = self.phien
            gan = getattr(w, "gan_phien", None)
            if callable(gan):
                gan(self.phien)
        self._man_con[khoa] = w
        self.outer_stack.addWidget(w)
        return w

    def _highlight_nav(self, khoa_active):
        """Tô sáng nút nav đang chọn (string key)."""
        for k, btn in self.nav_btns.items():
            active = (k == khoa_active)
            style = (
                self._btn_style(Theme.GRID, text_color=Theme.ACCENT) if active
                else self._btn_style("transparent", text_color=Theme.TEXT_SUB)
            )
            btn.setStyleSheet(style + " QPushButton { padding: 4px 12px; font-size: 13px; }")

                                                                              
                                                                            
    def _build_left_panel(self):
        panel = QFrame()
        panel.setMinimumWidth(220)
        panel.setStyleSheet(f"background: {Theme.CARD_ALT}; border: none;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

                   
        tabbar = QHBoxLayout()
        tabbar.setContentsMargins(0, 0, 0, 0)
        tabbar.setSpacing(0)
        self.left_tab_btns = {}
        for idx, name in [(0, "Chỉ báo"), (1, "Mô-đun"), (2, "Plugin"), (3, "Data Pool")]:
            b = QPushButton(name)
            b.setCheckable(True)
            b.setFixedHeight(34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, i=idx: self._switch_left_tab(i))
            self.left_tab_btns[idx] = b
            tabbar.addWidget(b, 1)
        lay.addLayout(tabbar)

        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self._build_indicator_palette())     
        self.left_stack.addWidget(self._build_module_palette())        
        self.left_stack.addWidget(self._build_plugin_palette())        
        self.left_stack.addWidget(self._build_data_pool_palette())     
        lay.addWidget(self.left_stack, 1)
        self._switch_left_tab(0)
        return panel

    def _switch_left_tab(self, idx):
        self.left_stack.setCurrentIndex(idx)
        for i, b in self.left_tab_btns.items():
            active = (i == idx)
            b.setChecked(active)
            b.setStyleSheet(
                f"QPushButton {{ background: {Theme.GRID if active else Theme.BG}; "
                f"color: {Theme.ACCENT if active else Theme.TEXT_SUB}; "
                f"font-weight: bold; font-size: 12px; border: none; "
                f"border-bottom: 2px solid {Theme.ACCENT if active else Theme.BORDER}; }}"
            )

    def _build_indicator_palette(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QLabel(f"  CHỈ BÁO ({sum(len(v) for v in CATEGORIES.values())})  ·  kéo thả →")
        head.setFixedHeight(28)
        head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; padding-left: 8px;")
        lay.addWidget(head)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm chỉ báo...")
        self.search.setStyleSheet(f"background: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 6px; margin: 8px;")
        self.search.textChanged.connect(self._filter_indicators)
        lay.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(6, 0, 6, 10)
        self.list_layout.setSpacing(2)
        self.category_headers = []
        for cat, keys in CATEGORIES.items():
            cat_lbl = QLabel(cat.upper())
            cat_lbl.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 10px; font-weight: bold; padding: 10px 8px 4px 8px; background: transparent;")
            self.list_layout.addWidget(cat_lbl)
            self.category_headers.append((cat_lbl, keys))
            for key in keys:
                item = IndicatorItem(key)
                item.clicked.connect(self._select_quick)
                self.indicator_items[key] = item
                self.list_layout.addWidget(item)
        self.list_layout.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)
        return page

    def _build_plugin_palette(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(8, 6, 8, 2)
        head = QLabel("CHIẾN LƯỢC PLUGIN")
        head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent;")
        top.addWidget(head)
        top.addStretch()
        btn_reload = QPushButton("Nạp lại")
        btn_reload.setToolTip("Quét lại plugin trong chien_luoc/user_strategies/")
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setStyleSheet(self._btn_style(Theme.BORDER, text_color=Theme.TEXT_MAIN) + " QPushButton { font-size: 11px; padding: 3px 10px; }")
        btn_reload.clicked.connect(self._nap_lai_plugin)
        top.addWidget(btn_reload)
        lay.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.plugin_list_layout = QVBoxLayout(container)
        self.plugin_list_layout.setContentsMargins(6, 4, 6, 10)
        self.plugin_list_layout.setSpacing(2)
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

        self.btn_run_plugin = QPushButton("▶ Tối ưu plugin")
        self.btn_run_plugin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run_plugin.setStyleSheet(self._btn_style(Theme.PURPLE))
        self.btn_run_plugin.clicked.connect(self.run_plugin)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(8, 0, 8, 8)
        wrap.addWidget(self.btn_run_plugin)
        lay.addLayout(wrap)

        self._plugin_items = {}
        self._selected_plugin_key = None
        self._nap_lai_plugin()
        return page

    def _build_module_palette(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QLabel(f"  MÔ-ĐUN ({len(MODULE_DEFS)})  ·  kéo thả →")
        head.setFixedHeight(28)
        head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; padding-left: 8px;")
        lay.addWidget(head)

        hint = QLabel("Kéo mô-đun sang khung “Mô-đun” bên phải để bật. Có mặt = BẬT, kéo ra (×) = TẮT.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; padding: 4px 10px 8px 10px;")
        lay.addWidget(hint)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        box = QVBoxLayout(container)
        box.setContentsMargins(6, 0, 6, 10)
        box.setSpacing(2)
        for mid in MODULE_DEFS:
            it = ModuleItem(mid)
            self.module_items[mid] = it
            box.addWidget(it)
        box.addStretch()
        lay.addWidget(container, 1)
        return page

    def _build_data_pool_palette(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QLabel("  Data Pool  ·  kéo vào khung Run →")
        head.setFixedHeight(28)
        head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; padding-left: 8px;")
        lay.addWidget(head)

        hint = QLabel("Mỗi chip = 1 nhóm Symbol + khoảng ngày. Kéo chip vào khung “Data Pool” ở tab Tối ưu để chạy trên dữ liệu đó.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; padding: 4px 10px 8px 10px;")
        lay.addWidget(hint)

        btn_add = QPushButton("＋ Tạo bộ dữ liệu")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(self._btn_style(Theme.ACCENT) + " QPushButton { font-size: 12px; padding: 6px 10px; }")
        btn_add.clicked.connect(self._them_bo_du_lieu)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(8, 0, 8, 6)
        wrap.addWidget(btn_add)
        lay.addLayout(wrap)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.data_pool_layout = QVBoxLayout(container)
        self.data_pool_layout.setContentsMargins(6, 0, 6, 10)
        self.data_pool_layout.setSpacing(6)
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)
        self._render_data_pool()
        return page

    def _render_data_pool(self):
        if self.data_pool_layout is None:
            return
        while self.data_pool_layout.count():
            it = self.data_pool_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        if not self.bo_du_lieu:
            empty = QLabel("Chưa có bộ dữ liệu nào.\nBấm “＋ Tạo bộ dữ liệu”.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; padding: 10px;")
            self.data_pool_layout.addWidget(empty)
        else:
            for item in self.bo_du_lieu:
                self.data_pool_layout.addWidget(DataChip(item, self))
        self.data_pool_layout.addStretch()

    def _them_bo_du_lieu(self):
        dlg = DataPoolDialog(item=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.get_data():
            data = dlg.get_data()
            data["id"] = f"ds_{int(time.time() * 1000)}"
            self.bo_du_lieu.append(data)
            luu_bo_du_lieu(self.bo_du_lieu)
            self._render_data_pool()
            self.lbl_status.setText(f"Đã tạo bộ dữ liệu “{data['ten']}” ({len(data['symbols'])} symbol).")

    def _sua_bo_du_lieu(self, did):
        item = next((x for x in self.bo_du_lieu if x.get("id") == did), None)
        if item is None:
            return
        dlg = DataPoolDialog(item=item, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.get_data():
            item.update(dlg.get_data())
            luu_bo_du_lieu(self.bo_du_lieu)
            self._render_data_pool()
            if self.active_dataset and self.active_dataset.get("id") == did:
                self.active_dataset = dict(item)
                self._render_data_zone()
            self.lbl_status.setText(f"Đã cập nhật bộ dữ liệu “{item['ten']}”.")

    def _xoa_bo_du_lieu(self, did):
        self.bo_du_lieu = [x for x in self.bo_du_lieu if x.get("id") != did]
        luu_bo_du_lieu(self.bo_du_lieu)
        if self.active_dataset and self.active_dataset.get("id") == did:
            self.active_dataset = None
            self._render_data_zone()
        self._render_data_pool()

    def _on_data_drop(self, mime):
        if not mime.startswith("data:"):
            return
        did = mime.split(":", 1)[1]
        item = next((x for x in self.bo_du_lieu if x.get("id") == did), None)
        if item is None:
            return
        self.active_dataset = dict(item)
        self._render_data_zone()
        self.lbl_status.setText(f"Sẽ tối ưu trên bộ dữ liệu “{item.get('ten', '')}” ({len(item.get('symbols', []))} symbol).")

    def _clear_active_dataset(self):
        self.active_dataset = None
        self._render_data_zone()
        self.lbl_status.setText("Bỏ chọn bộ dữ liệu — dùng Symbol/ngày trong config.")

    def _render_data_zone(self):
        if self.data_zone is None:
            return
        if self.active_dataset:
            self.data_zone.set_chips([ActiveDatasetChip(self.active_dataset, self)])
        else:
            self.data_zone.set_chips([])

                                                                              
    def _build_right_panel(self):
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_builder_page())      
        self.stack.addWidget(self._build_thu_vien_page())     
        return self.stack

    def _build_builder_page(self):
        page = QWidget()
        page.setStyleSheet(f"background: {Theme.BG};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.lbl_builder_title = QLabel("Kéo chỉ báo từ trái thả vào cột khung thời gian → bấm “▶ Tối ưu”")
        self.lbl_builder_title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 14px;")
        lay.addWidget(self.lbl_builder_title)

        quick = QHBoxLayout()
        quick.setSpacing(8)
        btn_clear = QPushButton("Xóa hết")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(self._btn_style(Theme.BORDER, text_color=Theme.TEXT_MAIN))
        btn_clear.clicked.connect(self._clear_combo)
        quick.addWidget(self._mk_label("Mục tiêu:"))
        self.combo_objective = QComboBox()
        for _txt, _val in (("Sharpe", "sharpe"), ("Sortino", "sortino"), ("Calmar", "calmar")):
            self.combo_objective.addItem(_txt, _val)
        self.combo_objective.setStyleSheet(self._combo_style() + "QComboBox { min-width: 0px; max-width: 80px; padding: 3px 18px 3px 6px; } QComboBox::drop-down { width: 14px; }")
        self.combo_objective.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_objective.setToolTip("Chỉ số mục tiêu tối đa hóa khi dò tham số (Sharpe / Sortino / Calmar)")
        quick.addWidget(self.combo_objective)

        quick.addWidget(self._mk_label("Logic:"))
        self.combo_logic = QComboBox()
        for _txt, _val in (("AND", "and"), ("OR", "or")):
            self.combo_logic.addItem(_txt, _val)
        self.combo_logic.setStyleSheet(self._combo_style() + "QComboBox { min-width: 0px; max-width: 58px; padding: 3px 18px 3px 6px; } QComboBox::drop-down { width: 14px; }")
        self.combo_logic.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_logic.setToolTip(
            "Cách kết hợp các chỉ báo TRIGGER:\n"
            "• AND: mọi trigger phải đồng thuận mới vào lệnh.\n"
            "• OR: bất kỳ trigger cho tín hiệu là vào.\n"
            "(Filter luôn AND — phải cùng chiều thì mới cho lệnh.)"
        )
        quick.addWidget(self.combo_logic)
        self.combo_logic.currentIndexChanged.connect(self._update_builder_title)

        quick.addWidget(self._mk_label("Giữ nến:"))
        self.spin_persist = QSpinBox()
        self.spin_persist.setRange(1, 200)
        self.spin_persist.setValue(1)
        self.spin_persist.setStyleSheet(self._spin_style() + "QSpinBox { min-width: 42px; max-width: 52px; padding: 3px 18px 3px 6px; }")
        self.spin_persist.setToolTip(
            "Signal Persistence: tín hiệu trigger còn hiệu lực trong N nến cơ sở 1m (1 phút) sau khi xuất hiện\n"
            "(giúp khớp đa khung khi các trigger không cắt đúng cùng 1 nến). 1 = tức thời như cũ."
        )
        quick.addWidget(self.spin_persist)
        self.spin_persist.valueChanged.connect(lambda _: self._update_builder_title())

                                                                           
        quick.addWidget(self._mk_label("Trials:"))
        self.spin_trials = QSpinBox()
        self.spin_trials.setRange(7, 5000)
        self.spin_trials.setValue(100)
        self.spin_trials.setStyleSheet(self._spin_style() + "QSpinBox { min-width: 48px; max-width: 60px; padding: 3px 18px 3px 6px; }")
        quick.addWidget(self.spin_trials)

        quick.addStretch()

                                                                                    
        self.btn_run = QPushButton("▶ Tối ưu")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setStyleSheet(self._btn_style(Theme.ACCENT))
        self.btn_run.clicked.connect(self.run_builder)
        quick.addWidget(self.btn_run)

        self.btn_save = QPushButton("💾 Lưu")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(self._btn_style(Theme.ENTRY))
        self.btn_save.setToolTip("Lưu bộ tham số + kết quả hiện tại vào Thư viện (tab 'Đã lưu')")
        self.btn_save.clicked.connect(self._luu_ket_qua)
        quick.addWidget(self.btn_save)

                                                                               
        self.btn_load_last = QPushButton("↻ Mở lại")
        self.btn_load_last.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_last.setStyleSheet(self._btn_style(Theme.BORDER, text_color=Theme.TEXT_MAIN) + "QPushButton { padding: 7px 10px; }")
        self.btn_load_last.setToolTip("Nạp lại lần chạy tối ưu gần nhất vào builder (không tự nạp khi mở app).")
        self.btn_load_last.clicked.connect(self._nap_lan_chay_gan_nhat)
        quick.addWidget(self.btn_load_last)

        quick.addWidget(btn_clear)                          

        self.btn_stop = QPushButton("■ Dừng")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet(self._btn_style(Theme.LOSS))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_worker)
        quick.addWidget(self.btn_stop)

        lay.addLayout(quick)

                                                                        
        self.data_zone = DataDropZone()
        self.data_zone.setToolTip("Kéo 1 bộ dữ liệu (Symbol + khoảng ngày) vào đây để tối ưu trên dữ liệu đó. Để trống = dùng Symbol/ngày trong config.")
        self.data_zone.data_dropped.connect(self._on_data_drop)
        lay.addWidget(self.data_zone)
        self._render_data_zone()

                                                                 
        self.module_zone = ModuleDropZone()
        self.module_zone.setToolTip("Kéo các mô-đun (Regime ML / SL-TP động / Đòn bẩy động) vào khung này để bật và chỉnh thông số riêng.")
        self.module_zone.module_dropped.connect(self._on_module_drop)
        lay.addWidget(self.module_zone)

        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"background: {Theme.CARD_ALT}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        grid_lay = QHBoxLayout(grid_frame)
        grid_lay.setContentsMargins(8, 8, 8, 8)
        grid_lay.setSpacing(8)
        for tf in ALL_TIMEFRAMES:
            col = TimeframeColumn(tf)
            col.indicator_dropped.connect(self._on_drop)
            self.tf_columns[tf] = col
            grid_lay.addWidget(col, 1)
        lay.addWidget(grid_frame)

        self.lbl_strategy_desc = QLabel("Mỗi cột là 1 khung; đặt được nhiều chỉ báo, và cùng 1 chỉ báo có thể đặt ở nhiều khung. Chiến lược chỉ vào lệnh khi các chỉ báo đồng thuận — hệ thống tìm ngưỡng tối ưu RIÊNG cho từng chỉ báo/khung.")
        self.lbl_strategy_desc.setWordWrap(True)
        self.lbl_strategy_desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(self.lbl_strategy_desc)

                        
        self.combo_banner = QLabel("")
        self.combo_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.combo_banner.setFixedHeight(0)
        lay.addWidget(self.combo_banner)

        metrics_frame = QFrame()
        metrics_frame.setObjectName("card")
        metrics_frame.setStyleSheet(f"QFrame#card {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}")
        mlay = QVBoxLayout(metrics_frame)
        mlay.setContentsMargins(16, 12, 16, 12)
        mlay.setSpacing(10)
        mhead = QLabel("HIỆU SUẤT CHIẾN LƯỢC (IS / OOS)")
        mhead.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        mlay.addWidget(mhead)
        self.combo_metrics_grid = QGridLayout()
        self.combo_metrics_grid.setHorizontalSpacing(8)
        self.combo_metrics_grid.setVerticalSpacing(8)
        mlay.addLayout(self.combo_metrics_grid)
        lay.addWidget(metrics_frame)

                                                                    
        row_columns = QHBoxLayout()
        row_columns.setSpacing(10)
        row_columns.setContentsMargins(0, 0, 0, 0)

                                                                                
        guardrail_frame = QFrame()
        guardrail_frame.setObjectName("card")
        guardrail_frame.setStyleSheet(f"QFrame#card {{ background: transparent; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}")
        glay = QVBoxLayout(guardrail_frame)
        glay.setContentsMargins(16, 10, 16, 10)
        glay.setSpacing(4)
        ghead = QLabel("KIỂM ĐỊNH GUARDRAIL (điều kiện để DEPLOY)")
        ghead.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        glay.addWidget(ghead)
        self.combo_guardrail_box = QVBoxLayout()
        self.combo_guardrail_box.setSpacing(3)
        glay.addLayout(self.combo_guardrail_box)
        row_columns.addWidget(guardrail_frame, 1)

                                                                          
        wf_frame = QFrame()
        wf_frame.setObjectName("card")
        wf_frame.setStyleSheet(f"QFrame#card {{ background: transparent; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}")
        wlay = QVBoxLayout(wf_frame)
        wlay.setContentsMargins(16, 10, 16, 10)
        wlay.setSpacing(4)
        whead = QLabel("WALK-FORWARD OOS (độ bền 1 bộ tham số qua nhiều đoạn)")
        whead.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        wlay.addWidget(whead)
        self.combo_wf_box = QVBoxLayout()
        self.combo_wf_box.setSpacing(3)
        wlay.addLayout(self.combo_wf_box)
        row_columns.addWidget(wf_frame, 1)

        lay.addLayout(row_columns)

                                                                                         
        tbl_head = QLabel("THAM SỐ TỐI ƯU CHO TỪNG CHỈ BÁO (ở đúng khung của nó)")
        tbl_head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold;")
        lay.addWidget(tbl_head)
        self.combo_table = QTableWidget()
        cols = ["Chỉ báo", "Khung", "Loại", "Tham số chỉ báo", "Ngưỡng vào/thoát lệnh"]
        self.combo_table.setColumnCount(len(cols))
        self.combo_table.setHorizontalHeaderLabels(cols)
        self.combo_table.verticalHeader().setVisible(False)
        self.combo_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.combo_table.setWordWrap(True)                                              
        self.combo_table.setMinimumHeight(150)
        self.combo_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.combo_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.combo_table.setStyleSheet(f"""
            QTableWidget {{ background-color: {Theme.CARD}; color: {Theme.TEXT_MAIN}; gridline-color: {Theme.GRID}; border: 1px solid {Theme.BORDER}; border-radius: 8px; font-size: 12px; }}
            QHeaderView::section {{ background-color: {Theme.BG}; color: {Theme.TEXT_SUB}; font-weight: bold; padding: 8px 5px; border: 1px solid {Theme.BORDER}; border-top: none; }}
        """)
        self.combo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.combo_table)

                                                                                    
        self.bieu_do_phan_tich = BieuDoPhanTich(self)
        self.bieu_do_phan_tich.setMinimumHeight(430)
        lay.addWidget(self.bieu_do_phan_tich)

                                                                
        heatmap_frame = QFrame()
        heatmap_frame.setObjectName("card")
        heatmap_frame.setStyleSheet(f"QFrame#card {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}")
        hlay = QVBoxLayout(heatmap_frame)
        hlay.setContentsMargins(16, 10, 16, 10)
        hlay.setSpacing(6)

        h_header = QHBoxLayout()
        h_header.setSpacing(6)
        h_lbl = QLabel("BẢN ĐỒ NHIỆT (HEATMAP) ĐỘ NHẠY THAM SỐ")
        h_lbl.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        h_header.addWidget(h_lbl)
        h_header.addStretch()
        
        h_header.addWidget(self._mk_label("Trục X:"))
        self.cb_param_x = QComboBox()
        self.cb_param_x.setStyleSheet(self._combo_style() + "QComboBox { min-width: 100px; font-size: 11px; }")
        self.cb_param_x.currentIndexChanged.connect(self._ve_heatmap_do_nhay)
        h_header.addWidget(self.cb_param_x)
        
        h_header.addSpacing(8)
        
        h_header.addWidget(self._mk_label("Trục Y:"))
        self.cb_param_y = QComboBox()
        self.cb_param_y.setStyleSheet(self._combo_style() + "QComboBox { min-width: 100px; font-size: 11px; }")
        self.cb_param_y.currentIndexChanged.connect(self._ve_heatmap_do_nhay)
        h_header.addWidget(self.cb_param_y)
        
        hlay.addLayout(h_header)
        
                    
                                      
        self.heatmap_canvas = ParameterSensitivityScatterWidget(self)
        self.heatmap_canvas.setMinimumHeight(360)
        hlay.addWidget(self.heatmap_canvas)
        
        lay.addWidget(heatmap_frame)

                                                                          
        lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Theme.BG}; }}")
        scroll.setWidget(page)
        return scroll

    def _build_thu_vien_page(self):
        """Trang THƯ VIỆN: lưu & quản lý các bộ tham số đã nghiên cứu (nền tảng cho M4)."""
        page = QWidget()
        page.setStyleSheet(f"background: {Theme.BG};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(16)

                                                                                                     
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("Thư viện tham số đã nghiên cứu")
        title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 20px; background: transparent;")
        self.thu_vien_count = QLabel("Chưa có bộ tham số nào")
        self.thu_vien_count.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 12px; background: transparent;")
        title_box.addWidget(title)
        title_box.addWidget(self.thu_vien_count)
        lay.addLayout(title_box)

                                                                           
        self.thu_vien_scroll = QScrollArea()
        self.thu_vien_scroll.setWidgetResizable(True)
        self.thu_vien_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.thu_vien_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thu_vien_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thu_vien_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {Theme.BG}; border: none; }}
            QScrollBar:vertical {{ width: 9px; background: transparent; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {Theme.BORDER}; border-radius: 4px; min-height: 36px; }}
            QScrollBar::handle:vertical:hover {{ background: {Theme.TEXT_SUB}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

        self.thu_vien_container = QWidget()
        self.thu_vien_container.setStyleSheet(f"background: {Theme.BG};")
        self.thu_vien_flow = FlowLayout(self.thu_vien_container, margin=2, h_spacing=14, v_spacing=14)
        self.thu_vien_scroll.setWidget(self.thu_vien_container)
        lay.addWidget(self.thu_vien_scroll, 1)

        self._thu_vien_cards = []
        self._thu_vien_selected_card = None
        self._thu_vien_selected_ten = None
        return page

                                                                              
    def _thu_vien_chon_card(self, card):
        """Single click: chọn thẻ; bấm lại đúng thẻ đang chọn để bỏ chọn."""
        if card is self._thu_vien_selected_card:
            card.set_selected(False)
            self._thu_vien_selected_card = None
            self._thu_vien_selected_ten = None
            return
        if self._thu_vien_selected_card is not None:
            self._thu_vien_selected_card.set_selected(False)
        card.set_selected(True)
        self._thu_vien_selected_card = card
        self._thu_vien_selected_ten = card.ten

    def _thu_vien_mo_card(self, card):
        """Double click: chọn rồi mở vào builder."""
        if self._thu_vien_selected_card is not None and self._thu_vien_selected_card is not card:
            self._thu_vien_selected_card.set_selected(False)
        card.set_selected(True)
        self._thu_vien_selected_card = card
        self._thu_vien_selected_ten = card.ten
        self._mo_da_luu()

    def _thu_vien_menu(self, card, global_pos):
        """Chuột phải: Mở · Chạy ▶ (tiến trình riêng) · Đổi tên · Nhân bản · Xóa."""
        self._thu_vien_chon_card_force(card)
        css = (
            f"QMenu {{ background: {Theme.CARD}; color: {Theme.TEXT_MAIN};"
            f" border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {Theme.GRID}; }}"
            f"QMenu::separator {{ height: 1px; background: {Theme.BORDER}; margin: 4px 8px; }}"
        )
        menu = QMenu(self)
        menu.setStyleSheet(css)
        act_open = menu.addAction("Mở")

        run_menu = menu.addMenu("Chạy ▶")
        run_menu.setStyleSheet(css)
        run_acts = {}
        for khoa, nhan in CHAY_CHUC_NANG:
            run_acts[run_menu.addAction(f"▶  {nhan}")] = khoa

        menu.addSeparator()
        act_rename = menu.addAction("Đổi tên")
        act_dup = menu.addAction("Nhân bản")
        menu.addSeparator()
        act_del = menu.addAction("Xóa")

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is act_open:
            self._mo_da_luu()
        elif chosen in run_acts:
            self._chay_man_rieng(run_acts[chosen], card.ten)
        elif chosen is act_rename:
            self._doi_ten_da_luu(card.ten)
        elif chosen is act_dup:
            self._nhan_ban_da_luu(card.ten)
        elif chosen is act_del:
            self._xoa_da_luu()

    def _chay_man_rieng(self, khoa, ten):
        """Mở 1 màn vận hành cho chiến lược `ten` trong TIẾN TRÌNH RIÊNG (subprocess).

        Process tách hẳn app chính (DETACHED) → đóng app chính thì cửa sổ này vẫn chạy.
        Ưu tiên pythonw.exe để không kèm cửa sổ console.
        """
        import subprocess
                                                                                        
        ovr = self._hoi_thiet_lap_chay(khoa, ten)
        if ovr is None:
            return                      
        cmd = [sys.executable, "-m", "hien_thi.app.chay_man", "--man", khoa]
        if ten:
            cmd += ["--chien-luoc", ten]
                                                                                             
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
                                                                                     
        if ovr.get("symbols"):
            import json as _json
            env["KAIROS_RUN_SYMBOLS"] = _json.dumps(ovr["symbols"])
        if ovr.get("tu_ngay"):
            env["KAIROS_RUN_TU_NGAY"] = ovr["tu_ngay"]
        if ovr.get("den_ngay"):
            env["KAIROS_RUN_DEN_NGAY"] = ovr["den_ngay"]
                                                                                                
        kwargs = {
            "cwd": PROJECT_ROOT,
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            kwargs["start_new_session"] = True
        nhan = dict(CHAY_CHUC_NANG).get(khoa, khoa)
        try:
            subprocess.Popen(cmd, **kwargs)
            self.lbl_status.setText(f"▶ Đã mở {nhan} (tiến trình riêng) cho: {ten}")
        except Exception as e:                
            self.lbl_status.setText(f"✗ Không mở được {nhan}: {e}")

    def _hoi_thiet_lap_chay(self, khoa, ten):
        """Hiện dialog chọn symbols (+ ngày) cho lần chạy. Trả dict override, hoặc None nếu Hủy.

        Mặc định điền theo bộ dữ liệu đã lưu kèm chiến lược; universe = danh sách coin cấu hình.
        Universe rỗng → trả {} (không có gì để chọn) → chạy như cũ, không override.
        """
        from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
        universe = (lay_cau_hinh_giao_dich() or {}).get("cap_giao_dich", []) or []
        if not universe:
            return {}

                                                                                                 
        default_symbols, default_tu, default_den = None, None, None
        try:
            from toi_uu_hoa.thu_vien import doc_chien_luoc
            payload = doc_chien_luoc(ten) or {}
            ds = payload.get("dataset") or {}
            if isinstance(ds, dict):
                default_symbols = ds.get("symbols")
                default_tu = ds.get("tu_ngay")
                default_den = ds.get("den_ngay")
        except Exception:                
            pass
        if not default_tu or not default_den:
            cfg_ao = lay_cau_hinh_ao() or {}
            default_tu = default_tu or cfg_ao.get("ngay_bat_dau")
            default_den = default_den or cfg_ao.get("ngay_ket_thuc")

        from hien_thi.man_hinh.toi_uu.thiet_lap_chay import ThietLapChayDialog
        from PyQt6.QtWidgets import QDialog
        nhan = dict(CHAY_CHUC_NANG).get(khoa, khoa)
        dlg = ThietLapChayDialog(
            khoa, nhan, universe,
            default_symbols=default_symbols, default_tu=default_tu, default_den=default_den,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.lay_ket_qua()

    def _thu_vien_chon_card_force(self, card):
        """Đảm bảo `card` là thẻ đang chọn (dùng trước khi mở context menu)."""
        if card is self._thu_vien_selected_card:
            return
        if self._thu_vien_selected_card is not None:
            self._thu_vien_selected_card.set_selected(False)
        card.set_selected(True)
        self._thu_vien_selected_card = card
        self._thu_vien_selected_ten = card.ten

    def _doi_ten_da_luu(self, ten):
        cur = ten.split("__")[0]
        ten_moi, ok = QInputDialog.getText(self, "Đổi tên", "Tên mới:", text=cur)
        if not ok or not ten_moi.strip():
            return
        from toi_uu_hoa.thu_vien import doi_ten_chien_luoc
        moi = doi_ten_chien_luoc(ten, ten_moi.strip())
        self._thu_vien_selected_ten = moi
        self._thu_vien_selected_card = None
        self._nap_thu_vien()
        self.lbl_status.setText(f"Đã đổi tên: {moi}" if moi else "✗ Đổi tên thất bại.")

    def _nhan_ban_da_luu(self, ten):
        from toi_uu_hoa.thu_vien import nhan_ban_chien_luoc
        moi = nhan_ban_chien_luoc(ten)
        self._thu_vien_selected_card = None
        self._thu_vien_selected_ten = None
        self._nap_thu_vien()
        self.lbl_status.setText(f"Đã nhân bản → {moi}" if moi else "✗ Nhân bản thất bại.")

    def _ten_da_chon(self):
        if not self._thu_vien_selected_ten:
            self.lbl_status.setText("Chọn một thẻ trong thư viện trước.")
            return None
        return self._thu_vien_selected_ten

    def _nap_thu_vien(self):
        if not hasattr(self, "thu_vien_flow"):
            return
        from toi_uu_hoa.thu_vien import danh_sach_da_luu
        ds = danh_sach_da_luu()

                                        
        while self.thu_vien_flow.count():
            item = self.thu_vien_flow.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._thu_vien_cards = []

                                                       
        ten_chon = self._thu_vien_selected_ten
        self._thu_vien_selected_card = None

        if hasattr(self, "thu_vien_count"):
            n = len(ds)
            self.thu_vien_count.setText(f"{n:,} bộ tham số đã lưu" if n else "Chưa có bộ tham số nào")

        if not ds:
            self._thu_vien_selected_ten = None
            empty = QLabel("Chưa có chiến lược nào được lưu — chạy “Tối ưu” rồi bấm 💾 Lưu để thêm vào thư viện.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 13px; background: transparent; padding: 60px 20px;")
            empty.setFixedWidth(max(420, self.thu_vien_scroll.viewport().width() - 20))
            self.thu_vien_flow.addWidget(empty)
            return

        for s in ds:
            card = StrategyCard(s)
            card.clicked.connect(self._thu_vien_chon_card)
            card.doubleClicked.connect(self._thu_vien_mo_card)
            card.menuRequested.connect(self._thu_vien_menu)
            self.thu_vien_flow.addWidget(card)
            self._thu_vien_cards.append(card)
            if ten_chon is not None and s["ten"] == ten_chon:
                card.set_selected(True)
                self._thu_vien_selected_card = card

        if self._thu_vien_selected_card is None:
            self._thu_vien_selected_ten = None

    def _luu_ket_qua(self):
        if not getattr(self, "combo_result", None):
            self.lbl_status.setText("⚠ Chưa có kết quả để lưu — chạy “▶ Tối ưu” trước.")
            return
        try:
            from toi_uu_hoa.thu_vien import luu_chien_luoc
            ten = luu_chien_luoc(self.combo_result)
        except Exception as e:                
            self.lbl_status.setText(f"✗ Lưu thất bại: {e}")
            return
        self._nap_thu_vien()
        self.lbl_status.setText(f"✓ Đã lưu vào thư viện: {ten}")
        
                                           
        self.btn_save.setText("✔️ Đã lưu")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_save.setText("💾 Lưu"))

    def _mo_da_luu(self):
        ten = self._ten_da_chon()
        if not ten:
            return
        from toi_uu_hoa.thu_vien import doc_chien_luoc
        result = (doc_chien_luoc(ten) or {}).get("result") or {}
        if not result:
            self.lbl_status.setText(f"✗ Không đọc được: {ten}")
            return
        self.combo_specs = [{"key": c["key"], "tf": c["tf"], "role": c.get("role", "trigger")} for c in result.get("combo", [])]
        self.combo_result = result
        self.combo_result_specs = list(self.combo_specs)
        self._dat_logic_ui(result)
        self._render_grid()
        self._update_builder_title()
        self._render_combo_result(result)
        self._switch_page(0)
        self.lbl_status.setText(f"Đã mở từ thư viện: {ten}")
        self._xuat_ban_chien_luoc(result)

    def _dat_logic_ui(self, result):
        """Khôi phục dropdown Logic + ô Giữ-nến theo kết quả đã lưu/nạp."""
        if not hasattr(self, "combo_logic"):
            return
        logic_val = result.get("logic")
        if isinstance(logic_val, dict):
            lg = str(logic_val.get("mode") or "and").lower()
            persistence = logic_val.get("persistence", 1)
        else:
            lg = str(logic_val or "and").lower()
            persistence = result.get("persistence", 1)
        self.combo_logic.setCurrentIndex(1 if lg == "or" else 0)
        try:
            self.spin_persist.setValue(max(1, int(persistence)))
        except (TypeError, ValueError):
            self.spin_persist.setValue(1)

    def _xoa_da_luu(self):
        ten = self._ten_da_chon()
        if not ten:
            return
        from toi_uu_hoa.thu_vien import xoa_chien_luoc
        xoa_chien_luoc(ten)
        self._nap_thu_vien()
        self.lbl_status.setText(f"Đã xóa: {ten}")

    def _build_statusbar(self, parent_layout):
        bar = QFrame()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background: {Theme.CARD}; border-top: 1px solid {Theme.BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        self.lbl_status = QLabel("Sẵn sàng.")
        self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(self.lbl_status)
        lay.addStretch()

                                                                                      
        self.btn_gui_bieu_do = QPushButton("Gửi sang Biểu đồ nến →")
        self.btn_gui_bieu_do.setStyleSheet(self._btn_style(Theme.ACCENT) + "QPushButton { padding: 3px 12px; font-size: 11px; }")
        self.btn_gui_bieu_do.setEnabled(False)
        self.btn_gui_bieu_do.clicked.connect(self._gui_sang_bieu_do)
        lay.addWidget(self.btn_gui_bieu_do)
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(190, 14)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {Theme.GRID}; border: 1px solid {Theme.BORDER}; border-radius: 7px; }}"
            f"QProgressBar::chunk {{ background: {Theme.ACCENT}; border-radius: 6px; }}"
        )
        lay.addWidget(self.progress_bar)
        parent_layout.addWidget(bar)

                                                                                
    def _xuat_ban_chien_luoc(self, result):
        """Đẩy chiến lược (+ dataset) đang xem lên bus phiên để các tab khác đồng bộ.

        Dataset cập nhật LẶNG (im_lang) rồi mới phát strategy → bên nhận chỉ kích hoạt
        1 lần và đọc được cả 2. Bật nút 'Gửi sang Biểu đồ nến' khi đã có kết quả.
        """
        co_kq = bool(result)
        if hasattr(self, "btn_gui_bieu_do"):
            self.btn_gui_bieu_do.setEnabled(co_kq)
        phien = getattr(self, "phien", None)
        if phien is None or not co_kq:
            return
        phien.set_active_dataset(self.active_dataset, im_lang=True)
        phien.set_active_strategy(result)

    def _gui_sang_bieu_do(self):
        """Nút 'Gửi sang Biểu đồ nến': xuất bản kết quả hiện tại rồi chuyển sang tab nến."""
        result = self.combo_result
        if not result:
            self.lbl_status.setText("⚠ Chưa có kết quả để gửi. Hãy chạy tối ưu hoặc nạp từ thư viện trước.")
            return
        self._xuat_ban_chien_luoc(result)
        phien = getattr(self, "phien", None)
        if phien is not None:
            phien.yeu_cau_xem("vectorized")                                     
        self.lbl_status.setText("✓ Đã gửi chiến lược sang Biểu đồ nến.")

                                                                              
    def _mk_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent;")
        return lbl

    def _combo_style(self):
        return (
            f"QComboBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 24px 4px 8px; min-width: 150px; }}"
            f"QComboBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
            f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border-left: none; background: transparent; }}"
            f"QComboBox QAbstractItemView {{ background: {Theme.CARD}; color: {Theme.TEXT_MAIN}; selection-background-color: {Theme.GRID}; border: 1px solid {Theme.BORDER}; border-radius: 4px; }}"
        )

    def _spin_style(self):
        return (
            f"QSpinBox {{ background-color: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 20px 4px 8px; min-width: 70px; max-width: 80px; }}"
            f"QSpinBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
            f"QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 16px; border-left: none; border-bottom: none; background: transparent; border-top-right-radius: 4px; }}"
            f"QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 16px; border-left: none; border-top: none; background: transparent; border-bottom-right-radius: 4px; }}"
            f"QSpinBox::up-button:hover {{ background: {Theme.GRID}; }}"
            f"QSpinBox::down-button:hover {{ background: {Theme.GRID}; }}"
            f"QSpinBox::up-arrow {{ image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-bottom: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QSpinBox::down-arrow {{ image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QSpinBox::up-arrow:hover {{ border-bottom-color: {Theme.TEXT_MAIN}; }}"
            f"QSpinBox::down-arrow:hover {{ border-top-color: {Theme.TEXT_MAIN}; }}"
        )

    def _btn_style(self, bg, text_color="#FFFFFF"):
        return (
            f"QPushButton {{ background-color: {bg}; color: {text_color}; font-weight: bold; padding: 7px 14px; border-radius: 5px; border: none; }}"
            f"QPushButton:disabled {{ background-color: {Theme.GRID}; color: {Theme.TEXT_SUB}; }}"
        )

                                                                              
    def _filter_indicators(self, text):
        text = text.strip().lower()
        for cat_lbl, keys in self.category_headers:
            visible = 0
            for key in keys:
                item = self.indicator_items[key]
                match = text in key.lower() or text in INDICATOR_DESC.get(key, "").lower()
                item.setVisible(match)
                visible += int(match)
            cat_lbl.setVisible(visible > 0)

    def _select_quick(self, key):
        if getattr(self, "_selected_indicator_key", None) == key:
            self._selected_indicator_key = None
            for it in self.indicator_items.values():
                it.set_selected(False)
        else:
            self._selected_indicator_key = key
            for k, it in self.indicator_items.items():
                it.set_selected(k == key)

                                                                              
    def _on_drop(self, tf, key_or_mime):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi sửa chiến lược.")
            return
        if key_or_mime.startswith("module:") or key_or_mime.startswith("data:"):
            self.lbl_status.setText("⚠ Mô-đun/bộ dữ liệu không thả vào lưới khung thời gian. Hãy thả vào đúng khu vực của nó.")
            return
        if key_or_mime.startswith("move:"):
            parts = key_or_mime.split(":")
            if len(parts) >= 3:
                idx = int(parts[1])
                if 0 <= idx < len(self.combo_specs):
                    self.combo_specs[idx]["tf"] = tf
                    self.combo_result = None
                    self._set_combo_metrics_placeholder()
                    self._render_grid()
                    self._update_builder_title()
                    return
        else:
            self.combo_specs.append({"key": key_or_mime, "tf": tf, "role": "trigger"})
            self.combo_result = None
            self._set_combo_metrics_placeholder()
            self._render_grid()
            self._update_builder_title()

    def _toggle_role(self, idx):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi sửa chiến lược.")
            return
        if 0 <= idx < len(self.combo_specs):
            cur = self.combo_specs[idx].get("role", "trigger")
            self.combo_specs[idx]["role"] = "filter" if cur == "trigger" else "trigger"
            self.combo_result = None
            self._set_combo_metrics_placeholder()
            self._render_grid()
            self._update_builder_title()

    def _remove_chip(self, idx):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi sửa chiến lược.")
            return
        if 0 <= idx < len(self.combo_specs):
            del self.combo_specs[idx]
            self.combo_result = None
            self._set_combo_metrics_placeholder()
            self._render_grid()
            self._update_builder_title()

    def _clear_combo(self):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi sửa chiến lược.")
            return
        self.combo_specs = []
        self.combo_result = None
        self._set_combo_metrics_placeholder()
        self._render_grid()
        self._update_builder_title()

    def _render_grid(self):
        by_tf = {tf: [] for tf in ALL_TIMEFRAMES}
        for i, spec in enumerate(self.combo_specs):
            by_tf.setdefault(spec["tf"], []).append((i, spec))
        for tf, col in self.tf_columns.items():
            chips = [self._make_grid_chip(i, spec) for i, spec in by_tf.get(tf, [])]
            col.set_chips(chips)

    def _make_grid_chip(self, i, spec):
        return GridChip(i, spec, self)

    def _chip_params_text(self, i):
        if not self.combo_result or self.combo_specs != self.combo_result_specs:
            return ""
        spec = (self.combo_result.get("best_params", {}) or {}).get(f"s{i}")
        if not spec:
            return ""
        parts = [f"{k}={v}" for k, v in (spec.get("params") or {}).items()]
        parts += [f"{k}={v}" for k, v in (spec.get("thresholds") or {}).items()]
        return " · ".join(parts)

    def _update_builder_title(self):
        if not self.combo_specs:
            self.lbl_builder_title.setText("Kéo chỉ báo từ trái thả vào cột khung thời gian → bấm “▶ Tối ưu”")
            if hasattr(self, "lbl_strategy_desc"):
                self.lbl_strategy_desc.setText(
                    "Mỗi cột là 1 khung; đặt được nhiều chỉ báo, và cùng 1 chỉ báo có thể đặt ở nhiều khung. "
                    "Chiến lược chỉ vào lệnh khi các chỉ báo đồng thuận — hệ thống tìm ngưỡng tối ưu RIÊNG cho từng chỉ báo/khung."
                )
                self.lbl_strategy_desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
            return
            
        short_label = " + ".join(f"{s['key']}@{s['tf']}" for s in self.combo_specs)
        self.lbl_builder_title.setText(f"CHIẾN LƯỢC TỔ HỢP: {short_label}")
        
                                          
        logic = self.combo_logic.currentData() or "and"
        persistence = self.spin_persist.value()
        
        triggers = [s for s in self.combo_specs if s.get("role", "trigger") == "trigger"]
        filters = [s for s in self.combo_specs if s.get("role", "trigger") == "filter"]
        
        parts = []
        if triggers:
            trigger_descs = []
            for s in triggers:
                key_upper = s["key"].upper()
                tf_val = s["tf"]
                trigger_descs.append(f"giá chạm tới ngưỡng {key_upper} ở Khung {tf_val}")
            
                                            
            conj = " và " if logic == "and" else " hoặc "
            trigger_phrase = conj.join(trigger_descs)
            if len(triggers) > 1:
                trigger_phrase = f"({trigger_phrase})"
            parts.append(f"vào lệnh khi {trigger_phrase}")
        else:
            parts.append("vào lệnh khi có tín hiệu trigger")
            
        if filters:
            filter_descs = []
            for s in filters:
                key_upper = s["key"].upper()
                tf_val = s["tf"]
                filter_descs.append(f"{key_upper} ở Khung {tf_val}")
            filter_phrase = " và ".join(filter_descs)
            parts.append(f"ĐỒNG THỜI thỏa mãn điều kiện lọc của {filter_phrase}")
            
        if persistence > 1:
            parts.append(f"(hiệu lực tín hiệu giữ trong {persistence} nến 1m ~ {persistence} phút)")
            
        explanation = ", ".join(parts)
        
        if explanation:
            explanation = explanation[0].upper() + explanation[1:]
            
        if hasattr(self, "lbl_strategy_desc"):
            self.lbl_strategy_desc.setText(f"💡 Giải thích chiến lược: {explanation}")
            self.lbl_strategy_desc.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 11px; font-weight: bold;")

                                                                               
    def _default_module_params(self, mid):
        p = dict(DEFAULT_MODULE_PARAMS.get(mid, {}))
        if mid == "don_bay":
            try:
                import chien_luoc.quan_ly_chien_luoc_vectorized as Q
                p["goc"] = int(getattr(Q, "DON_BAY_CO_DINH", p.get("goc", 5)))
            except Exception:
                pass
        elif mid == "regime":
            try:
                from chien_luoc.optimizer import trang_thai_thi_truong as TTT
                cam = set(getattr(TTT, "_REGIME_KHONG_TRADE", {0, 7}))
                p["allowed"] = sorted(TTT.TAT_CA_REGIME - cam)
            except Exception:
                pass
        return p

    def _on_module_drop(self, mime):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi đổi mô-đun.")
            return
        if not mime.startswith("module:"):
            return
        mid = mime.split(":", 1)[1]
        if mid not in MODULE_DEFS or mid in self.active_modules:
            return
        self.active_modules[mid] = self._default_module_params(mid)
        self._apply_module_flag(mid, True)
        self._apply_module_params_to_Q(mid)
        self._render_modules()

    def _remove_module(self, mid):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng dừng hoặc chờ tối ưu xong trước khi đổi mô-đun.")
            return
        if mid in self.active_modules:
            del self.active_modules[mid]
            self._apply_module_flag(mid, False)
            if mid == "sl_tp":
                try:
                    import chien_luoc.quan_ly_chien_luoc_vectorized as Q
                    Q.SL_TP_TIME_FRAME = None
                    Q.SL_RANGE = (1.0, 5.0)
                    Q.RR_RANGE = (1.2, 4.0)
                except Exception:
                    pass
            if mid == "regime":
                try:
                    from chien_luoc.optimizer import trang_thai_thi_truong as TTT
                    TTT.dat_regime_cho_phep(None)
                except Exception:
                    pass
            self._render_modules()

    def _set_module_param(self, mid, key, value):
        if mid in self.active_modules:
            self.active_modules[mid][key] = value
            self._apply_module_params_to_Q(mid)

    def _apply_module_flag(self, mid, on):
        flag = MODULE_DEFS[mid]["flag"]
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
            setattr(Q, flag, bool(on))
        except Exception as e:                
            self.lbl_status.setText(f"✗ Không đặt được mô-đun {mid}: {e}")
            return
        self.lbl_status.setText(f"{MODULE_DEFS[mid]['name']}: {'BẬT' if on else 'TẮT'} (dùng chung optimizer + backtest danh mục)")

    def _apply_module_params_to_Q(self, mid):
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        except Exception:
            return
        p = self.active_modules.get(mid, {})
        if mid == "sl_tp":
            tf = p.get("tf", "Tự động")
            Q.SL_TP_TIME_FRAME = None if tf in (None, "", "Tự động") else tf
            Q.SL_RANGE = (float(p.get("sl_min", 1.0)), float(p.get("sl_max", 5.0)))
            Q.RR_RANGE = (float(p.get("rr_min", 1.2)), float(p.get("rr_max", 4.0)))
        elif mid == "don_bay":
            Q.DON_BAY_GOC = int(p.get("goc", getattr(Q, "DON_BAY_CO_DINH", 5)))
            Q.MAX_LEVERAGE = int(p.get("max_lev", 50))
            Q.DON_BAY_TF = p.get("tf", "15m") or "15m"
        elif mid == "regime":
            allowed = p.get("allowed", REGIME_ALLOWED_DEFAULT)
            try:
                from chien_luoc.optimizer import trang_thai_thi_truong as TTT
                TTT.dat_regime_cho_phep(allowed)
            except Exception:
                pass

    def _render_modules(self):
        if self.module_zone is None:
            return
        chips = [ModuleChip(mid, self) for mid in MODULE_DEFS if mid in self.active_modules]
        self.module_zone.set_chips(chips)

    def _sync_module_flags_to_Q(self):
        """Ép toàn bộ cờ Q.* khớp ĐÚNG active_modules (UI = nguồn sự thật duy nhất).

        Cờ module (DUNG_REGIME_MAC_DINH, DUNG_SL_TP_DONG, DUNG_DON_BAY_DONG) là global
        trong RAM, dính suốt phiên app → có thể "rò" sang lần chạy sau dù không còn chip.
        Gọi trước mỗi lần tối ưu: có chip = BẬT (+áp params); không chip = TẮT (+reset).
        Nhờ vậy regime ML CHỈ chạy khi thực sự có chip Regime trên UI.
        """
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        except Exception:
            return
        for mid, d in MODULE_DEFS.items():
            on = mid in self.active_modules
            setattr(Q, d["flag"], on)
            if on:
                self._apply_module_params_to_Q(mid)
            elif mid == "sl_tp":
                Q.SL_TP_TIME_FRAME = None
                Q.SL_RANGE = (1.0, 5.0)
                Q.RR_RANGE = (1.2, 4.0)
            elif mid == "regime":
                try:
                    from chien_luoc.optimizer import trang_thai_thi_truong as TTT
                    TTT.dat_regime_cho_phep(None)
                except Exception:
                    pass

    def _init_modules_from_Q(self):
        """Mở màn Tối ưu = state mô-đun SẠCH. KHÔNG kế thừa cờ Q global dính lại từ
        lần dùng trước (vd regime ML từng kéo rồi điều hướng đi). Module là OPT-IN qua
        kéo-thả: chưa kéo chip nào → không module nào bật, cờ Q ép về mặc định TẮT.
        """
        self.active_modules = {}
        self._sync_module_flags_to_Q()

                                                                              
    def run_builder(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self._sync_module_flags_to_Q()                                                      
        seen, specs = set(), []
        for s in self.combo_specs:
            k = (s["key"], s["tf"])
            if k not in seen:
                seen.add(k)
                specs.append(s)
        if not specs:
            self.lbl_status.setText("⚠ Hãy kéo ít nhất 1 chỉ báo vào lưới khung thời gian.")
            return
        if not any(s.get("role", "trigger") == "trigger" for s in specs):
            self.lbl_status.setText("⚠ Cần ít nhất 1 chỉ báo vai trò Trigger (Filter chỉ để lọc). Bấm badge để đổi.")
            return

                                                                                  
                                                                            
        from toi_uu_hoa.bo_dieu_phoi import TINH_NANG_NANG_CAP
        if len(specs) > 1 and not TINH_NANG_NANG_CAP:
            hien_thong_bao(
                self, "Tính năng nâng cấp",
                "Tối ưu Tổ hợp nhiều chỉ báo (≥2) thuộc bản nâng cấp, không mở cho cộng đồng.\n\n"
                "Vui lòng liên hệ tác giả để được cấp quyền sử dụng.",
                loai="nang_cap",
            )
            return

        self._switch_page(0)
        self._set_combo_metrics_placeholder()
        self.combo_table.setRowCount(0)
        self.combo_banner.setText("")
        self.combo_banner.setFixedHeight(0)
        self._set_running_ui(True)
        self._progress_busy()
        logic = self.combo_logic.currentData()
        persistence = self.spin_persist.value()
        label = " + ".join(f"{s['key']}@{s['tf']}" for s in specs)
        ds_txt = f" · dữ liệu: {self.active_dataset['ten']}" if self.active_dataset else ""
        self.lbl_status.setText(f"Đang tối ưu chiến lược ({logic.upper()}, giữ {persistence} nến 1m){ds_txt}: {label}")
        self.worker = ComboWorker(specs, self.spin_trials.value(), self.combo_objective.currentData(),
                                  logic=logic, persistence=persistence, dataset=self.active_dataset)
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.trial_progress.connect(self._on_trial_progress)
        self.worker.finished_combo.connect(self._on_combo_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_combo_finished(self, result):
        self.combo_result = result
        self.combo_result_specs = list(self.combo_specs)
        self._set_running_ui(False)
        self._render_combo_result(result)
        self._render_grid()
        oos = result.get("oos_metrics", {}) or {}
        sharpe_txt = "—" if _safe_float(oos.get("total_trades")) <= 0 else f"{_safe_float(oos.get('sharpe_ratio')):+.3f}"
        self.lbl_status.setText(f"✓ Hoàn tất · {ket_luan_chien_luoc(result)} · OOS Sharpe {sharpe_txt}")

        self._xuat_ban_chien_luoc(result)

                                                                                
    def _nap_lai_plugin(self):
        from toi_uu_hoa.dang_ky_chien_luoc import nap_plugins, danh_sach_plugins
        nap_plugins()
        while self.plugin_list_layout.count():
            it = self.plugin_list_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        self._plugin_items = {}
        ds = danh_sach_plugins()
        if not ds:
            empty = QLabel("Chưa có plugin.\nThả file .py kế thừa\nChienLuocPluginCoSo vào\nchien_luoc/user_strategies/")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; padding: 12px 8px;")
            self.plugin_list_layout.addWidget(empty)
            self.btn_run_plugin.setEnabled(False)
        else:
            for p in ds:
                item = PluginItem(p["khoa"], p["ten"], p["mo_ta"])
                item.clicked.connect(self._chon_plugin)
                self._plugin_items[p["khoa"]] = item
                self.plugin_list_layout.addWidget(item)
            self.btn_run_plugin.setEnabled(True)
        self.plugin_list_layout.addStretch()
        if self._selected_plugin_key in self._plugin_items:
            self._chon_plugin(self._selected_plugin_key)
        else:
            self._selected_plugin_key = None

    def _chon_plugin(self, khoa):
        if self._selected_plugin_key == khoa:
            self._selected_plugin_key = None
            for item in self._plugin_items.values():
                item.set_selected(False)
        else:
            self._selected_plugin_key = khoa
            for k, item in self._plugin_items.items():
                item.set_selected(k == khoa)

    def run_plugin(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self._sync_module_flags_to_Q()                                             
        khoa = self._selected_plugin_key
        if not khoa:
            self.lbl_status.setText("⚠ Chưa chọn plugin (thêm file vào chien_luoc/user_strategies/).")
            return
        self._switch_page(0)
        self._set_combo_metrics_placeholder()
        self.combo_table.setRowCount(0)
        self.combo_banner.setText("")
        self.combo_banner.setFixedHeight(0)
        self._set_running_ui(True)
        self._progress_busy()
        ten = self._plugin_items[khoa].lbl_ten.text() if khoa in self._plugin_items else khoa
        self.lbl_status.setText(f"Đang tối ưu plugin: {ten}")
        self.worker = StrategyWorker(khoa, self.spin_trials.value(), self.combo_objective.currentData())
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.trial_progress.connect(self._on_trial_progress)
        self.worker.finished_combo.connect(self._on_plugin_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_plugin_finished(self, result):
        self.combo_result = result
        self.combo_result_specs = None
        self._set_running_ui(False)
        self._render_combo_result(result)
        oos = result.get("oos_metrics", {}) or {}
        sharpe_txt = "—" if _safe_float(oos.get("total_trades")) <= 0 else f"{_safe_float(oos.get('sharpe_ratio')):+.3f}"
        self.lbl_status.setText(f"✓ Hoàn tất plugin · {ket_luan_chien_luoc(result)} · OOS Sharpe {sharpe_txt}")
        self._xuat_ban_chien_luoc(result)

                                                                              
    def stop_worker(self):
        if self.worker is not None and self.worker.isRunning():
            if hasattr(self.worker, "stop"):
                self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⏳ Đang dừng...")
            self.lbl_status.setText("Đang dừng — kết thúc sau bộ hiện tại rồi chốt kết quả tốt nhất hiện có...")

    def _on_worker_failed(self, msg):
        self._set_running_ui(False)
        self.lbl_status.setText(f"✗ Lỗi: {msg}")
        hien_thong_bao(self, "Lỗi khi chạy", str(msg), loai="error")

    def _set_running_ui(self, running):
        self.btn_run.setEnabled(not running)
        self.btn_save.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.spin_trials.setEnabled(not running)
        if hasattr(self, "combo_logic"):
            self.combo_logic.setEnabled(not running)
        if hasattr(self, "spin_persist"):
            self.spin_persist.setEnabled(not running)
        if hasattr(self, "btn_run_plugin"):
            self.btn_run_plugin.setEnabled(not running)
        if not running:
            self.lbl_progress.setText("")
            self._progress_reset()

        self.btn_stop.setText("■ Dừng")
        if running:
            self.btn_run.setText("⏳ Đang tối ưu...")
            if hasattr(self, "btn_run_plugin"):
                self.btn_run_plugin.setText("⏳ Đang tối ưu...")
        else:
            self.btn_run.setText("▶ Tối ưu")
            if hasattr(self, "btn_run_plugin"):
                self.btn_run_plugin.setText("▶ Tối ưu plugin")

                                                                              
    def _progress_busy(self):
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
                                                                          
        self.lbl_progress.setText("⏳ Đang nạp dữ liệu & chuẩn bị...")

    def _progress_set(self, done, total):
        total = max(int(total), 1)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(min(int(done), total))
        self.progress_bar.setVisible(True)

    def _progress_reset(self):
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

    def _on_trial_progress(self, done, total, best):
        self._progress_set(done, total)
        best_txt = "" if best is None else f" · best IS {float(best):+.2f}"
        self.lbl_progress.setText(f"Bộ {done}/{total}{best_txt}")
                                                                               
        nut = self.btn_run_plugin if isinstance(self.worker, StrategyWorker) else self.btn_run
        nut.setText(f"⏳ Bộ {done}/{total}")

                                                                              
    def _clear_grid(self, grid):
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_combo_metrics_placeholder(self):
        self._clear_grid(self.combo_metrics_grid)
        hint = QLabel("Chưa có kết quả — dựng chiến lược rồi bấm “▶ Tối ưu”.")
        hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        self.combo_metrics_grid.addWidget(hint, 0, 0)
        self.combo_banner.setText("")
        self.combo_banner.setFixedHeight(0)
        self._clear_grid(self.combo_guardrail_box)
        self._clear_grid(self.combo_wf_box)
        self.combo_table.setRowCount(0)
        if hasattr(self, "cb_param_x"):
            self._cap_nhat_heatmap_controls(None)
        if hasattr(self, "bieu_do_phan_tich"):
            self.bieu_do_phan_tich.update_data(None)

    def _render_combo_result(self, result):
        conclusion = ket_luan_chien_luoc(result)
        color, txt = self._conclusion_style(conclusion)
        self.combo_banner.setText(f"{result.get('combo_label', '')} · {txt}")
        self.combo_banner.setFixedHeight(26)
        self.combo_banner.setStyleSheet(f"background: {color}; color: #FFFFFF; font-weight: bold; font-size: 11px; border-radius: 4px;")

        self._cap_nhat_heatmap_controls(result.get("trials_data"))

        if hasattr(self, "bieu_do_phan_tich"):
            self.bieu_do_phan_tich.update_data(result.get("phan_tich"))

        self._clear_grid(self.combo_metrics_grid)
        NCOL = 5
        for n, (k, v, c) in enumerate(self._format_metrics(result)):
            self.combo_metrics_grid.addWidget(self._metric_cell(k, v, c), n // NCOL, n % NCOL)
        for col in range(NCOL):
            self.combo_metrics_grid.setColumnStretch(col, 1)

        self._clear_grid(self.combo_guardrail_box)
        for _w in (result.get("canh_bao") or []):
            wl = QLabel(f"⚠ {_w}")
            wl.setWordWrap(True)
            wl.setStyleSheet(f"color: {Theme.NEUTRAL}; font-size: 11px; font-weight: bold;")
            self.combo_guardrail_box.addWidget(wl)
        audit = danh_gia_guardrails(result)
        for c in audit["checks"]:
            ok = c["dat"]
            row = QLabel(f"{'✓' if ok else '✗'}  {c['ten']}   —   {c['hien_thi']}")
            row.setStyleSheet(f"color: {Theme.WIN if ok else Theme.LOSS}; font-size: 12px;")
            self.combo_guardrail_box.addWidget(row)

        self._clear_grid(self.combo_wf_box)
        folds = result.get("oos_folds") or []
        wf = result.get("wf_summary") or {}
        if folds:
            head = QLabel(
                f"{wf.get('so_doan_co_du_lieu', 0)}/{wf.get('so_doan', len(folds))} đoạn có dữ liệu  ·  "
                f"% đoạn dương: {_safe_float(wf.get('ty_le_doan_duong')) * 100:.0f}%  ·  "
                f"Sharpe TB: {wf.get('sharpe_trung_binh')}"
            )
            head.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 12px; font-weight: bold;")
            self.combo_wf_box.addWidget(head)
            for f in folds:
                sh = _safe_float(f.get("sharpe_ratio"))
                n_tr = int(_safe_float(f.get("total_trades")))
                no_data = sh <= -9.99
                if n_tr == 0:
                    txt = "— (không có tín hiệu khớp)"
                elif no_data:
                    txt = f"— (dưới {MIN_TRADES_OOS} lệnh hoặc < {MIN_DAYS_TIN_CAY} ngày)"
                else:
                    txt = f"{sh:+.2f}"
                color = Theme.TEXT_SUB if no_data else (Theme.WIN if sh > 0 else Theme.LOSS)
                row = QLabel(f"{f.get('ky', '')}    Sharpe {txt}  ·  {n_tr} lệnh")
                row.setStyleSheet(f"color: {color}; font-size: 11px;")
                self.combo_wf_box.addWidget(row)
        else:
            hint = QLabel("Chưa có dữ liệu walk-forward (OOS quá ngắn để chia đoạn).")
            hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
            self.combo_wf_box.addWidget(hint)

        self.combo_table.setRowCount(0)
        best = result.get("best_params", {}) or {}
        for sk in sorted([k for k in best if k.startswith("s")], key=lambda x: int(x[1:])):
            spec = best[sk]
            row = self.combo_table.rowCount()
            self.combo_table.insertRow(row)
            _loai = spec.get("type", "")
            _role = spec.get("role")
            if _role:
                _loai = f"{_loai} · {'TRIGGER' if _role == 'trigger' else 'FILTER'}"
            cells = [spec.get("key", ""), spec.get("tf", ""), _loai,
                     self._dict_to_str(spec.get("params", {})), self._dict_to_str(spec.get("thresholds", {}))]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setToolTip(str(text))
                if col < 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.combo_table.setItem(row, col, item)
        risk = best.get("risk", {})
        if risk:
            row = self.combo_table.rowCount()
            self.combo_table.insertRow(row)
            cells = ["RISK", "—", "sl/tp", f"Stop Loss = {risk.get('base_sl', '—')}%", f"Risk:Reward = {risk.get('rr', '—')}"]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setToolTip(str(text))
                item.setForeground(QColor(Theme.ACCENT))
                if col < 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.combo_table.setItem(row, col, item)
        self.combo_table.resizeRowsToContents()

    def _metric_cell(self, key, value, color):
        cell = QFrame()
        cell.setStyleSheet(
            f"QFrame {{ background: {Theme.BG}; border: 1px solid {Theme.BORDER}; border-radius: 6px; }}"
        )
        v = QVBoxLayout(cell)
        v.setContentsMargins(10, 7, 10, 7)
        v.setSpacing(3)
        kl = QLabel(str(key))
        kl.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
        vl = QLabel(str(value))
        vl.setStyleSheet(f"color: {color or Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        v.addWidget(kl)
        v.addWidget(vl)
        return cell

    def _format_metrics(self, res):
        ism = res.get("is_metrics", {}) or {}
        oos = res.get("oos_metrics", {}) or {}
        no_oos = _oos_thieu_lenh(res)
        is_sharpe = _safe_float(ism.get("sharpe_ratio"))
        oos_sharpe = _safe_float(oos.get("sharpe_ratio"))
        ratio = _safe_float(res.get("oos_is_ratio"))
        c_oos = Theme.TEXT_SUB if no_oos else (Theme.WIN if oos_sharpe > 0 else (Theme.LOSS if oos_sharpe < 0 else Theme.TEXT_MAIN))
        c_ratio = Theme.TEXT_SUB if no_oos else (Theme.WIN if ratio >= 0.8 else Theme.LOSS)

        def oos_txt(value, fmt):
            return "—" if no_oos else fmt.format(value)

        return [
            ("IS Sharpe", f"{is_sharpe:+.3f}", Theme.TEXT_MAIN),
            ("OOS Sharpe", oos_txt(oos_sharpe, "{:+.3f}"), c_oos),
            ("OOS Sortino", oos_txt(_safe_float(oos.get('sortino_ratio')), "{:+.3f}"), c_oos),
            ("OOS / IS", oos_txt(ratio, "{:.2f}"), c_ratio),
            ("IS DSR", f"{_safe_float(ism.get('deflated_sharpe_ratio')) * 100:.1f}%", Theme.TEXT_MAIN),
            ("OOS DSR", oos_txt(_safe_float(oos.get('deflated_sharpe_ratio')) * 100, "{:.1f}%"), Theme.TEXT_MAIN),
            ("OOS Win rate", oos_txt(_safe_float(oos.get('win_rate')), "{:.1f}%"), Theme.TEXT_MAIN),
            ("OOS Max DD", oos_txt(_safe_float(oos.get('max_drawdown_pct')), "{:.2f}%"), Theme.LOSS),
            ("OOS Profit factor", oos_txt(_safe_float(oos.get('profit_factor')), "{:.2f}"), Theme.TEXT_MAIN),
            ("OOS Trades", f"{int(_safe_float(oos.get('total_trades')))}", Theme.TEXT_MAIN),
        ]

    def _dict_to_str(self, d):
        if not d:
            return "—"
        return ", ".join(f"{k}={v}" for k, v in d.items())

    def _conclusion_style(self, conclusion):
        if conclusion == "DEPLOY":
            return Theme.WIN, "DEPLOY · ĐẠT NGƯỠNG TIN CẬY — CÓ THỂ DEPLOY"
        if conclusion == "NO_TRADE":
            return Theme.NEUTRAL, "KHÔNG ĐỦ LỆNH OOS để đánh giá — nới khoảng dữ liệu (config) hoặc giảm bớt/nới điều kiện AND"
        return Theme.LOSS, "REJECT · CHƯA ĐẠT NGƯỠNG (rủi ro overfit / hiệu suất kém)"

    def _cap_nhat_heatmap_controls(self, trials_data):
        self.cb_param_x.blockSignals(True)
        self.cb_param_y.blockSignals(True)
        self.cb_param_x.clear()
        self.cb_param_y.clear()
        
        if not trials_data or len(trials_data) == 0:
            self.cb_param_x.blockSignals(False)
            self.cb_param_y.blockSignals(False)
            self._ve_heatmap_do_nhay()
            return
            
        first_trial = trials_data[0]
        params = list(first_trial.get("params", {}).keys())
        
        if len(params) > 0:
            self.cb_param_x.addItems(params)
            self.cb_param_y.addItems(params)
            
            self.cb_param_x.setCurrentIndex(0)
            if len(params) > 1:
                self.cb_param_y.setCurrentIndex(1)
            else:
                self.cb_param_y.setCurrentIndex(0)
                
        self.cb_param_x.blockSignals(False)
        self.cb_param_y.blockSignals(False)
        self._ve_heatmap_do_nhay()

    def _ve_heatmap_do_nhay(self):
        result = getattr(self, "combo_result", None)
        if not result:
            self.heatmap_canvas.update_data(None, None, None)
            return

        trials_data = result.get("trials_data")
        param_x = self.cb_param_x.currentText()
        param_y = self.cb_param_y.currentText()

        self.heatmap_canvas.update_data(trials_data, param_x, param_y)

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        if getattr(self, "outer_stack", None) is not None:
            self.outer_stack.setCurrentWidget(self._workspace)
                                                                                                
        if getattr(self, "_left_panel", None) is not None:
            self._left_panel.setVisible(idx == 0)
        self._highlight_nav("toi_uu" if idx == 0 else "da_luu")

    def _load_existing_results(self):
        self._nap_thu_vien()

    def _nap_lan_chay_gan_nhat(self):
        if self.worker is not None and self.worker.isRunning():
            self.lbl_status.setText("⚠ Đang tối ưu — chờ xong hoặc dừng trước khi mở lần chạy cũ.")
            return
        history_dir = os.path.join(PROJECT_ROOT, "du_lieu", "history_uu_hoa")
        files = []
        if os.path.isdir(history_dir):
            files = sorted(
                [os.path.join(history_dir, f) for f in os.listdir(history_dir) if f.endswith(".json")],
                key=os.path.getmtime, reverse=True,
            )
        if not files:
            self.lbl_status.setText("⚠ Chưa có lịch sử chạy nào để mở.")
            return
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not data.get("best_params"):
                    continue
                self.combo_specs = [{"key": c["key"], "tf": c["tf"], "role": c.get("role", "trigger")} for c in data.get("combo", [])]
                self.combo_result = data
                self.combo_result_specs = list(self.combo_specs)
                self._dat_logic_ui(data)
                self._render_grid()
                self._update_builder_title()
                self._render_combo_result(data)
                self._switch_page(0)
                self.lbl_status.setText(f"Đã mở lần chạy gần nhất ({data.get('ngay_chay', '')}).")
                return
            except Exception as e:
                import traceback
                print(f"[load_history] Bỏ qua '{os.path.basename(fpath)}' do lỗi: {e}")
                traceback.print_exc()
                continue
        self.lbl_status.setText("⚠ Có lịch sử nhưng không nạp được file nào — xem console để biết lỗi.")

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'pvinh.kairos.analytics.v2'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication.instance() or QApplication(sys.argv)
    win = DashboardToiUu()
    win.setWindowTitle("Kairos v2 — Tối ưu chiến lược tổ hợp")
    
    icon_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(icon_path):
        try:
            from hien_thi.app.ung_dung import _load_rounded_icon
            icon = _load_rounded_icon(icon_path, 256, 40)
            app.setWindowIcon(icon)
            win.setWindowIcon(icon)
        except Exception:
            pass
            
    win.show()
    sys.exit(app.exec())
