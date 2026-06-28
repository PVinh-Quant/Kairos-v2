"""toi_uu/bieu_do.py — Biểu đồ phân tích: Equity/Drawdown/PnL + scatter độ nhạy tham số."""
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
from .theme import *
from .tien_ich import *
from .dinh_nghia import *
class _ChartBase(QWidget):
    """
    Nền chung cho biểu đồ QPainter (đồng bộ phong cách dashboard_backtest):
    card bo góc + viền + tiêu đề + trạng thái rỗng. Lớp con cài `_ve_du_lieu`.
    """

    HEADER_H = 34
    PAD_L = 14
    PAD_R = 14
    PAD_B = 14

    def __init__(self, tieu_de, parent=None):
        super().__init__(parent)
        self.tieu_de = tieu_de
        self.co_du_lieu = False
        self.setMinimumHeight(170)
        self._f_title = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self._f_sub = QFont("Segoe UI", 8)
        self._f_val = QFont("Segoe UI", 15, QFont.Weight.Bold)
        self._f_tag = QFont("Segoe UI", 9, QFont.Weight.Bold)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(Theme.BORDER), 1))
        p.setBrush(QColor(Theme.CARD))
        p.drawRoundedRect(rect, 8, 8)

        p.setPen(QColor(Theme.TEXT_SUB))
        p.setFont(self._f_title)
        p.drawText(self.PAD_L, 20, self.tieu_de)

        if not self.co_du_lieu:
            p.setPen(QColor(Theme.TEXT_SUB))
            p.setFont(self._f_sub)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu")
            return

        x = self.PAD_L
        y = self.HEADER_H
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.HEADER_H - self.PAD_B
        if w > 20 and h > 20:
            self._ve_du_lieu(p, x, y, w, h)

    def _ve_du_lieu(self, p, x, y, w, h):
        pass


class EquityChartWidget(_ChartBase):
    """Đường cong vốn IS (vàng đồng) → OOS (xanh/đỏ) nối liền, gradient fill + vạch phân tách."""

    HEADER_H = 56

    def __init__(self, parent=None):
        super().__init__("ĐƯỜNG CONG VỐN  ·  IS → OOS", parent)
        self.setMinimumHeight(210)
        self.is_eq = []
        self.oos_eq = []
        self.final_val = 0.0
        self.pnl = 0.0
        self.pnl_pct = 0.0
        self.oos_up = True

    def update_data(self, is_eq, oos_eq, von_base=0.0):
        is_eq = [float(v) for v in (is_eq or [])]
        oos_raw = [float(v) for v in (oos_eq or [])]
        if is_eq and oos_raw:
            shift = is_eq[-1] - oos_raw[0]
            oos_eq = [v + shift for v in oos_raw]
        else:
            oos_eq = oos_raw
        self.is_eq, self.oos_eq = is_eq, oos_eq

        chuoi = is_eq + oos_eq
        base = von_base if von_base else (chuoi[0] if chuoi else 0.0)
        self.final_val = chuoi[-1] if chuoi else 0.0
        self.pnl = self.final_val - base
        self.pnl_pct = (self.pnl / base * 100) if base else 0.0
        self.oos_up = (oos_raw[-1] >= oos_raw[0]) if len(oos_raw) >= 2 else (self.pnl >= 0)
        self.co_du_lieu = bool(chuoi)
        self.update()

    def _ve_du_lieu(self, p, x, y, w, h):
        chuoi = self.is_eq + self.oos_eq
        n = len(chuoi)
        mn, mx = min(chuoi), max(chuoi)
        rng = (mx - mn) or 1.0
        step = w / (n - 1) if n > 1 else w
        baseline = y + h
        oos_color = QColor(Theme.WIN if self.oos_up else Theme.LOSS)

        def XY(i, val):
            return QPointF(x + i * step, baseline - (val - mn) / rng * h)


        p.setFont(self._f_val)
        p.setPen(QColor(Theme.TEXT_MAIN))
        sval = f"{self.final_val:,.2f}"
        p.drawText(self.PAD_L, 46, sval)
        wv = QFontMetrics(self._f_val).horizontalAdvance(sval)
        p.setFont(self._f_tag)
        p.setPen(QColor(Theme.WIN if self.pnl >= 0 else Theme.LOSS))
        sign = "+" if self.pnl >= 0 else ""
        p.drawText(self.PAD_L + wv + 10, 46, f"{sign}{self.pnl:,.2f}  ({sign}{self.pnl_pct:.2f}%)")

        def ve_doan(i0, vals, mau, anchor=None):
            if not vals:
                return
            path = QPainterPath()
            start = anchor if anchor is not None else XY(i0, vals[0])
            path.moveTo(start)
            for j, v in enumerate(vals):
                path.lineTo(XY(i0 + j, v))
            fill = QPainterPath(path)
            fill.lineTo(XY(i0 + len(vals) - 1, mn).x(), baseline)
            fill.lineTo(start.x(), baseline)
            fill.closeSubpath()
            g = QLinearGradient(0, y, 0, baseline)
            c1 = QColor(mau); c1.setAlpha(70)
            c2 = QColor(mau); c2.setAlpha(0)
            g.setColorAt(0, c1); g.setColorAt(1, c2)
            p.fillPath(fill, QBrush(g))
            p.setPen(QPen(QColor(mau), 2))
            p.drawPath(path)

        Lis = len(self.is_eq)
        ve_doan(0, self.is_eq, QColor(Theme.ACCENT))
        if self.oos_eq:
            anchor = XY(Lis - 1, self.is_eq[-1]) if Lis > 0 else None
            ve_doan(Lis, self.oos_eq, oos_color, anchor=anchor)
            if Lis > 0:
                xb = x + (Lis - 1) * step
                p.setPen(QPen(QColor(Theme.TEXT_SUB), 1, Qt.PenStyle.DashLine))
                p.drawLine(int(xb), int(y), int(xb), int(baseline))


        p.setFont(self._f_sub)
        ly = 20
        lx = self.width() - self.PAD_R - 76
        p.setBrush(QColor(Theme.ACCENT)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(lx, ly - 5, 12, 3))
        p.setPen(QColor(Theme.TEXT_SUB)); p.drawText(int(lx + 15), int(ly), "IS")
        p.setBrush(oos_color); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(lx + 38, ly - 5, 12, 3))
        p.setPen(QColor(Theme.TEXT_SUB)); p.drawText(int(lx + 53), int(ly), "OOS")


class DrawdownChartWidget(_ChartBase):
    """Drawdown (%) — vùng tô đỏ từ mốc 0% xuống đáy, IS + OOS với vạch phân tách."""

    HEADER_H = 32

    def __init__(self, parent=None):
        super().__init__("DRAWDOWN (%)", parent)
        self.dd = []
        self.boundary = 0
        self.max_dd = 0.0

    def update_data(self, is_dd, oos_dd):
        is_dd = [float(v) for v in (is_dd or [])]
        oos_dd = [float(v) for v in (oos_dd or [])]
        self.dd = is_dd + oos_dd
        self.boundary = len(is_dd)
        self.max_dd = min(self.dd) if self.dd else 0.0
        self.co_du_lieu = bool(self.dd)
        self.update()

    def _ve_du_lieu(self, p, x, y, w, h):
        n = len(self.dd)
        p.setFont(self._f_tag)
        p.setPen(QColor(Theme.LOSS))
        p.drawText(self.PAD_L + 96, 20, f"Max {self.max_dd:.2f}%")

        worst = abs(self.max_dd) or 1.0
        step = w / (n - 1) if n > 1 else w
        y0 = y

        def XY(i, val):
            return QPointF(x + i * step, y0 + (abs(val) / worst) * h)

        path = QPainterPath(); path.moveTo(XY(0, self.dd[0]))
        for i, v in enumerate(self.dd):
            path.lineTo(XY(i, v))
        fill = QPainterPath(path)
        fill.lineTo(x + (n - 1) * step, y0)
        fill.lineTo(x, y0)
        fill.closeSubpath()
        g = QLinearGradient(0, y0, 0, y0 + h)
        c1 = QColor(Theme.LOSS); c1.setAlpha(85)
        c2 = QColor(Theme.LOSS); c2.setAlpha(10)
        g.setColorAt(0, c1); g.setColorAt(1, c2)
        p.fillPath(fill, QBrush(g))
        p.setPen(QPen(QColor(Theme.LOSS), 1.4)); p.drawPath(path)

        p.setPen(QPen(QColor(Theme.GRID), 1))
        p.drawLine(int(x), int(y0), int(x + w), int(y0))
        if 0 < self.boundary < n:
            xb = x + (self.boundary - 1) * step
            p.setPen(QPen(QColor(Theme.TEXT_SUB), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(xb), int(y0), int(xb), int(y0 + h))


class PnLHistogramWidget(_ChartBase):
    """Phân phối PnL mỗi lệnh — cột xanh (lãi) / đỏ (lỗ), gộp IS + OOS, có mốc 0."""

    HEADER_H = 32

    def __init__(self, parent=None):
        super().__init__("PHÂN PHỐI PnL / LỆNH", parent)
        self.counts = []
        self.edges = []
        self.n_trades = 0

    def update_data(self, all_pnl):
        arr = np.asarray([float(v) for v in (all_pnl or [])], dtype=float)
        self.n_trades = int(arr.size)
        if arr.size >= 1:
            lo, hi = float(arr.min()), float(arr.max())
            if hi <= lo:
                lo, hi = lo - 1.0, hi + 1.0


            if lo < 0 < hi:
                range_neg = abs(lo)
                range_pos = hi
                total_range = range_neg + range_pos

                nb_total = max(8, min(30, arr.size))
                nb_neg = max(3, int(round(nb_total * (range_neg / total_range))))
                nb_pos = max(3, nb_total - nb_neg)

                edges_neg = np.linspace(lo, 0.0, nb_neg + 1)
                edges_pos = np.linspace(0.0, hi, nb_pos + 1)
                edges = np.concatenate([edges_neg[:-1], edges_pos])
                counts, edges = np.histogram(arr, bins=edges)
            else:
                nb = max(8, min(30, arr.size))
                counts, edges = np.histogram(arr, bins=nb, range=(lo, hi))

            self.counts = counts.tolist()
            self.edges = edges.tolist()
        else:
            self.counts, self.edges = [], []
        self.co_du_lieu = self.n_trades > 0 and bool(self.counts)
        self.update()

    def _ve_du_lieu(self, p, x, y, w, h):
        nb = len(self.counts)
        p.setFont(self._f_sub)
        p.setPen(QColor(Theme.TEXT_SUB))
        p.drawText(self.PAD_L + 132, 20, f"{self.n_trades} lệnh")

        mx = max(self.counts) or 1
        lo, hi = self.edges[0], self.edges[-1]
        rng = (hi - lo) or 1.0
        baseline = y + h
        gap = 1.0

        for i, c in enumerate(self.counts):
            left_val = self.edges[i]
            right_val = self.edges[i + 1]
            center = (left_val + right_val) / 2

            col = QColor(Theme.WIN if center > 0 else Theme.LOSS)
            col.setAlpha(210)
            bh = (c / mx) * h


            x_left = x + (left_val - lo) / rng * w
            x_right = x + (right_val - lo) / rng * w
            bin_w = x_right - x_left

            p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
            p.drawRect(QRectF(x_left + gap / 2, baseline - bh, max(bin_w - gap, 1.0), bh))

        if lo < 0 < hi:
            zx = x + (0 - lo) / rng * w
            p.setPen(QPen(QColor(Theme.TEXT_SUB), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(zx), int(y), int(zx), int(baseline))
        p.setPen(QPen(QColor(Theme.GRID), 1))
        p.drawLine(int(x), int(baseline), int(x + w), int(baseline))


class BieuDoPhanTich(QWidget):
    """
    Bộ 3 biểu đồ phân tích (QPainter, phong cách dashboard_backtest):
    Equity (toàn chiều rộng) ở trên; hàng dưới gồm Drawdown + Histogram PnL.
    Dùng dữ liệu ``result['phan_tich']`` = {is:{...}, oos:{...}}.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.equity = EquityChartWidget(self)
        self.drawdown = DrawdownChartWidget(self)
        self.histogram = PnLHistogramWidget(self)
        lay.addWidget(self.equity, 5)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.drawdown, 3)
        row.addWidget(self.histogram, 2)
        lay.addLayout(row, 4)

    def update_data(self, phan_tich):
        pt = phan_tich or {}
        is_d = pt.get("is") or {}
        oos_d = pt.get("oos") or {}



        von_notional = _safe_float(is_d.get("von") or oos_d.get("von")) or 1.0
        so_du = _safe_float(is_d.get("so_du") or oos_d.get("so_du")) or SO_DU_BAN_DAU
        delta = so_du - von_notional
        is_eq = [v + delta for v in (is_d.get("equity") or [])]
        oos_eq = [v + delta for v in (oos_d.get("equity") or [])]
        self.equity.update_data(is_eq, oos_eq, so_du)
        self.drawdown.update_data(is_d.get("drawdown_pct"), oos_d.get("drawdown_pct"))
        self.histogram.update_data((is_d.get("pnl") or []) + (oos_d.get("pnl") or []))


class ParameterSensitivityScatterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.points = []
        self.max_x = 1.0
        self.min_x = 0.0
        self.max_y = 1.0
        self.min_y = 0.0
        self.max_val = 1.0
        self.min_val = 0.0

        self.param_x_name = "X"
        self.param_y_name = "Y"

        self.setMouseTracking(True)
        self.hover_point = None

        self.font_sub = QFont("Segoe UI", 8)
        self.font_label = QFont("Segoe UI", 9)
        self.font_main = QFont("Segoe UI", 10)

    def update_data(self, trials_data, param_x, param_y):
        self.points = []
        self.hover_point = None
        self.param_x_name = param_x or "X"
        self.param_y_name = param_y or "Y"

        if not trials_data or not param_x or not param_y:
            self.update()
            return

        try:
            x_vals = []
            y_vals = []
            vals = []

            for t in trials_data:
                t_params = t.get("params", {})
                if param_x in t_params and param_y in t_params:
                    x_v = float(t_params[param_x])
                    y_v = float(t_params[param_y])
                    val = float(t.get("value", 0.0))

                    x_vals.append(x_v)
                    y_vals.append(y_v)
                    vals.append(val)

            if len(x_vals) < 2:
                self.update()
                return

            self.min_x = min(x_vals)
            self.max_x = max(x_vals)
            self.min_y = min(y_vals)
            self.max_y = max(y_vals)
            self.min_val = min(vals)
            self.max_val = max(vals)


            if self.max_x == self.min_x: self.max_x += 1.0
            if self.max_y == self.min_y: self.max_y += 1.0
            if self.max_val == self.min_val: self.max_val += 1.0

            for t in trials_data:
                t_params = t.get("params", {})
                if param_x in t_params and param_y in t_params:
                    x_v = float(t_params[param_x])
                    y_v = float(t_params[param_y])
                    val = float(t.get("value", 0.0))


                    ratio = (val - self.min_val) / (self.max_val - self.min_val)
                    ratio = max(0.0, min(1.0, ratio))


                    r_col = int(242 + ratio * (8 - 242))
                    g_col = int(54 + ratio * (153 - 54))
                    b_col = int(69 + ratio * (129 - 69))
                    color = QColor(r_col, g_col, b_col)

                    self.points.append({
                        "x_val": x_v,
                        "y_val": y_v,
                        "val": val,
                        "color": color
                    })

        except Exception as e:
            print(f"Lỗi logic Parameter Scatter Plot: {e}")

        self.update()

    def get_pos(self, x_val, y_val, plot_w, plot_h, m_left, m_top):
        x_ratio = (x_val - self.min_x) / (self.max_x - self.min_x)
        y_ratio = (y_val - self.min_y) / (self.max_y - self.min_y)

        px = m_left + x_ratio * plot_w

        py = m_top + plot_h - (y_ratio * plot_h)
        return px, py

    def mouseMoveEvent(self, event):
        import math
        if not self.points:
            return

        mx, my = event.position().x(), event.position().y()
        w, h = self.width(), self.height()

        m_left, m_bottom, m_top, m_right = 60, 40, 20, 20
        plot_w = w - m_left - m_right
        plot_h = h - m_top - m_bottom

        closest_dist = 15
        found = None

        for p in self.points:
            px, py = self.get_pos(p["x_val"], p["y_val"], plot_w, plot_h, m_left, m_top)

            dist = math.hypot(px - mx, py - my)
            if dist < closest_dist:
                closest_dist = dist
                found = p
                found["sx"] = px
                found["sy"] = py

        if self.hover_point != found:
            self.hover_point = found
            self.update()

    def paintEvent(self, event):
        if not hasattr(self, "points") or not self.points:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(Theme.CARD))
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No Data Available"
            )
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Theme.CARD))

        w, h = self.width(), self.height()
        m_left, m_bottom, m_top, m_right = 60, 40, 20, 20
        plot_w = w - m_left - m_right
        plot_h = h - m_top - m_bottom


        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.drawLine(m_left, m_top, m_left, h - m_bottom)
        painter.drawLine(m_left, h - m_bottom, w - m_right, h - m_bottom)


        painter.setFont(self.font_sub)


        for i in range(5):
            ratio = i / 4.0
            val_x = self.min_x + ratio * (self.max_x - self.min_x)
            px = m_left + ratio * plot_w


            painter.setPen(QPen(QColor(Theme.GRID), 1, Qt.PenStyle.DotLine))
            painter.drawLine(int(px), m_top, int(px), h - m_bottom)


            painter.setPen(QColor(Theme.TEXT_SUB))
            label = f"{val_x:.1f}" if (self.max_x - self.min_x) < 5 else f"{int(round(val_x))}"
            painter.drawText(int(px) - 15, h - m_bottom + 15, label)


        for i in range(5):
            ratio = i / 4.0
            val_y = self.min_y + ratio * (self.max_y - self.min_y)
            py = m_top + plot_h - (ratio * plot_h)


            painter.setPen(QPen(QColor(Theme.GRID), 1, Qt.PenStyle.DotLine))
            painter.drawLine(m_left, int(py), w - m_right, int(py))


            painter.setPen(QColor(Theme.TEXT_SUB))
            label = f"{val_y:.1f}" if (self.max_y - self.min_y) < 5 else f"{int(round(val_y))}"
            painter.drawText(5, int(py) + 4, label)


        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.points:
            x, y = self.get_pos(p["x_val"], p["y_val"], plot_w, plot_h, m_left, m_top)

            is_hover = self.hover_point == p
            radius = 7 if is_hover else 5

            c = QColor(p["color"])
            c.setAlpha(255 if is_hover else 185)
            painter.setBrush(c)

            if is_hover:
                painter.setPen(QPen(QColor("white"), 1))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawEllipse(QPointF(x, y), radius, radius)


        if self.hover_point:
            hp = self.hover_point
            tip_text = f"{self.param_x_name}: {hp['x_val']}\n{self.param_y_name}: {hp['y_val']}\nScore: {hp['val']:.4f}"

            fm = painter.fontMetrics()
            lines = tip_text.split("\n")
            max_w = max([fm.horizontalAdvance(l) for l in lines]) + 20
            box_h = len(lines) * fm.height() + 15

            bx = hp["sx"] + 10
            by = hp["sy"] - 10


            if bx + max_w > w:
                bx = hp["sx"] - max_w - 10
            if by + box_h > h:
                by = hp["sy"] - box_h - 10

            painter.setPen(QPen(QColor(Theme.ACCENT), 1))
            painter.setBrush(QColor(20, 20, 20, 240))
            painter.drawRoundedRect(QRectF(bx, by, max_w, box_h), 5, 5)

            painter.setPen(QColor(Theme.TEXT_MAIN))
            for i, line in enumerate(lines):
                painter.drawText(int(bx + 10), int(by + 15 + i * fm.height()), line)






__all__ = ["_ChartBase", "EquityChartWidget", "DrawdownChartWidget",
           "PnLHistogramWidget", "BieuDoPhanTich", "ParameterSensitivityScatterWidget"]
