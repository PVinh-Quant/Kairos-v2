"""toi_uu/data_pool.py — Hộp thoại quản lý bộ dữ liệu (Data Pool) cho màn Tối ưu."""
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
class DataPoolDialog(QDialog):
    """Hộp thoại tạo/sửa 1 bộ dữ liệu: tên + chọn nhiều Symbol + khoảng ngày.
    Thiết kế modern dark-glass: smooth hover, search/filter, select-all, badge đếm."""

    _DIALOG_CSS = f"""
        QDialog {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #161820, stop:1 #0e0f13);
            border: 1px solid rgba(200,170,110,0.18);
            border-radius: 12px;
        }}
        QLabel {{ color: {Theme.TEXT_MAIN}; background: transparent; }}
    """
    _INPUT_CSS = f"""
        QLineEdit {{
            background: rgba(14,14,14,0.85);
            color: {Theme.TEXT_MAIN};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
            font-family: 'Segoe UI';
            selection-background-color: rgba(200,170,110,0.3);
        }}
        QLineEdit:focus {{
            border: 1px solid {Theme.ACCENT};
        }}
        QLineEdit:hover {{
            border: 1px solid rgba(200,170,110,0.45);
        }}
    """
    _LIST_CSS = f"""
        QListWidget {{
            background: rgba(14,14,14,0.7);
            color: {Theme.TEXT_MAIN};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 4px;
            outline: none;
            font-family: 'Segoe UI';
            font-size: 12px;
        }}
        QListWidget::item {{
            padding: 6px 10px;
            border-radius: 4px;
            margin: 1px 2px;
        }}
        QListWidget::item:hover {{
            background: rgba(200,170,110,0.08);
        }}
        QListWidget::item:selected {{
            background: rgba(200,170,110,0.12);
        }}
        QListWidget::indicator {{
            width: 16px; height: 16px;
            border: 2px solid {Theme.BORDER};
            border-radius: 4px;
            background: transparent;
        }}
        QListWidget::indicator:hover {{
            border-color: {Theme.ACCENT};
        }}
        QListWidget::indicator:checked {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {Theme.ACCENT}, stop:1 #a08040);
            border-color: {Theme.ACCENT};
            image: none;
        }}
        QScrollBar:vertical {{
            width: 0px;
            background: transparent;
        }}
    """
    _DATE_CSS = f"""
        QDateEdit {{
            background: rgba(14,14,14,0.85);
            color: {Theme.TEXT_MAIN};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 7px 10px;
            font-size: 12px;
            font-family: 'Segoe UI';
        }}
        QDateEdit:hover {{
            border: 1px solid rgba(200,170,110,0.45);
        }}
        QDateEdit:focus {{
            border: 1px solid {Theme.ACCENT};
        }}
        QDateEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: right center;
            width: 26px;
            border: none;
            border-left: 1px solid {Theme.BORDER};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: transparent;
        }}
        QDateEdit::down-arrow {{
            width: 10px; height: 10px;
        }}
    """
    _CALENDAR_CSS = f"""
        QCalendarWidget {{
            background: #14161c;
            border: 1px solid rgba(200,170,110,0.2);
            border-radius: 8px;
        }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #1c1e26, stop:1 #14161c);
            border-bottom: 1px solid {Theme.BORDER};
            padding: 4px 8px;
            min-height: 36px;
        }}
        QCalendarWidget QToolButton {{
            color: {Theme.TEXT_MAIN};
            background: transparent;
            border: none;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 9pt;
            font-family: 'Segoe UI';
            font-weight: bold;
        }}
        QCalendarWidget QToolButton:hover {{
            background: rgba(200,170,110,0.12);
            color: {Theme.ACCENT};
        }}
        QCalendarWidget QToolButton:pressed {{
            background: rgba(200,170,110,0.2);
        }}
        QCalendarWidget QToolButton#qt_calendar_prevmonth,
        QCalendarWidget QToolButton#qt_calendar_nextmonth {{
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            border-radius: 14px;
            font-size: 11pt;
            qproperty-text: '';
        }}
        QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
        QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {{
            background: rgba(200,170,110,0.15);
        }}
        QCalendarWidget QMenu {{
            background: #1a1c24;
            color: {Theme.TEXT_MAIN};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 4px;
            font-family: 'Segoe UI';
        }}
        QCalendarWidget QMenu::item {{
            padding: 6px 16px;
            border-radius: 4px;
        }}
        QCalendarWidget QMenu::item:selected {{
            background: rgba(200,170,110,0.18);
            color: {Theme.ACCENT};
        }}
        QCalendarWidget QSpinBox {{
            background: #1a1c24;
            color: {Theme.TEXT_MAIN};
            border: 1px solid {Theme.BORDER};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 9pt;
            font-family: 'Segoe UI';
            selection-background-color: rgba(200,170,110,0.3);
        }}
        QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button {{
            width: 16px;
            border: none;
            background: transparent;
        }}
        QCalendarWidget QSpinBox::up-button:hover, QCalendarWidget QSpinBox::down-button:hover {{
            background: rgba(200,170,110,0.1);
        }}
        QCalendarWidget QAbstractItemView {{
            background: #14161c;
            color: {Theme.TEXT_MAIN};
            selection-background-color: {Theme.ACCENT};
            selection-color: #0e0e0e;
            border: none;
            outline: none;
            font-size: 8pt;
            font-family: 'Segoe UI';
        }}
        QCalendarWidget QAbstractItemView::item {{
            padding: 0px;
            margin: 0px;
        }}
        QCalendarWidget QAbstractItemView::item:hover {{
            background: rgba(200,170,110,0.10);
            border-radius: 0px;
        }}
        QCalendarWidget QAbstractItemView::item:selected {{
            background: {Theme.ACCENT};
            color: #0e0e0e;
            border-radius: 0px;
        }}
    """

    def __init__(self, item=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✦  Data Pool mới" if item is None else "✎  Sửa bộ dữ liệu")
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self.setStyleSheet(self._DIALOG_CSS)
        item = item or {}
        self._result = None
        self._all_symbols = liet_ke_symbol_co_san()

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(14)

                       
        header = QLabel("Tạo bộ dữ liệu mới" if not item.get("ten") else "Chỉnh sửa bộ dữ liệu")
        header.setStyleSheet(
            f"color: {Theme.TEXT_MAIN}; font-size: 16px; font-weight: bold; "
            f"font-family: 'Segoe UI'; background: transparent; padding-bottom: 2px;"
        )
        v.addWidget(header)

                               
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"stop:0 {Theme.ACCENT}, stop:0.5 rgba(200,170,110,0.3), stop:1 transparent);"
        )
        v.addWidget(sep)

                              
        v.addWidget(self._lbl("TÊN BỘ DỮ LIỆU"))
        self.ed_ten = QLineEdit(item.get("ten", ""))
        self.ed_ten.setPlaceholderText("VD: BTC+ETH Q1-Q2 2026")
        self.ed_ten.setStyleSheet(self._INPUT_CSS)
        v.addWidget(self.ed_ten)

                                             
        sym_header = QHBoxLayout()
        sym_header.setSpacing(8)
        sym_header.addWidget(self._lbl("CHỌN SYMBOL"))
        self.lbl_count = QLabel("0")
        self.lbl_count.setFixedSize(28, 18)
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setStyleSheet(
            f"color: {Theme.ACCENT}; background: rgba(200,170,110,0.14); "
            f"border-radius: 9px; font-size: 10px; font-weight: bold; "
            f"font-family: 'Segoe UI';"
        )
        sym_header.addWidget(self.lbl_count)
        sym_header.addStretch()

                                         
        btn_all = QPushButton("Chọn tất cả")
        btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_all.setStyleSheet(self._mini_btn_css())
        btn_all.clicked.connect(lambda: self._toggle_all(True))
        btn_none = QPushButton("Bỏ chọn")
        btn_none.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_none.setStyleSheet(self._mini_btn_css())
        btn_none.clicked.connect(lambda: self._toggle_all(False))
        sym_header.addWidget(btn_all)
        sym_header.addWidget(btn_none)
        v.addLayout(sym_header)

                                     
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("🔍  Tìm symbol...")
        self.ed_search.setStyleSheet(
            self._INPUT_CSS.replace("padding: 8px 12px", "padding: 6px 10px")
            .replace("font-size: 13px", "font-size: 11px")
        )
        self.ed_search.textChanged.connect(self._filter_symbols)
        v.addWidget(self.ed_search)

                                
        self.list_sym = QListWidget()
        self.list_sym.setMinimumHeight(140)
        self.list_sym.setMaximumHeight(220)
        self.list_sym.setStyleSheet(self._LIST_CSS)
        self.list_sym.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_sym.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_sym.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        chosen = set(item.get("symbols", []))
        for sym in self._all_symbols:
            it = QListWidgetItem(sym)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if sym in chosen else Qt.CheckState.Unchecked)
            self.list_sym.addItem(it)
        self.list_sym.itemChanged.connect(self._update_count)
        self.list_sym.itemClicked.connect(self._on_item_clicked)
        v.addWidget(self.list_sym)
        self._update_count()

                           
        cfg = {}
        try:
            from utils.doc_cau_hinh import lay_cau_hinh_ao
            cfg = lay_cau_hinh_ao() or {}
        except Exception:                
            cfg = {}

        row = QHBoxLayout()
        row.setSpacing(12)
        box1 = QVBoxLayout(); box1.setSpacing(4)
        box1.addWidget(self._lbl("TỪ NGÀY"))
        self.de_tu = self._mk_date(item.get("tu_ngay") or cfg.get("ngay_bat_dau") or "2025-01-01")
        box1.addWidget(self.de_tu)
        box2 = QVBoxLayout(); box2.setSpacing(4)
        box2.addWidget(self._lbl("ĐẾN NGÀY"))
        self.de_den = self._mk_date(item.get("den_ngay") or cfg.get("ngay_ket_thuc") or "2026-06-15")
        box2.addWidget(self.de_den)
        row.addLayout(box1, 1)
        row.addLayout(box2, 1)
        v.addLayout(row)

                                      
        v.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_ok = QPushButton("  ✓  Xác nhận  ")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Theme.ACCENT}, stop:1 #a08040);
                color: #0e0e0e;
                border: none;
                border-radius: 6px;
                padding: 8px 28px;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d4b878, stop:1 #b89850);
            }}
            QPushButton:pressed {{
                background: #9a7a30;
            }}
        """)
        btn_ok.clicked.connect(self._on_accept)

        btn_cancel = QPushButton("  Huỷ  ")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SUB};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px 22px;
                font-size: 12px;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_MAIN};
                border-color: {Theme.TEXT_SUB};
                background: rgba(255,255,255,0.03);
            }}
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        v.addLayout(btn_row)

                   
    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet(
            f"color: {Theme.TEXT_SUB}; font-size: 10px; font-weight: bold; "
            f"font-family: 'Segoe UI'; letter-spacing: 1px; background: transparent;"
        )
        return l

    @staticmethod
    def _mini_btn_css():
        return (
            f"QPushButton {{ color: {Theme.TEXT_SUB}; background: transparent; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 10px; font-family: 'Segoe UI'; }}"
            f"QPushButton:hover {{ color: {Theme.ACCENT}; border-color: {Theme.ACCENT}; "
            f"background: rgba(200,170,110,0.06); }}"
        )

    def _mk_date(self, s):
        from PyQt6.QtWidgets import QCalendarWidget
        from PyQt6.QtGui import QTextCharFormat
        de = QDateEdit()
        de.setDisplayFormat("yyyy-MM-dd")
        de.setCalendarPopup(True)
        de.setStyleSheet(self._DATE_CSS)
        d = QDate.fromString(str(s), "yyyy-MM-dd")
        de.setDate(d if d.isValid() else QDate(2026, 1, 1))

                                    
        cal = de.calendarWidget()
        if cal is not None:
            cal.setStyleSheet(self._CALENDAR_CSS)
            cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
            cal.setFixedSize(320, 260)

                                               
            hdr_fmt = QTextCharFormat()
            hdr_fmt.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            hdr_fmt.setForeground(QColor(Theme.ACCENT))
            hdr_fmt.setBackground(QColor("#1a1c24"))
            cal.setHeaderTextFormat(hdr_fmt)

                              
            normal_fmt = QTextCharFormat()
            normal_fmt.setFont(QFont("Segoe UI", 9))
            normal_fmt.setForeground(QColor(Theme.TEXT_MAIN))
            normal_fmt.setBackground(QColor("transparent"))

                                                   
            weekend_fmt = QTextCharFormat()
            weekend_fmt.setFont(QFont("Segoe UI", 9))
            weekend_fmt.setForeground(QColor("#8a7050"))
            weekend_fmt.setBackground(QColor("transparent"))
            cal.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_fmt)
            cal.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_fmt)
            for day in [Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday,
                        Qt.DayOfWeek.Wednesday, Qt.DayOfWeek.Thursday,
                        Qt.DayOfWeek.Friday]:
                cal.setWeekdayTextFormat(day, normal_fmt)

        return de

    def _on_item_clicked(self, item):
        """Click bất kỳ đâu trên dòng → toggle checkbox (không cần nhấn đúng vào ô checkbox)."""
        if item.checkState() == Qt.CheckState.Checked:
            item.setCheckState(Qt.CheckState.Unchecked)
        else:
            item.setCheckState(Qt.CheckState.Checked)

    def _toggle_all(self, checked):
        """Chọn tất cả / bỏ chọn — chỉ ảnh hưởng item đang hiển thị (theo filter)."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_sym.count()):
            it = self.list_sym.item(i)
            if not it.isHidden():
                it.setCheckState(state)

    def _filter_symbols(self, text):
        """Lọc symbol theo từ khoá tìm kiếm (case-insensitive)."""
        needle = text.strip().upper()
        for i in range(self.list_sym.count()):
            it = self.list_sym.item(i)
            it.setHidden(needle not in it.text().upper() if needle else False)

    def _update_count(self):
        """Cập nhật badge đếm số symbol đã chọn."""
        n = sum(
            1 for i in range(self.list_sym.count())
            if self.list_sym.item(i).checkState() == Qt.CheckState.Checked
        )
        self.lbl_count.setText(str(n))
                                   
        if n > 0:
            self.lbl_count.setStyleSheet(
                f"color: #0e0e0e; background: {Theme.ACCENT}; "
                f"border-radius: 9px; font-size: 10px; font-weight: bold; font-family: 'Segoe UI';"
            )
        else:
            self.lbl_count.setStyleSheet(
                f"color: {Theme.ACCENT}; background: rgba(200,170,110,0.14); "
                f"border-radius: 9px; font-size: 10px; font-weight: bold; font-family: 'Segoe UI';"
            )

    def _on_accept(self):
        syms = []
        for i in range(self.list_sym.count()):
            it = self.list_sym.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                syms.append(it.text())
        if not syms:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Thiếu Symbol", "Hãy chọn ít nhất 1 Symbol cho bộ dữ liệu.")
            return
        ten = self.ed_ten.text().strip() or ("+".join(s.split("/")[0] for s in syms))
        tu = self.de_tu.date().toString("yyyy-MM-dd")
        den = self.de_den.date().toString("yyyy-MM-dd")
        if tu > den:
            tu, den = den, tu
        self._result = {"ten": ten, "symbols": syms, "tu_ngay": tu, "den_ngay": den}
        self.accept()

    def get_data(self):
        return self._result



                                                                                
                                                       
                                                                                

__all__ = ["DataPoolDialog"]
