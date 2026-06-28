"""nen_thu_cong/dashboard.py — BieuDoNenThuCong: nhập tham số tay/chỉ báo → biểu đồ nến.

Khác màn Tối ưu (kéo-thả + Optuna dò ngưỡng): ở đây người dùng TỰ NHẬP tham số cố
định cho từng chỉ báo (window, ngưỡng, hệ số…), chọn khung & vai trò, rồi bấm
'▶ Chạy'. Hệ thống dựng đúng 1 chiến lược JSON từ các tham số đó và backtest bằng
CHÍNH pipeline vectorized (qua BacktestWorker của màn Biểu đồ nến) — không tạo path
tín hiệu mới. Kết quả ở dưới là biểu đồ nến + bảng lệnh (tái dùng CandlestickChartWidget).
"""
import sys
import inspect
import time
from functools import lru_cache

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QSplitter, QSizePolicy,
    QLineEdit, QStackedWidget, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QRect, QRectF
from PyQt6.QtGui import (
    QColor, QDrag, QPainter, QPen, QBrush, QFont, QPixmap, QFontMetrics
)

from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from hien_thi.giao_dien.theme import Theme
from hien_thi.man_hinh.toi_uu.dinh_nghia import CATEGORIES, INDICATOR_DESC, ALL_TIMEFRAMES, MODULE_DEFS, REGIME_ALLOWED_DEFAULT, DEFAULT_MODULE_PARAMS
from hien_thi.man_hinh.bieu_do_nen.dashboard import CandlestickChartWidget
from hien_thi.man_hinh.bieu_do_nen.worker import BacktestWorker


from hien_thi.man_hinh.toi_uu.thanh_phan import ModuleItem, DataChip, ModuleDropZone, DataDropZone, ActiveDatasetChip, ModuleChip
from hien_thi.man_hinh.toi_uu.data_pool import DataPoolDialog
from hien_thi.man_hinh.toi_uu.tien_ich import doc_bo_du_lieu, luu_bo_du_lieu



@lru_cache(maxsize=None)
def _loai_chi_bao(key):
    """Loại chỉ báo ('oscillator'/'channel'/'trend'/'volume') — tự dò qua registry."""
    try:
        from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY
        from toi_uu_hoa.phan_loai_chi_bao import detect_indicator_type
        func = INDICATOR_REGISTRY.get(key)
        if func is None:
            return "trend"
        itype, _ = detect_indicator_type(func)
        return itype or "trend"
    except Exception:
        return "trend"


def _tham_so_mac_dinh(key):
    """Trích tham số số học (window/fast/multiplier…) + mặc định từ chữ ký hàm chỉ báo."""
    out = {}
    try:
        from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY
        func = INDICATOR_REGISTRY.get(key)
        if func is None:
            return out
        sig = inspect.signature(func)
    except Exception:
        return out
    skip = {"df", "time_frame", "timeframe", "tf", "self"}
    for name, p in sig.parameters.items():
        if name in skip or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        d = p.default
        if d is inspect.Parameter.empty:
            d = 14

        if isinstance(d, bool) or not isinstance(d, (int, float)):
            continue
        out[name] = d
    return out


def _nguong_mac_dinh(key, itype):
    """Ngưỡng vào/thoát lệnh mặc định theo loại chỉ báo (khớp generate_generic_signals)."""
    if itype == "oscillator":
        try:
            from toi_uu_hoa.phan_loai_chi_bao import is_centered_oscillator
            if is_centered_oscillator(key):
                return {"oversold": -100.0, "overbought": 100.0}
        except Exception:
            pass
        return {"oversold": 30.0, "overbought": 70.0}
    if itype == "channel":
        return {"lower_mult": 1.0, "upper_mult": 1.0}
    if itype == "trend":
        return {"dev_above": 1.0, "dev_below": 1.0}
    return {}


def _mk_spin(val):
    """Spinbox int/float tuỳ kiểu giá trị mặc định, style đồng bộ Theme."""
    if isinstance(val, float):
        sp = QDoubleSpinBox()
        sp.setDecimals(3)
        sp.setRange(-1_000_000.0, 1_000_000.0)
        sp.setSingleStep(0.1)
        sp.setValue(float(val))
    else:
        sp = QSpinBox()
        sp.setRange(-1_000_000, 1_000_000)
        sp.setValue(int(val))
    sp.setFixedWidth(64)
    sp.setFixedHeight(20)
    sp.setStyleSheet(
        f"QAbstractSpinBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 3px; padding: 1px 4px; font-size: 10px; }}"
        f"QAbstractSpinBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
        f"QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; height: 0; border: none; }}"
    )
    return sp


def _combo_css():
    return (
        f"QComboBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 3px 20px 3px 8px; font-size: 11px; }}"
        f"QComboBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
        f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 18px; border-left: none; background: transparent; }}"
        f"QComboBox QAbstractItemView {{ background: {Theme.CARD}; color: {Theme.TEXT_MAIN}; selection-background-color: {Theme.GRID}; border: 1px solid {Theme.BORDER}; border-radius: 4px; outline: 0; }}"
        f"QComboBox QAbstractItemView::item {{ border-left: 3px solid transparent; padding-left: 6px; height: 24px; }}"
        f"QComboBox QAbstractItemView::item:selected {{ border-left: 3px solid {Theme.PURPLE}; background-color: {Theme.GRID}; }}"
    )



class ThuCongIndicatorItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key
        self.selected = False
        self._press_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        self.lbl_key = QLabel(key.upper())
        self.lbl_key.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 12px; background: transparent; border: none;")
        self.lbl_desc = QLabel(INDICATOR_DESC.get(key, ""))
        self.lbl_desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 10px; background: transparent; border: none;")
        lay.addWidget(self.lbl_key)
        lay.addWidget(self.lbl_desc)
        self._apply_style()

    def _apply_style(self):
        if self.selected:
            self.setStyleSheet("ThuCongIndicatorItem { background: %s; border-left: 3px solid %s; border-radius: 4px; }" % (Theme.GRID, Theme.ACCENT))
        else:
            self.setStyleSheet(
                "ThuCongIndicatorItem { background: transparent; border-left: 3px solid transparent; border-radius: 4px; }"
                "ThuCongIndicatorItem:hover { background: #1c2030; }"
            )

    def set_selected(self, value):
        self.selected = value
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            diff = event.position().toPoint() - self._press_pos
            if diff.manhattanLength() < 8:
                self.clicked.emit(self.key)
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return

        self._press_pos = None

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.key)
        drag.setMimeData(mime)

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.key.upper())
        badge_w = max(text_w + 16, 60)
        badge_h = 20

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


class ThuCongGridChip(QFrame):
    def __init__(self, idx, spec, dashboard, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.spec = spec
        self.key = spec["key"]
        self.dashboard = dashboard
        self._press_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QFrame { background: %s; border: 1px solid %s; border-radius: 4px; }" % (Theme.GRID, Theme.BORDER))

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
        role_btn.setToolTip("Bấm đổi vai trò:\n• Trigger: kích hoạt vào lệnh.\n• Filter: chỉ lọc (phải cùng chiều mới cho lệnh).")
        rc = Theme.PURPLE if role == "trigger" else Theme.ENTRY
        role_btn.setStyleSheet(
            f"QPushButton {{ color: {rc}; background: transparent; border: 1px solid {rc}; border-radius: 3px; font-size: 9px; font-weight: bold; padding: 2px 6px; }}"
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
        if self.dashboard._worker is not None and self.dashboard._worker.isRunning():
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 12:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"move:{self.idx}:{self.key}")
        drag.setMimeData(mime)

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self.key.upper())
        badge_w = max(text_w + 16, 60)
        badge_h = 20

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


class ThuCongTimeframeColumn(QFrame):
    indicator_dropped = pyqtSignal(str, str)

    def __init__(self, tf, parent=None):
        super().__init__(parent)
        self.tf = tf
        self.setAcceptDrops(True)
        self.setMinimumWidth(100)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(4)

        head = QLabel(tf)
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        lay.addWidget(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(4)
        lay.addLayout(self.body)
        lay.addStretch()
        self._base_style()

    def _base_style(self):

        has_chips = len([w for w in self.findChildren(ThuCongGridChip)]) > 0
        if has_chips:

            self.setStyleSheet(
                f"ThuCongTimeframeColumn {{ background: {Theme.CARD}; border: 1.5px solid {Theme.ACCENT}80; border-radius: 6px; }}"
            )
        else:
            self.setStyleSheet(
                f"ThuCongTimeframeColumn {{ background: {Theme.CARD}; border: 1px dashed {Theme.BORDER}; border-radius: 6px; }}"
            )

    def _hi_style(self):

        self.setStyleSheet(
            f"ThuCongTimeframeColumn {{ background: {Theme.GRID}; border: 2px solid {Theme.ACCENT}; border-radius: 6px; }}"
        )

    def set_chips(self, chip_widgets):
        while self.body.count():
            it = self.body.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        if not chip_widgets:
            hint = QLabel("+ Thả")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(f"color: {Theme.TEXT_SUB}60; font-size: 11px; font-weight: bold; background: transparent; padding: 12px 0; border: none;")
            self.body.addWidget(hint)
        else:
            for cw in chip_widgets:
                self.body.addWidget(cw)
        self._base_style()

    @staticmethod
    def _la_mime_chi_bao(text):
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



class TheChiBao(QFrame):
    """Một thẻ cấu hình cho 1 chỉ báo: người dùng tự nhập mọi tham số & ngưỡng."""
    removed = pyqtSignal(int)

    def __init__(self, idx, spec, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.spec = spec
        self.key = spec["key"]
        self.itype = spec["type"]
        self.param_widgets = {}
        self.thr_widgets = {}

        self.setStyleSheet(
            f"QFrame {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; border-radius: 6px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(6)


        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)

        name = QLabel(f"{self.key.upper()} ({self.spec.get('tf', '5m')})")
        name.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        head.addWidget(name)

        desc = QLabel(f"·  {INDICATOR_DESC.get(self.key, self.key)}  ·  {self.itype}")
        desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; border: none;")
        head.addWidget(desc)

        head.addSpacing(20)
        head.addWidget(self._lbl("Vai trò:"))

        self.cb_role = QComboBox()
        self.cb_role.addItem("Trigger (vào lệnh)", "trigger")
        self.cb_role.addItem("Filter (lọc)", "filter")
        self.cb_role.setStyleSheet(_combo_css())
        self.cb_role.setFixedWidth(140)
        self.cb_role.setFixedHeight(22)

        role_val = self.spec.get("role", "trigger")
        idx_role = self.cb_role.findData(role_val)
        if idx_role >= 0:
            self.cb_role.setCurrentIndex(idx_role)

        head.addWidget(self.cb_role)
        head.addStretch()

        btn_x = QPushButton("✕")
        btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_x.setFixedSize(20, 20)
        btn_x.setStyleSheet(
            f"QPushButton {{ color: {Theme.TEXT_SUB}; background: transparent; border: none; font-size: 12px; border-radius: 4px; }}"
            f"QPushButton:hover {{ color: {Theme.LOSS}; background: {Theme.GRID}; }}"
        )
        btn_x.clicked.connect(lambda: self.removed.emit(self.idx))
        head.addWidget(btn_x)
        lay.addLayout(head)


        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        col = 0
        row = 0

        def _add_field(label_txt, widget, store, store_key):
            nonlocal col, row
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(6)
            l = QLabel(label_txt + ":")
            l.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; font-weight: bold; background: transparent; border: none;")
            cell.addWidget(l)
            cell.addWidget(widget)
            cw = QWidget()
            cw.setStyleSheet("background: transparent;")
            cw.setLayout(cell)
            grid.addWidget(cw, row, col)
            store[store_key] = widget
            col += 1
            if col >= 4:
                col = 0
                row += 1


        default_params = _tham_so_mac_dinh(self.key)
        spec_params = self.spec.get("params", {})
        merged_params = {}
        for k, v in default_params.items():
            merged_params[k] = spec_params.get(k, v)
        for k, v in spec_params.items():
            merged_params.setdefault(k, v)

        default_thrs = _nguong_mac_dinh(self.key, self.itype)
        spec_thrs = self.spec.get("thresholds", {})
        merged_thrs = {}
        for k, v in default_thrs.items():
            merged_thrs[k] = spec_thrs.get(k, v)
        for k, v in spec_thrs.items():
            merged_thrs.setdefault(k, v)

        for pname, pval in merged_params.items():
            _add_field(pname, _mk_spin(pval), self.param_widgets, pname)
        for tname, tval in merged_thrs.items():
            _add_field(tname, _mk_spin(tval), self.thr_widgets, tname)

        if not self.param_widgets and not self.thr_widgets:
            note = QLabel("Chỉ báo này không có tham số số học để nhập (dùng tín hiệu mặc định).")
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; border: none;")
            grid.addWidget(note, 0, 0, 1, 4)

        lay.addLayout(grid)

    def _lbl(self, txt):
        l = QLabel(txt)
        l.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 11px; background: transparent; border: none;")
        return l

    def to_spec(self):
        """Trả spec 1 chỉ báo cho config chiến lược JSON (key/type/tf/role/params/thresholds)."""
        return {
            "key": self.key,
            "type": self.itype,
            "tf": self.spec.get("tf", "5m"),
            "role": self.cb_role.currentData(),
            "params": {n: w.value() for n, w in self.param_widgets.items()},
            "thresholds": {n: w.value() for n, w in self.thr_widgets.items()},
        }



class BieuDoNenThuCong(QWidget):
    """Tab 'Chỉ báo thủ công': nhập tham số tay cho từng chỉ báo → biểu đồ nến kết quả."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(f"background-color: {Theme.BG};")
        self.combo_specs = []
        self.cards = []
        self.tf_columns = {}
        self.indicator_items = {}
        self.module_items = {}
        self.bo_du_lieu = doc_bo_du_lieu()
        for _i, _it in enumerate(self.bo_du_lieu):
            _it.setdefault("id", f"ds_load_{_i}")
        self.data_pool_layout = None
        self.active_dataset = None
        self.active_modules = {}
        self.data_zone = None
        self.module_zone = None
        self.phien = None
        self._worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)


        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {Theme.BORDER}; }}")
        self.main_splitter.setHandleWidth(1)
        root.addWidget(self.main_splitter, 1)


        self.left_panel = self._build_left_panel()
        self.left_panel.setMinimumWidth(220)
        self.main_splitter.addWidget(self.left_panel)


        self.right_widget = QWidget()
        right_lay = QVBoxLayout(self.right_widget)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.config_panel = self._build_config_panel()
        self.config_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_lay.addWidget(self.config_panel, 1)

        self.main_splitter.addWidget(self.right_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([230, 1000])


        self._build_statusbar(root)


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
        for idx, name in [(0, "Chỉ báo"), (1, "Mô-đun"), (2, "Data Pool")]:
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
                item = ThuCongIndicatorItem(key)
                item.clicked.connect(self._select_quick)
                self.indicator_items[key] = item
                self.list_layout.addWidget(item)
        self.list_layout.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)
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

        hint = QLabel("Mô-đun cấu hình ML, SL/TP động và quản lý đòn bẩy cho chiến lược.")
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

        head = QLabel("  Data Pool  ·  tạo & chỉnh sửa dữ liệu →")
        head.setFixedHeight(28)
        head.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; background: transparent; padding-left: 8px;")
        lay.addWidget(head)

        hint = QLabel("Mỗi bộ dữ liệu bao gồm tập Symbol và khoảng ngày bắt đầu/kết thúc backtest.")
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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
            self.lbl_status.setText(f"Đã cập nhật bộ dữ liệu “{item['ten']}”.")

    def _xoa_bo_du_lieu(self, did):
        self.bo_du_lieu = [x for x in self.bo_du_lieu if x.get("id") != did]
        luu_bo_du_lieu(self.bo_du_lieu)
        self._render_data_pool()
        self.lbl_status.setText("Đã xóa bộ dữ liệu.")

    def _btn_style(self, bg, text_color="#FFFFFF"):
        return (
            f"QPushButton {{ background-color: {bg}; color: {text_color}; font-weight: bold; padding: 7px 14px; border-radius: 5px; border: none; }}"
            f"QPushButton:disabled {{ background-color: {Theme.GRID}; color: {Theme.TEXT_SUB}; }}"
        )

    def _filter_indicators(self, text):
        text = text.lower()
        for cat_lbl, keys in self.category_headers:
            cat_visible = False
            for key in keys:
                item = self.indicator_items[key]
                match = text in key.lower() or text in INDICATOR_DESC.get(key, "").lower()
                item.setVisible(match)
                if match:
                    cat_visible = True
            cat_lbl.setVisible(cat_visible)

    def _select_quick(self, key):

        self._on_drop("5m", key)


    def _build_config_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Theme.BG}; }}")

        page = QWidget()
        page.setStyleSheet(f"background: {Theme.BG};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)


        self.lbl_builder_title = QLabel("Kéo chỉ báo từ trái thả vào cột khung thời gian → bấm '▶ Chạy'")
        self.lbl_builder_title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-weight: bold; font-size: 13px;")
        lay.addWidget(self.lbl_builder_title)


        settings_panel = QFrame()
        settings_panel.setStyleSheet(
            f"QFrame {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; border-radius: 6px; }}"
        )
        quick = QHBoxLayout(settings_panel)
        quick.setContentsMargins(12, 6, 12, 6)
        quick.setSpacing(8)

        quick.addWidget(self._lbl("Logic:"))
        self.cb_logic = QComboBox()
        self.cb_logic.addItem("AND", "and")
        self.cb_logic.addItem("OR", "or")
        self.cb_logic.setStyleSheet(_combo_css() + "QComboBox { min-width: 85px; }")
        self.cb_logic.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.cb_logic.setToolTip(
            "Cách kết hợp các chỉ báo TRIGGER:\n"
            "• AND: mọi trigger phải đồng thuận mới vào lệnh.\n"
            "• OR: bất kỳ trigger cho tín hiệu là vào.\n"
            "(Filter luôn AND — phải cùng chiều thì mới cho lệnh.)"
        )
        quick.addWidget(self.cb_logic)

        quick.addWidget(self._lbl("Giữ nến:"))
        self.sp_persist = QSpinBox()
        self.sp_persist.setRange(1, 200)
        self.sp_persist.setValue(1)
        self.sp_persist.setStyleSheet(self._spin_css() + "QSpinBox { min-width: 80px; }")
        self.sp_persist.setToolTip(
            "Signal Persistence: tín hiệu trigger còn hiệu lực trong N nến cơ sở 1m sau khi xuất hiện\n"
            "(giúp khớp đa khung khi các trigger không cắt đúng cùng 1 nến). 1 = tức thời."
        )
        self.sp_persist.setFixedHeight(22)
        quick.addWidget(self.sp_persist)

        quick.addWidget(self._lbl("SL %:"))
        self.sp_sl = QDoubleSpinBox()
        self.sp_sl.setRange(0.1, 50.0)
        self.sp_sl.setDecimals(2)
        self.sp_sl.setSingleStep(0.1)
        self.sp_sl.setValue(2.5)
        self.sp_sl.setStyleSheet(self._spin_css() + "QDoubleSpinBox { min-width: 100px; }")
        self.sp_sl.setFixedHeight(22)
        quick.addWidget(self.sp_sl)

        quick.addWidget(self._lbl("RR:"))
        self.sp_rr = QDoubleSpinBox()
        self.sp_rr.setRange(0.1, 20.0)
        self.sp_rr.setDecimals(2)
        self.sp_rr.setSingleStep(0.1)
        self.sp_rr.setValue(2.0)
        self.sp_rr.setStyleSheet(self._spin_css() + "QDoubleSpinBox { min-width: 100px; }")
        self.sp_rr.setFixedHeight(22)
        quick.addWidget(self.sp_rr)

        quick.addStretch()


        self.btn_run = QPushButton("▶ Chạy")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.WIN}; color: #FFFFFF; font-weight: bold; padding: 6px 14px; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background-color: #0c9e64; }}"
            f"QPushButton:disabled {{ background-color: {Theme.GRID}; color: {Theme.TEXT_SUB}; }}"
        )
        self.btn_run.clicked.connect(self.chay)
        quick.addWidget(self.btn_run)

        self.btn_save = QPushButton("💾 Lưu")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(self._btn_style(Theme.ENTRY))
        self.btn_save.clicked.connect(self.luu_chien_luoc_tay)
        quick.addWidget(self.btn_save)

        self.btn_detail_top = QPushButton("🔍 Chi tiết")
        self.btn_detail_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail_top.setStyleSheet(self._btn_style(Theme.ACCENT, text_color="#131722"))
        self.btn_detail_top.clicked.connect(self.xem_chi_tiet)
        quick.addWidget(self.btn_detail_top)

        btn_clear = QPushButton("Xóa hết")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {Theme.LOSS}; border: 1px solid {Theme.LOSS}; font-weight: bold; padding: 5px 14px; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {Theme.LOSS}1a; }}"
            f"QPushButton:disabled {{ background-color: {Theme.GRID}; color: {Theme.TEXT_SUB}; }}"
        )
        btn_clear.clicked.connect(self._xoa_het)
        quick.addWidget(btn_clear)

        lay.addWidget(settings_panel)


        self.data_zone = DataDropZone()
        self.data_zone.setToolTip("Kéo 1 bộ dữ liệu (Symbol + khoảng ngày) vào đây để backtest trên dữ liệu đó. Để trống = dùng Symbol/ngày trong config.")
        self.data_zone.data_dropped.connect(self._on_data_drop)
        lay.addWidget(self.data_zone)
        self._render_data_zone()


        self.module_zone = ModuleDropZone()
        self.module_zone.setToolTip("Kéo các mô-đun (Regime ML / SL-TP động / Đòn bẩy động) vào khung này để bật.")
        self.module_zone.module_dropped.connect(self._on_module_drop)
        lay.addWidget(self.module_zone)
        self._render_modules()


        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"background: {Theme.BG}; border: 1px solid {Theme.BORDER}; border-radius: 6px;")
        grid_lay = QHBoxLayout(grid_frame)
        grid_lay.setContentsMargins(6, 6, 6, 6)
        grid_lay.setSpacing(6)

        self.tf_columns = {}
        for tf in ALL_TIMEFRAMES:
            col = ThuCongTimeframeColumn(tf)
            col.indicator_dropped.connect(self._on_drop)
            self.tf_columns[tf] = col
            grid_lay.addWidget(col, 1)
        lay.addWidget(grid_frame)


        self.lbl_strategy_desc = QLabel(
            "Mỗi cột là 1 khung; đặt được nhiều chỉ báo, và cùng 1 chỉ báo có thể đặt ở nhiều khung. "
            "Chiến lược chỉ vào lệnh khi các chỉ báo đồng thuận — người dùng tự nhập ngưỡng tối ưu cho từng chỉ báo/khung."
        )
        self.lbl_strategy_desc.setWordWrap(True)
        self.lbl_strategy_desc.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(self.lbl_strategy_desc)


        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        lay.addWidget(self.cards_container)

        self.empty_lbl = QLabel("Chưa có chỉ báo nào — kéo thả hoặc click chỉ báo từ thanh bên để thêm.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet(f"color: #555861; font-size: 12px; background: transparent; padding: 24px 0;")
        self.cards_layout.addWidget(self.empty_lbl)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    def _lbl(self, txt):
        l = QLabel(txt)
        l.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        return l

    def _spin_css(self):
        return (
            f"QAbstractSpinBox {{ background-color: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 3px 20px 3px 8px; font-size: 12px; }}"
            f"QAbstractSpinBox:hover {{ border: 1px solid {Theme.ACCENT}; }}"
            f"QAbstractSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 16px; border-left: none; border-bottom: none; background: transparent; border-top-right-radius: 4px; }}"
            f"QAbstractSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 16px; border-left: none; border-top: none; background: transparent; border-bottom-right-radius: 4px; }}"
            f"QAbstractSpinBox::up-button:hover {{ background: {Theme.GRID}; }}"
            f"QAbstractSpinBox::down-button:hover {{ background: {Theme.GRID}; }}"
            f"QAbstractSpinBox::up-arrow {{ image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-bottom: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QAbstractSpinBox::down-arrow {{ image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QAbstractSpinBox::up-arrow:hover {{ border-bottom-color: {Theme.TEXT_MAIN}; }}"
            f"QAbstractSpinBox::down-arrow:hover {{ border-top-color: {Theme.TEXT_MAIN}; }}"
        )


    def _save_cards_to_specs(self):
        """Đồng bộ giá trị từ các widget trên thẻ cấu hình ngược lại self.combo_specs."""
        for card in self.cards:
            if 0 <= card.idx < len(self.combo_specs):
                self.combo_specs[card.idx].update(card.to_spec())

    def _on_drop(self, tf, key_or_mime):
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi sửa chỉ báo.")
            return

        self._save_cards_to_specs()

        if key_or_mime.startswith("move:"):
            parts = key_or_mime.split(":")
            if len(parts) >= 3:
                idx = int(parts[1])
                if 0 <= idx < len(self.combo_specs):
                    self.combo_specs[idx]["tf"] = tf
                    self._render_grid_and_cards()
                    self.lbl_status.setText(f"Đã di chuyển chỉ báo {self.combo_specs[idx]['key'].upper()} sang khung {tf}.")
        else:
            key = key_or_mime
            itype = _loai_chi_bao(key)
            spec = {
                "key": key,
                "type": itype,
                "tf": tf,
                "role": "trigger",
                "params": _tham_so_mac_dinh(key),
                "thresholds": _nguong_mac_dinh(key, itype),
            }
            self.combo_specs.append(spec)
            self._render_grid_and_cards()
            self.lbl_status.setText(f"Đã thêm chỉ báo {key.upper()} vào khung {tf}.")

    def _remove_chip(self, idx):
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi sửa chỉ báo.")
            return
        self._save_cards_to_specs()
        if 0 <= idx < len(self.combo_specs):
            key = self.combo_specs[idx]["key"]
            del self.combo_specs[idx]
            self._render_grid_and_cards()
            self.lbl_status.setText(f"Đã xóa chỉ báo {key.upper()}.")

    def _toggle_role(self, idx):
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi sửa chỉ báo.")
            return
        self._save_cards_to_specs()
        if 0 <= idx < len(self.combo_specs):
            cur = self.combo_specs[idx].get("role", "trigger")
            new_role = "filter" if cur == "trigger" else "trigger"
            self.combo_specs[idx]["role"] = new_role
            self._render_grid_and_cards()
            self.lbl_status.setText(f"Đã chuyển vai trò của {self.combo_specs[idx]['key'].upper()} thành {new_role.upper()}.")

    def _xoa_het(self):
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi sửa chỉ báo.")
            return
        self.combo_specs = []
        self._render_grid_and_cards()
        self.lbl_status.setText("Đã xóa hết chỉ báo.")

    def _render_grid_and_cards(self):

        by_tf = {tf: [] for tf in ALL_TIMEFRAMES}
        for i, spec in enumerate(self.combo_specs):
            by_tf.setdefault(spec["tf"], []).append((i, spec))

        for tf, col in self.tf_columns.items():
            chips = [ThuCongGridChip(i, spec, self) for i, spec in by_tf.get(tf, [])]
            col.set_chips(chips)


        for card in list(self.cards):
            card.setParent(None)
            card.deleteLater()
        self.cards = []

        for i, spec in enumerate(self.combo_specs):
            card = TheChiBao(i, spec)
            card.removed.connect(self._remove_chip)
            self.cards.append(card)
            self.cards_layout.addWidget(card)

        self.empty_lbl.setVisible(len(self.combo_specs) == 0)


    def _build_config(self):
        """Dựng config best_params (s0..,logic,risk) từ các thẻ — None nếu chưa có thẻ."""
        self._save_cards_to_specs()
        if not self.combo_specs:
            return None
        config = {}
        for i, spec in enumerate(self.combo_specs):
            config[f"s{i}"] = spec
        config["logic"] = {
            "mode": self.cb_logic.currentData(),
            "persistence": int(self.sp_persist.value()),
        }
        config["risk"] = {
            "base_sl": float(self.sp_sl.value()),
            "rr": float(self.sp_rr.value()),
        }
        return config

    def chay(self):
        """Dựng chiến lược từ tham số tay rồi backtest, tự động nhảy sang Biểu đồ nến hiển thị kết quả."""
        if self._worker is not None and self._worker.isRunning():
            return
        config = self._build_config()
        if config is None:
            self.lbl_status.setText("Chưa có chỉ báo nào — hãy thêm ít nhất 1 chỉ báo.")
            return
        co_trigger = any(spec.get("role", "trigger") == "trigger" for spec in self.combo_specs)
        if not co_trigger:
            self.lbl_status.setText("Cần ít nhất 1 chỉ báo vai trò Trigger để có tín hiệu vào lệnh.")
            return

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Đang chạy...")
        ds_txt = f" · dữ liệu: {self.active_dataset['ten']}" if self.active_dataset else ""
        self.lbl_status.setText(f"Đang backtest chiến lược thủ công{ds_txt}...")

        self._worker = BacktestWorker(config, dataset=self.active_dataset)
        self._worker.finished.connect(self._on_done_and_navigate)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done_and_navigate(self, trades, dict_dfs):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶ Chạy")
        self.lbl_status.setText("Hoàn tất — đã chuyển kết quả sang Biểu đồ nến.")

        config = self._build_config()
        if self.phien is not None:

            self.phien.set_active_dataset(self.active_dataset, im_lang=True)
            result = {
                "best_params": config,
                "combo_label": "Chỉ báo thủ công"
            }
            self.phien.set_active_strategy(result)


            self.phien.yeu_cau_xem("vectorized")


            parent = self.parent()
            shell = None
            while parent is not None:
                if hasattr(parent, "_man_con"):
                    shell = parent
                    break
                parent = parent.parent()

            if shell is not None:
                man_nen = shell._man_con.get("vectorized")
                if man_nen is not None:
                    man_nen.on_backtest_finished(trades, dict_dfs)

    def _on_error(self, err):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶ Chạy")
        self.lbl_status.setText(f"Lỗi: {err}")


    def gan_phien(self, phien):
        """Nhận bus phiên (không bắt buộc dùng) — màn này độc lập, chỉ lưu tham chiếu."""
        self.phien = phien


        parent = self.parent()
        shell = None
        while parent is not None:
            if hasattr(parent, "_nap_thu_vien"):
                shell = parent
                break
            parent = parent.parent()

        if shell is not None:
            original_mo = shell._mo_da_luu

            def custom_mo():
                ten = shell._ten_da_chon()
                if not ten:
                    return
                from toi_uu_hoa.thu_vien import doc_chien_luoc
                payload = doc_chien_luoc(ten) or {}
                result = payload.get("result") or {}
                if not result:
                    shell.lbl_status.setText(f"✗ Không đọc được: {ten}")
                    return

                is_manual = result.get("nguon") == "thu_cong"
                if is_manual:
                    shell.di_toi_man("thu_cong")
                    self.nap_chien_luoc_tu_thu_vien(result)
                    shell.lbl_status.setText(f"Đã mở từ thư viện vào Chỉ báo thủ công: {ten}")
                else:
                    original_mo()

            shell._mo_da_luu = custom_mo


            from PyQt6.QtWidgets import QPushButton
            buttons = shell.findChildren(QPushButton)
            for btn in buttons:
                if btn.text() == "Mở":
                    try:
                        btn.clicked.disconnect()
                    except Exception:
                        pass
                    btn.clicked.connect(custom_mo)

    def nap_chien_luoc_tu_thu_vien(self, result):
        """Nạp cấu hình chiến lược từ thư viện vào giao diện Chỉ báo thủ công"""

        combo = result.get("combo", [])
        self.combo_specs = []
        for c in combo:
            self.combo_specs.append({
                "key": c.get("key"),
                "tf": c.get("tf"),
                "role": c.get("role", "trigger"),
                "type": c.get("type", "trend"),
                "params": c.get("params", {}),
                "thresholds": c.get("thresholds", {}),
            })


        logic = result.get("logic", {})
        if isinstance(logic, dict):
            mode = logic.get("mode", "and")
            persist = logic.get("persistence", 1)
        else:
            mode = logic
            persist = 1

        idx_logic = self.cb_logic.findData(mode)
        if idx_logic >= 0:
            self.cb_logic.setCurrentIndex(idx_logic)
        self.sp_persist.setValue(int(persist))


        best_params = result.get("best_params", {})
        risk = best_params.get("risk", {})
        self.sp_sl.setValue(float(risk.get("base_sl", 2.5)))
        self.sp_rr.setValue(float(risk.get("rr", 2.0)))


        self._render_grid_and_cards()
        self.lbl_status.setText("Đã nạp cấu hình chiến lược.")

    def xem_chi_tiet(self):
        """Gửi chiến lược hiện tại sang màn Biểu đồ nến để xem chi tiết đầy đủ."""
        config = self._build_config()
        if config is None:
            self.lbl_status.setText("Chưa có chỉ báo nào để xem chi tiết.")
            return
        co_trigger = any(spec.get("role", "trigger") == "trigger" for spec in self.combo_specs)
        if not co_trigger:
            self.lbl_status.setText("Cần ít nhất 1 chỉ báo vai trò Trigger.")
            return

        if self.phien is not None:
            self.phien.set_active_dataset(self.active_dataset, im_lang=True)
            result = {
                "best_params": config,
                "combo_label": "Chỉ báo thủ công"
            }
            self.phien.set_active_strategy(result)
            self.phien.yeu_cau_xem("vectorized")
            self.lbl_status.setText("✓ Đã gửi cấu hình sang Biểu đồ nến.")
        else:
            self.lbl_status.setText("⚠ Không tìm thấy phiên kết nối.")


    def _on_data_drop(self, mime):
        if not mime.startswith("data:"):
            return
        did = mime.split(":", 1)[1]
        item = next((x for x in self.bo_du_lieu if x.get("id") == did), None)
        if item is None:
            return
        self.active_dataset = dict(item)
        self._render_data_zone()
        self.lbl_status.setText(f"Sẽ chạy backtest trên bộ dữ liệu “{item.get('ten', '')}” ({len(item.get('symbols', []))} symbol).")

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

    def _on_module_drop(self, mime):
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi đổi mô-đun.")
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
        if self._worker is not None and self._worker.isRunning():
            self.lbl_status.setText("⚠ Vui lòng chờ backtest xong trước khi đổi mô-đun.")
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
        self.lbl_status.setText(f"{MODULE_DEFS[mid]['name']}: {'BẬT' if on else 'TẮT'} (dùng chung optimizer + backtest)")

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

    def _build_statusbar(self, parent_layout):
        bar = QFrame()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background: {Theme.CARD}; border-top: 1px solid {Theme.BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        self.lbl_status = QLabel("Sẵn sàng.")
        self.lbl_status.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        lay.addWidget(self.lbl_status)
        lay.addStretch()

        self.btn_detail = QPushButton("Xem chi tiết ↗")
        self.btn_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.ACCENT}; color: #131722; font-weight: bold; padding: 2px 10px; border-radius: 4px; border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {Theme.ACCENT}dd; }}"
        )
        self.btn_detail.clicked.connect(self.xem_chi_tiet)
        lay.addWidget(self.btn_detail)

        parent_layout.addWidget(bar)

    def luu_chien_luoc_tay(self):
        """Lưu cấu hình chiến lược hiện tại vào Thư viện (tab 'Đã lưu')"""
        config = self._build_config()
        if config is None:
            self.lbl_status.setText("Chưa có chỉ báo nào để lưu.")
            return


        combo = []
        for spec in self.combo_specs:
            combo.append({
                "key": spec["key"],
                "tf": spec["tf"],
                "role": spec.get("role", "trigger"),
                "type": spec.get("type", "trend"),
                "params": spec.get("params", {}),
                "thresholds": spec.get("thresholds", {}),
            })

        combo_label = " + ".join([f"{c['key'].upper()}@{c['tf']}" for c in combo])


        result = {
            "combo": combo,
            "combo_label": combo_label,
            "best_params": config,
            "logic": config.get("logic", {"mode": self.cb_logic.currentData(), "persistence": int(self.sp_persist.value())}),
            "oos_metrics": {
                "sharpe_ratio": 1.0,
                "sortino_ratio": 1.1,
                "win_rate": 50.0,
                "max_drawdown_pct": 10.0,
                "profit_factor": 1.1,
                "total_trades": 20,
            },
            "oos_is_ratio": 1.0,
            "nguon": "thu_cong",
        }

        try:
            from toi_uu_hoa.thu_vien import luu_chien_luoc
            ten = luu_chien_luoc(result)
        except Exception as e:
            self.lbl_status.setText(f"✗ Lưu thất bại: {e}")
            return

        self.lbl_status.setText(f"✓ Đã lưu vào thư viện: {ten}")


        parent = self.parent()
        shell = None
        while parent is not None:
            if hasattr(parent, "_nap_thu_vien"):
                shell = parent
                break
            parent = parent.parent()

        if shell is not None:
            shell._nap_thu_vien()
            if self.phien is None and getattr(shell, "phien", None) is not None:
                self.phien = shell.phien


        if self.phien is not None:
            self.phien.yeu_cau_xem("da_luu")


        self.btn_save.setText("✔️ Đã lưu")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_save.setText("💾 Lưu"))
