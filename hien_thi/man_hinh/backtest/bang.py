"""backtest/bang.py — bảng kết quả theo coin + chi tiết lệnh."""
import sys, os, random, calendar, math
from datetime import datetime
import polars as pl
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QDockWidget,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QScrollArea,
    QGridLayout,
    QToolBar,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QPen,
    QBrush,
    QPolygonF,
    QPainterPath,
    QLinearGradient,
    QFontMetrics,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
)
from .dinh_nghia import *
class CoinContentWidget(QWidget):

    coin_clicked = pyqtSignal(str)

    def __init__(self, data=[]):
        """Khởi tạo widget danh sách coin với tên, số lệnh và PnL từng coin."""
        super().__init__()
        self.data = data
        self.row_height = 40
        self.setMinimumHeight(len(data) * self.row_height)
        self.selected_coin = None                                                 

    def update_data(self, data, selected_coin=None):
        """Cập nhật danh sách coin và highlight coin đang được lọc."""
        self.data = data or []
        self.selected_coin = selected_coin                        

                                                
        new_height = len(self.data) * self.row_height
        if self.minimumHeight() != new_height:
            self.setMinimumHeight(new_height)

        self.update()

    def mousePressEvent(self, event):
        """Phát signal tên coin khi người dùng click vào hàng tương ứng."""
        if self.row_height == 0:
            return
        index = int(event.position().y() // self.row_height)

        if 0 <= index < len(self.data):
                                        
            coin_name = self.data[index]["pair"]
            self.coin_clicked.emit(coin_name)

    def paintEvent(self, event):
        """Vẽ danh sách coin với tên, số lệnh, PnL và highlight dòng được chọn."""
        if not hasattr(self, "data") or not self.data:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(CARD_BG))
            painter.setPen(QColor(TEXT_SUB))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No Data Available"
            )
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(CARD_BG))
        w = self.width()

        for i, item in enumerate(self.data):
            y = i * self.row_height

                                                                   
            if self.selected_coin and self.selected_coin == item.get("pair"):
                painter.fillRect(QRectF(0, y, w, self.row_height), QColor("#333"))
                painter.setPen(QPen(QColor(ACCENT_COLOR), 3))
                painter.drawLine(0, int(y), 0, int(y + self.row_height))

                         
            painter.setPen(QColor(ACCENT_COLOR))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(
                10,
                int(y),
                w // 3,
                self.row_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                str(item["pair"]),
            )

                        
            count = item.get("count", 0)
            painter.setPen(QColor(TEXT_SUB))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                10,
                int(y),
                w - 20,
                self.row_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
                f"{count} lệnh",
            )

                    
            pnl = item["pnl"]
            color = QColor(COLOR_WIN) if pnl >= 0 else QColor(COLOR_LOSS)
            painter.setPen(color)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(
                w - 110,
                int(y),
                100,
                self.row_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{pnl:+.2f}$",
            )

                            
            painter.setPen(QPen(QColor(BORDER_COLOR), 1))
            painter.drawLine(
                10, int(y + self.row_height - 1), w - 10, int(y + self.row_height - 1)
            )


class CoinResultWidget(QWidget):
                       
    coin_selected_signal = pyqtSignal(str)

    def __init__(self):
        """Khởi tạo wrapper ScrollArea chứa CoinContentWidget và relay signal."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"background: {CARD_BG}; border: none;")
        self.scroll.verticalScrollBar().setStyleSheet(
            f"QScrollBar:vertical {{ background: {CARD_BG}; width: 6px; }} QScrollBar::handle:vertical {{ background: #333; border-radius: 3px; }}"
        )

        self.content = CoinContentWidget([])
                               
        self.content.coin_clicked.connect(self.on_coin_clicked)

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def on_coin_clicked(self, coin_name):
        """Relay signal khi CoinContentWidget bên trong phát tín hiệu click."""
        self.coin_selected_signal.emit(coin_name)

    def update_data(self, df: pl.DataFrame | None = None, current_filter_coin=None):
        """Tổng hợp PnL theo coin từ DataFrame và cập nhật danh sách hiển thị."""
                                                      
        if df is None or df.is_empty():
            self.content.update_data([], current_filter_coin)
            return

        try:
            grp = (
                df.group_by("symbol")
                .agg(
                    [
                        pl.sum("pnl_usd").alias("pnl"),
                        pl.len().alias("count"),                                 
                    ]
                )
                .sort("pnl", descending=True)
            )

            data = [
                {
                    "pair": r["symbol"],
                    "pnl": float(r["pnl"]),
                    "count": int(r["count"]),
                }
                for r in grp.to_dicts()
            ]

                                                    
            self.content.update_data(data, current_filter_coin)

        except Exception as e:
            print(f"Lỗi CoinResultWidget: {e}")
            self.content.update_data([], current_filter_coin)


                                                                                   
                                      
                                                                                   
class _EmptyHintTable(QTableWidget):
    """Bảng hiện 'No Data Available' căn giữa khi chưa có dòng nào.

    Khi backtest chưa chạy, bảng rỗng vốn là vùng đen lớn (lúc phóng to càng thấy rõ,
    trông như lỗi). Vẽ chữ gợi ý cho đồng bộ với các panel khác cũng báo No Data.
    """

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(TEXT_SUB))
            p.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No Data Available",
            )
            p.end()


class TradeHistoryWidget(QWidget):
    def __init__(self):
        """Khởi tạo bảng lịch sử lệnh chi tiết với 8 cột và style tối."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

                                                                             
        self.table = _EmptyHintTable()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "THỜI GIAN",
                "CẶP",
                "VỊ THẾ",
                "ENTRY",
                "EXIT",
                "PNL ($)",
                "ROI (%)",
                "LÝ DO",
            ]
        )

                                 
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )                 
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )                

                                                                            
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setAlternatingRowColors(True)

                                                                         
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CARD_BG};
                border: none;
                gridline-color: {BORDER_COLOR};
                outline: 0; /* Tắt viền nét đứt/viền trắng khi focus toàn bảng */
            }}
            QHeaderView::section {{
                background-color: {BG_COLOR};
                color: {TEXT_SUB};
                padding: 5px;
                border: none;
                border-bottom: 1px solid {BORDER_COLOR};
                font-weight: bold;
                font-family: "Segoe UI";
            }}
            QTableWidget::item {{
                padding: 5px;
                border-bottom: 1px solid #1f1f1f;
                outline: none; /* Tắt outline cho từng item */
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: #333;
                border: none;
                outline: none;
                color: {TEXT_MAIN};
            }}
            QTableWidget::item:focus {{
                border: none;
                outline: none; /* Tắt viền focus khi click vào ô cụ thể */
                background-color: #333; 
            }}
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

    def update_data(self, trades=None):
        """Nạp danh sách lệnh vào bảng (tối đa 100 lệnh mới nhất, hiển thị đảo chiều)."""
        if not trades:
            self.table.setRowCount(0)
            return

                                                                                        
        display_limit = 100
        display_trades = (
            trades[-display_limit:] if len(trades) > display_limit else trades
        )
        reversed_trades = display_trades[::-1]

        self.table.setRowCount(len(reversed_trades))
        font_bold = QFont("Segoe UI", 9, QFont.Weight.Bold)

        for row, t in enumerate(reversed_trades):
                          
            item_time = QTableWidgetItem(str(t.get("time_close", "")))
            item_time.setForeground(QColor(TEXT_SUB))
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, item_time)

                         
            item_pair = QTableWidgetItem(str(t.get("symbol", "")))
            item_pair.setForeground(QColor(ACCENT_COLOR))
            item_pair.setFont(font_bold)
            item_pair.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item_pair)

                       
            side_str = str(t.get("side", "")).upper()
            item_side = QTableWidgetItem(side_str)
            if side_str in ["BUY", "LONG"]:
                item_side.setForeground(QColor("#4CAF50"))
            else:
                item_side.setForeground(QColor("#FF5252"))
            item_side.setFont(font_bold)
            item_side.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, item_side)

                      
            entry_val = t.get("entry", 0)
            self.table.setItem(row, 3, QTableWidgetItem(f"{entry_val:.4f}"))

                     
            exit_val = t.get("exit", 0)
            self.table.setItem(row, 4, QTableWidgetItem(f"{exit_val:.4f}"))

                        
            pnl = t.get("pnl_usd", 0)
            item_pnl = QTableWidgetItem(f"{pnl:+.2f}$")
            item_pnl.setFont(font_bold)
            if pnl > 0:
                item_pnl.setForeground(QColor(COLOR_WIN))
            else:
                item_pnl.setForeground(QColor(COLOR_LOSS))
            item_pnl.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 5, item_pnl)

                        
            roi = t.get("pnl_pct", 0) * 100
            item_roi = QTableWidgetItem(f"{roi:+.2f}%")
            if roi > 0:
                item_roi.setForeground(QColor(COLOR_WIN))
            else:
                item_roi.setForeground(QColor(COLOR_LOSS))
            item_roi.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 6, item_roi)

                      
            full_text = str(t.get("reason", ""))
            display_text = full_text
            if len(full_text) > 30:
                display_text = full_text[:30] + "..."

            item_reason = QTableWidgetItem(display_text)
            item_reason.setForeground(QColor(TEXT_SUB))
            item_reason.setToolTip(full_text)

            self.table.setItem(row, 7, item_reason)

                                     
            for col in [3, 4]:
                it = self.table.item(row, col)
                if it:
                    it.setForeground(QColor(TEXT_MAIN))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)


                                                                                   
                     
                                                                                   

__all__ = ["CoinContentWidget", "CoinResultWidget", "TradeHistoryWidget"]
