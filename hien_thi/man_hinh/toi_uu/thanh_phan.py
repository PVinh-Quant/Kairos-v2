"""toi_uu/thanh_phan.py — Chip/Item kéo-thả: chỉ báo, plugin, lưới khung, mô-đun, dataset."""
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
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from .theme import *
from .dinh_nghia import *
from .tien_ich import *
class IndicatorItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.selected = False
        self._press_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(1)
        self.lbl_key = QLabel(key.upper())
        self.lbl_key.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 12px; background: transparent;")
        self.lbl_desc = QLabel(INDICATOR_DESC.get(key, ""))
        self.lbl_desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent;")
        lay.addWidget(self.lbl_key)
        lay.addWidget(self.lbl_desc)
        self._apply_style()

    def _apply_style(self):
        if self.selected:
            self.setStyleSheet("IndicatorItem { background: %s; border-left: 3px solid %s; border-radius: 4px; }" % (Theme.GRID, Theme.ACCENT))
        else:
            self.setStyleSheet(
                "IndicatorItem { background: transparent; border-left: 3px solid transparent; border-radius: 4px; }"
                "IndicatorItem:hover { background: #181b20; }"
            )

    def set_selected(self, value):
        self.selected = value
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.key)
        drag.setMimeData(mime)


        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QPoint, QRect

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.key.upper())
        badge_w = max(text_w + 24, 70)
        badge_h = 24

        pixmap = QPixmap(badge_w, badge_h)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)


        painter.setBrush(QBrush(QColor(14, 14, 14, 210)))
        painter.setPen(QPen(QColor(Theme.ACCENT), 1.5))
        painter.drawRoundedRect(1, 1, badge_w - 2, badge_h - 2, 4, 4)


        painter.setPen(QColor(Theme.TEXT_MAIN))
        painter.setFont(font)
        painter.drawText(QRect(0, 0, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, self.key.upper())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(badge_w // 2, badge_h // 2))

        drag.exec(Qt.DropAction.CopyAction)


class PluginItem(QFrame):
    """Mục chiến lược plugin trong panel trái (tab Plugin) — click để chọn."""
    clicked = pyqtSignal(str)

    def __init__(self, khoa, ten, mo_ta, parent=None):
        super().__init__(parent)
        self.khoa = khoa
        self.selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(1)
        self.lbl_ten = QLabel(ten)
        self.lbl_ten.setWordWrap(True)
        self.lbl_ten.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 12px; background: transparent; border: none;")
        lay.addWidget(self.lbl_ten)
        if mo_ta:
            d = QLabel(mo_ta)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
            lay.addWidget(d)
        self._apply_style()

    def _apply_style(self):
        if self.selected:
            self.setStyleSheet("PluginItem { background: %s; border-left: 3px solid %s; border-radius: 4px; }" % (Theme.GRID, Theme.PURPLE))
        else:
            self.setStyleSheet(
                "PluginItem { background: transparent; border-left: 3px solid transparent; border-radius: 4px; }"
                "PluginItem:hover { background: #181b20; }"
            )

    def set_selected(self, value):
        self.selected = value
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.khoa)
        super().mousePressEvent(event)





class GridChip(QFrame):
    def __init__(self, idx, spec, dashboard, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.spec = spec
        self.key = spec["key"]
        self.dashboard = dashboard
        self._press_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QFrame { background: %s; border: 1px solid %s; border-radius: 6px; }" % (Theme.GRID, Theme.BORDER))

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 6)
        v.setSpacing(4)


        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(2)

        name_str = self.key.upper()
        name = QLabel(name_str)

        font_size = 9 if len(name_str) > 12 else 11
        name.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: {font_size}px; background: transparent; border: none;")

        rm = QPushButton("×")
        rm.setFixedSize(14, 14)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(
            f"QPushButton {{ color: {Theme.TEXT_SUB}; background: transparent; border: none; font-weight: bold; font-size: 13px; line-height: 14px; }}"
            f"QPushButton:hover {{ color: {Theme.LOSS}; }}"
        )
        rm.clicked.connect(lambda _, idx=self.idx: self.dashboard._remove_chip(idx))

        top.addWidget(name, 1)
        top.addWidget(rm)
        v.addLayout(top)


        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)

        role = self.spec.get("role", "trigger")
        role_btn = QPushButton("Trigger" if role == "trigger" else "Filter")
        role_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        role_btn.setToolTip("Bấm đổi vai trò:\n• Trigger: kích hoạt vào lệnh.\n• Filter: chỉ điều kiện lọc (phải cùng chiều mới cho lệnh).")
        rc = Theme.PURPLE if role == "trigger" else Theme.ENTRY
        role_btn.setStyleSheet(
            f"QPushButton {{ color: {rc}; background: transparent; border: 1px solid {rc}; border-radius: 4px; font-size: 9px; font-weight: bold; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background: {rc}1a; }}"
        )
        role_btn.clicked.connect(lambda _, idx=self.idx: self.dashboard._toggle_role(idx))

        bottom.addWidget(role_btn)
        bottom.addStretch()
        v.addLayout(bottom)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dashboard.worker is not None and self.dashboard.worker.isRunning():
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"move:{self.idx}:{self.key}")
        drag.setMimeData(mime)

        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QPoint, QRect

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.key.upper())
        badge_w = max(text_w + 24, 70)
        badge_h = 24

        pixmap = QPixmap(badge_w, badge_h)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QBrush(QColor(14, 14, 14, 210)))
        painter.setPen(QPen(QColor(Theme.ACCENT), 1.5))
        painter.drawRoundedRect(1, 1, badge_w - 2, badge_h - 2, 4, 4)

        painter.setPen(QColor(Theme.TEXT_MAIN))
        painter.setFont(font)
        painter.drawText(QRect(0, 0, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, self.key.upper())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(badge_w // 2, badge_h // 2))

        action = drag.exec(Qt.DropAction.MoveAction)

        if action == Qt.DropAction.IgnoreAction:
            self.dashboard._remove_chip(self.idx)





class TimeframeColumn(QFrame):
    indicator_dropped = pyqtSignal(str, str)

    def __init__(self, tf, parent=None):
        super().__init__(parent)
        self.tf = tf
        self.setAcceptDrops(True)
        self.setMinimumWidth(115)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(6)
        head = QLabel(tf)
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 14px; background: transparent;")
        lay.addWidget(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(4)
        lay.addLayout(self.body)
        lay.addStretch()
        self._base_style()

    def _base_style(self):
        self.setStyleSheet("TimeframeColumn { background: %s; border: 1px dashed %s; border-radius: 8px; }" % (Theme.CARD, Theme.BORDER))

    def _hi_style(self):
        self.setStyleSheet("TimeframeColumn { background: %s; border: 2px solid %s; border-radius: 8px; }" % (Theme.GRID, Theme.ACCENT))

    def set_chips(self, chip_widgets):
        while self.body.count():
            it = self.body.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        if not chip_widgets:
            hint = QLabel("kéo thả\nchỉ báo")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent;")
            self.body.addWidget(hint)
        else:
            for cw in chip_widgets:
                self.body.addWidget(cw)

    @staticmethod
    def _la_mime_chi_bao(text):
        """Lưới khung thời gian CHỈ nhận chỉ báo (key thuần) hoặc di chuyển badge ("move:").
        KHÔNG nhận mô-đun ("module:" — Regime ML/SL-TP/Đòn bẩy) hay bộ dữ liệu ("data:")."""
        return bool(text) and not (text.startswith("module:") or text.startswith("data:"))

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and self._la_mime_chi_bao(event.mimeData().text()):
            event.acceptProposedAction()
            self._hi_style()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and self._la_mime_chi_bao(event.mimeData().text()):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._base_style()

    def dropEvent(self, event):
        if event.mimeData().hasText() and self._la_mime_chi_bao(event.mimeData().text()):
            self.indicator_dropped.emit(self.tf, event.mimeData().text())
            event.acceptProposedAction()
        self._base_style()





class ModuleItem(QFrame):
    """Item kéo được trong tab 'Mô-đun' (cột trái). Mime = 'module:<id>'."""

    def __init__(self, mid, parent=None):
        super().__init__(parent)
        self.mid = mid
        self._press_pos = None
        d = MODULE_DEFS[mid]
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        name = QLabel(d["name"])
        name.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 12px; background: transparent;")
        desc = QLabel(d["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent;")
        lay.addWidget(name)
        lay.addWidget(desc)
        self.setStyleSheet(
            "ModuleItem { background: transparent; border-left: 3px solid transparent; border-radius: 4px; }"
            "ModuleItem:hover { background: #181b20; }"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        from PyQt6.QtCore import QPoint
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"module:{self.mid}")
        drag.setMimeData(mime)
        pm, w, h = _make_badge_pixmap(MODULE_DEFS[self.mid]["name"])
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(w // 2, h // 2))
        drag.exec(Qt.DropAction.CopyAction)


class ModuleChip(QFrame):
    """Thẻ module đang dùng trong khung thả: tên + nút × + vùng tham số riêng."""

    def __init__(self, mid, dashboard, parent=None):
        super().__init__(parent)
        self.mid = mid
        self.dashboard = dashboard
        d = MODULE_DEFS[mid]
        self.setMinimumWidth(188)
        self.setMaximumWidth(240)
        self.setStyleSheet("ModuleChip { background: %s; border: 1px solid %s; border-radius: 6px; }" % (Theme.GRID, Theme.ACCENT))

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        name = QLabel(d["name"])
        name.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        rm = QPushButton("×")
        rm.setFixedSize(16, 16)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Gỡ module (tắt)")
        rm.setStyleSheet(
            f"QPushButton {{ color: {Theme.TEXT_SUB}; background: transparent; border: none; font-weight: bold; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {Theme.LOSS}; }}"
        )
        rm.clicked.connect(lambda _, m=mid: self.dashboard._remove_module(m))
        top.addWidget(name, 1)
        top.addWidget(rm)
        v.addLayout(top)

        self._build_params(v)


    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
        return l

    def _mk_combo(self, items, cur):
        c = QComboBox()
        c.addItems([str(x) for x in items])
        if str(cur) in [str(x) for x in items]:
            c.setCurrentText(str(cur))
        c.setFixedWidth(82)
        c.setStyleSheet(_compact_combo_css())
        return c

    def _mk_dspin(self, val, lo, hi, step):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setDecimals(1)
        s.setValue(float(val))
        s.setFixedWidth(54)
        s.setStyleSheet(_compact_spin_css())
        return s

    def _mk_ispin(self, val, lo, hi):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(int(val))
        s.setFixedWidth(54)
        s.setStyleSheet(_compact_spin_css())
        return s

    def _row(self, label, *widgets):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self._lbl(label))
        row.addStretch()
        for w in widgets:
            row.addWidget(w)
        return row

    def _set(self, key, value):
        self.dashboard._set_module_param(self.mid, key, value)

    def _toggle_regime(self, sid, on):
        """Bật/tắt 1 trạng thái thị trường trong tập 'allowed' của chip regime."""
        p = self.dashboard.active_modules.get(self.mid, {})
        allowed = {int(x) for x in p.get("allowed", REGIME_ALLOWED_DEFAULT)}
        if on:
            allowed.add(int(sid))
        else:
            allowed.discard(int(sid))
        self._set("allowed", sorted(allowed))

    def _build_params(self, v):
        p = self.dashboard.active_modules.get(self.mid, {})
        if self.mid == "regime":
            info = QLabel("ML lọc nến — chọn trạng thái thị trường được phép vào lệnh:")
            info.setWordWrap(True)
            info.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
            v.addWidget(info)

            allowed = {int(x) for x in p.get("allowed", REGIME_ALLOWED_DEFAULT)}
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(4)
            for i, (sid, name) in enumerate(REGIME_STATES):
                b = QPushButton(f"{sid}· {name}")
                b.setCheckable(True)
                b.setChecked(sid in allowed)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setToolTip(f"Regime {sid} — {name}: bật = cho phép vào lệnh khi ML nhận diện trạng thái này")
                b.setStyleSheet(_regime_toggle_css())
                b.toggled.connect(lambda on, s=sid: self._toggle_regime(s, on))
                grid.addWidget(b, i // 2, i % 2)
            v.addLayout(grid)

        elif self.mid == "sl_tp":
            cb = self._mk_combo(["Tự động"] + ALL_TIMEFRAMES, p.get("tf", "Tự động"))
            cb.currentTextChanged.connect(lambda t: self._set("tf", t))
            v.addLayout(self._row("Khung ATR", cb))

            smin = self._mk_dspin(p.get("sl_min", 1.0), 0.5, 20.0, 0.1)
            smax = self._mk_dspin(p.get("sl_max", 5.0), 0.5, 20.0, 0.1)
            smin.valueChanged.connect(lambda val: self._set("sl_min", val))
            smax.valueChanged.connect(lambda val: self._set("sl_max", val))
            v.addLayout(self._row("base_sl %", smin, self._lbl("–"), smax))

            rmin = self._mk_dspin(p.get("rr_min", 1.2), 0.5, 10.0, 0.1)
            rmax = self._mk_dspin(p.get("rr_max", 4.0), 0.5, 10.0, 0.1)
            rmin.valueChanged.connect(lambda val: self._set("rr_min", val))
            rmax.valueChanged.connect(lambda val: self._set("rr_max", val))
            v.addLayout(self._row("rr", rmin, self._lbl("–"), rmax))

        elif self.mid == "don_bay":
            sg = self._mk_ispin(p.get("goc", 5), 1, 125)
            sg.valueChanged.connect(lambda val: self._set("goc", val))
            v.addLayout(self._row("Đòn bẩy gốc", sg))

            sm = self._mk_ispin(p.get("max_lev", 50), 1, 125)
            sm.valueChanged.connect(lambda val: self._set("max_lev", val))
            v.addLayout(self._row("Max leverage", sm))

            cb = self._mk_combo(ALL_TIMEFRAMES, p.get("tf", "15m"))
            cb.currentTextChanged.connect(lambda t: self._set("tf", t))
            v.addLayout(self._row("Khung ATR", cb))


class ModuleDropZone(QFrame):
    """Khung thả module (giống cột khung thời gian, nhưng nằm ngang)."""

    module_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        self.body = QHBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)
        lay.addStretch()
        self._base_style()

    def _base_style(self):
        self.setStyleSheet("ModuleDropZone { background: %s; border: 1px dashed %s; border-radius: 8px; }" % (Theme.CARD, Theme.BORDER))

    def _hi_style(self):
        self.setStyleSheet("ModuleDropZone { background: %s; border: 2px solid %s; border-radius: 8px; }" % (Theme.GRID, Theme.ACCENT))

    def set_chips(self, chip_widgets):
        while self.body.count():
            it = self.body.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        if not chip_widgets:
            hint = QLabel("Kéo mô-đun từ tab “Mô-đun” (cột trái) thả vào đây")
            hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; border: none;")
            self.body.addWidget(hint)
        else:
            for cw in chip_widgets:
                self.body.addWidget(cw)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module:"):
            event.acceptProposedAction()
            self._hi_style()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module:"):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._base_style()

    def dropEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("module:"):
            self.module_dropped.emit(event.mimeData().text())
            event.acceptProposedAction()
        self._base_style()





class DataChip(QFrame):
    """Item kéo được trong tab 'Data Pool' (cột trái). Mime = 'data:<id>'."""

    def __init__(self, item, dashboard, parent=None):
        super().__init__(parent)
        self.item = item
        self.did = item.get("id", "")
        self.dashboard = dashboard
        self._press_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "DataChip { background: %s; border: 1px solid %s; border-radius: 8px; }"
            "DataChip:hover { border: 1px solid %s; background: #181b20; }" % (Theme.CARD, Theme.BORDER, Theme.ACCENT)
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 9, 8, 10)
        lay.setSpacing(6)

        syms = item.get("symbols", [])
        ten_full = item.get("ten", "(chưa đặt tên)")


        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(5)
        name = QLabel(_elide(ten_full, 100))
        name.setToolTip(ten_full)
        name.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 12px; background: transparent; border: none;")
        top.addWidget(name)
        top.addStretch()

        pill = QLabel(f"{len(syms)} sym")
        pill.setStyleSheet(_pill_css())
        top.addWidget(pill)

        edit = QPushButton("✎")
        edit.setFixedSize(20, 20)
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.setToolTip("Sửa bộ dữ liệu")
        edit.setStyleSheet(_icon_btn_css(Theme.ACCENT) + " QPushButton { font-size: 12px; }")
        edit.clicked.connect(lambda _, i=self.did: self.dashboard._sua_bo_du_lieu(i))
        rm = QPushButton("×")
        rm.setFixedSize(20, 20)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Xóa bộ dữ liệu")
        rm.setStyleSheet(_icon_btn_css(Theme.LOSS) + " QPushButton { font-weight: bold; font-size: 15px; }")
        rm.clicked.connect(lambda _, i=self.did: self.dashboard._xoa_bo_du_lieu(i))
        top.addWidget(edit)
        top.addWidget(rm)
        lay.addLayout(top)


        sl = QLabel(_ticker_goc(syms))
        sl.setWordWrap(True)
        sl.setToolTip(", ".join(syms))
        sl.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(sl)


        so_ngay = _so_ngay_khoang(item.get("tu_ngay"), item.get("den_ngay"))
        ngay_txt = f"{item.get('tu_ngay','?')}  →  {item.get('den_ngay','?')}"
        if so_ngay is not None:
            ngay_txt += f"   ·   {so_ngay} ngày"
        dt = QLabel(ngay_txt)
        dt.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
        lay.addWidget(dt)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        from PyQt6.QtCore import QPoint
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"data:{self.did}")
        drag.setMimeData(mime)
        pm, w, h = _make_badge_pixmap(self.item.get("ten", "dataset"))
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(w // 2, h // 2))
        drag.exec(Qt.DropAction.CopyAction)


class ActiveDatasetChip(QFrame):
    """Thẻ bộ dữ liệu đang chọn trong khung Run: tên + symbols + ngày + nút ×."""

    def __init__(self, item, dashboard, parent=None):
        super().__init__(parent)
        self.dashboard = dashboard
        self.setStyleSheet("ActiveDatasetChip { background: %s; border: 1px solid %s; border-radius: 8px; }" % (Theme.GRID, Theme.ACCENT))
        v = QVBoxLayout(self)
        v.setContentsMargins(9, 5, 7, 6)
        v.setSpacing(3)
        syms = item.get("symbols", [])
        ten_full = item.get("ten", "(dataset)")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(5)
        tag = QLabel("DỮ LIỆU")
        tag.setStyleSheet(_pill_css(8))
        top.addWidget(tag)
        name = QLabel(_elide(ten_full, 160, size=11))
        name.setToolTip(ten_full)
        name.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        top.addWidget(name)
        top.addStretch()
        rm = QPushButton("×")
        rm.setFixedSize(18, 18)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setToolTip("Bỏ chọn (trở về Symbol/ngày trong config)")
        rm.setStyleSheet(_icon_btn_css(Theme.LOSS) + " QPushButton { font-weight: bold; font-size: 15px; }")
        rm.clicked.connect(lambda: self.dashboard._clear_active_dataset())
        top.addWidget(rm)
        v.addLayout(top)

        so_ngay = _so_ngay_khoang(item.get("tu_ngay"), item.get("den_ngay"))
        ngay_txt = f"{item.get('tu_ngay','?')} → {item.get('den_ngay','?')}"
        if so_ngay is not None:
            ngay_txt += f"  ·  {so_ngay} ngày"
        info = QLabel(f"{_ticker_goc(syms)}   ·   {ngay_txt}")
        info.setToolTip(", ".join(syms))
        info.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
        v.addWidget(info)


class DataDropZone(QFrame):
    """Khung thả bộ dữ liệu (override Symbol + khoảng ngày cho lần tối ưu)."""

    data_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        self.body = QHBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)
        lay.addStretch()
        self._base_style()

    def _base_style(self):
        self.setStyleSheet("DataDropZone { background: %s; border: 1px dashed %s; border-radius: 8px; }" % (Theme.CARD, Theme.BORDER))

    def _hi_style(self):
        self.setStyleSheet("DataDropZone { background: %s; border: 2px solid %s; border-radius: 8px; }" % (Theme.GRID, Theme.ACCENT))

    def set_chips(self, chip_widgets):
        while self.body.count():
            it = self.body.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        if not chip_widgets:
            hint = QLabel("Kéo 1 bộ dữ liệu từ tab “Data Pool” vào đây · để trống = Symbol/ngày theo config")
            hint.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; border: none;")
            self.body.addWidget(hint)
        else:
            for cw in chip_widgets:
                self.body.addWidget(cw)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("data:"):
            event.acceptProposedAction()
            self._hi_style()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("data:"):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._base_style()

    def dropEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("data:"):
            self.data_dropped.emit(event.mimeData().text())
            event.acceptProposedAction()
        self._base_style()



__all__ = ["IndicatorItem", "PluginItem", "GridChip", "TimeframeColumn", "ModuleItem",
           "ModuleChip", "ModuleDropZone", "DataChip", "ActiveDatasetChip", "DataDropZone"]
