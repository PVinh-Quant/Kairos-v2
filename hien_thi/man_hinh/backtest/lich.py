"""backtest/lich.py — CalendarWidget: lịch giao dịch theo ngày."""
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
class CalendarWidget(QWidget):
                                      
    date_selected = pyqtSignal(object)

    def __init__(self):
        """Khởi tạo widget lịch tháng với navigation và highlight ngày có giao dịch."""
        super().__init__()
        self.setMinimumSize(250, 300)
        self.year, self.month = datetime.now().year, datetime.now().month
        self.selected_date = None                                    
        self.all_trades_df = pl.DataFrame()                         
        self.pnl_data = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

                         
        nav_container = QWidget()
        nav_container.setFixedHeight(30)
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedSize(30, 30)
        self.btn_prev.clicked.connect(self.prev_month)
        self.btn_prev.setStyleSheet(
            f"QPushButton {{ color: {TEXT_SUB}; border: none; font-weight: bold; background: transparent; }} QPushButton:hover {{ background: #222; border-radius: 4px; }}"
        )

        self.lbl_date = QLabel()
        self.lbl_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_date.setStyleSheet(
            f"color: {TEXT_MAIN}; font-family: 'Segoe UI'; font-weight: bold; font-size: 13px;"
        )

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedSize(30, 30)
        self.btn_next.clicked.connect(self.next_month)
        self.btn_next.setStyleSheet(
            f"QPushButton {{ color: {TEXT_SUB}; border: none; font-weight: bold; background: transparent; }} QPushButton:hover {{ background: #222; border-radius: 4px; }}"
        )

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addStretch()
        nav_layout.addWidget(self.lbl_date)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_next)

        layout.addWidget(nav_container)

                      
        self.grid = QWidget()
        self.grid.paintEvent = self.grid_paint_event
                                                
        self.grid.mousePressEvent = self.grid_mouse_press
        layout.addWidget(self.grid)

        self.all_trades = []
        self.update_header_text()
        self.update_data()

    def update_header_text(self):
        """Cập nhật tiêu đề lịch theo tháng và năm hiện tại."""
        self.lbl_date.setText(f"THÁNG {self.month:02d} / {self.year}")

    def set_trades(self, trades, current_date_filter=None):
        """Nạp danh sách lệnh vào lịch và highlight ngày đang được lọc."""
        if not trades:
            self.all_trades_df = pl.DataFrame()
        else:
                                      
            df = pl.DataFrame(trades)

                                             
            if df["time_close"].dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col("time_close").str.strptime(pl.Datetime, strict=False)
                )
            self.all_trades_df = df

        self.selected_date = current_date_filter
                                                                                       
                                                                                
        self._nhay_thang_co_du_lieu()
        self.update_data()

    def _nhay_thang_co_du_lieu(self):
        """Nếu tháng đang hiển thị trống nhưng có lệnh ở tháng khác → nhảy tới tháng mới nhất."""
        if self.all_trades_df.is_empty() or "time_close" not in self.all_trades_df.columns:
            return
        try:
            cur = self.all_trades_df.filter(
                (pl.col("time_close").dt.year() == self.year)
                & (pl.col("time_close").dt.month() == self.month)
            )
            if cur.height > 0:
                return                                                                            
            last_ts = self.all_trades_df["time_close"].max()
            if last_ts is not None:
                self.year, self.month = last_ts.year, last_ts.month
                self.update_header_text()
        except Exception:
            pass

    def update_data(self):
        """Tính PnL theo ngày trong tháng đang hiển thị và cập nhật lịch."""
                                                                     
        if not hasattr(self, "all_trades_df") or self.all_trades_df.is_empty():
            self.pnl_data = {}
            if hasattr(self, "grid"):
                self.grid.update()
            return

        try:
                                                          
            df = self.all_trades_df
            monthly_stats = (
                df.filter(
                    (pl.col("time_close").dt.year() == self.year)
                    & (pl.col("time_close").dt.month() == self.month)
                )
                .group_by(pl.col("time_close").dt.day().alias("day"))
                .agg(
                                                                         
                    pl.col("pnl_usd")
                    .sum()
                    .round(2)
                    .alias("total_pnl")
                )
            )
                                                
            self.pnl_data = {
                int(row["day"]): float(row["total_pnl"])
                for row in monthly_stats.to_dicts()
            }

        except Exception as e:
            print(f"Lỗi xử lý dữ liệu Calendar: {e}")
            self.pnl_data = {}

        if hasattr(self, "grid"):
            self.grid.update()

    def prev_month(self):
        """Chuyển sang tháng trước và cập nhật lịch."""
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self.update_header_text()
        self.update_data()

    def next_month(self):
        """Chuyển sang tháng sau và cập nhật lịch."""
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.update_header_text()
        self.update_data()

    def grid_mouse_press(self, event):
        """Xử lý click trên grid lịch để toggle ngày được chọn."""
        w, h = self.grid.width(), self.grid.height()
        col_w = w / 7
        row_h = h / 7

                                 
        if event.position().y() < row_h:
            return

        cal = calendar.Calendar(firstweekday=6)
        matrix = cal.monthdayscalendar(self.year, self.month)

                                         
        r = int((event.position().y() - row_h) // row_h)
        c = int(event.position().x() // col_w)

        if 0 <= r < len(matrix) and 0 <= c < 7:
            day = matrix[r][c]
            if day != 0:
                clicked_date = datetime(self.year, self.month, day).date()

                              
                if self.selected_date == clicked_date:
                    self.selected_date = None           
                else:
                    self.selected_date = clicked_date

                self.date_selected.emit(self.selected_date)
                self.grid.update()

    def grid_paint_event(self, event):
        """Vẽ lưới lịch tháng với số ngày, PnL và highlight ngày được chọn."""
        painter = QPainter(self.grid)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.grid.width(), self.grid.height()

        cal = calendar.Calendar(firstweekday=6)
        matrix = cal.monthdayscalendar(self.year, self.month)

        col_w = w / 7
        row_h = h / 7

        days = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
        painter.setFont(FONT_SUB)
        painter.setPen(QColor(TEXT_SUB))
        for i, d in enumerate(days):
            painter.drawText(
                QRectF(i * col_w, 0, col_w, row_h), Qt.AlignmentFlag.AlignCenter, d
            )

        font_day = QFont("Segoe UI", 10, QFont.Weight.Bold)
        font_val = QFont("Segoe UI", 7)

        for r, week in enumerate(matrix):
            y = (r + 1) * row_h
            painter.setPen(QPen(QColor(GRID_COLOR), 1))
            painter.drawLine(0, int(y), w, int(y))

            for c, day in enumerate(week):
                if day == 0:
                    continue
                x = c * col_w
                cell_rect = QRectF(x, y, col_w, row_h)

                                                 
                current_date_obj = None
                try:
                    current_date_obj = datetime(self.year, self.month, day).date()
                except:
                    pass

                if self.selected_date and current_date_obj == self.selected_date:
                    painter.fillRect(cell_rect.adjusted(2, 2, -2, -2), QColor("#333"))
                    painter.setPen(QPen(QColor(ACCENT_COLOR), 1))
                    painter.drawRect(cell_rect.adjusted(2, 2, -2, -2))

                            
                painter.setPen(QColor(TEXT_MAIN))
                painter.setFont(font_day)
                painter.drawText(
                    QRectF(x, y + 2, col_w, row_h / 2),
                    Qt.AlignmentFlag.AlignHCenter,
                    str(day),
                )

                        
                if day in self.pnl_data:
                    pnl = self.pnl_data[day]
                    color = QColor(COLOR_WIN) if pnl > 0 else QColor(COLOR_LOSS)
                    painter.setPen(color)
                    painter.setFont(font_val)
                    painter.drawText(
                        QRectF(x, y + 18, col_w, 15),
                        Qt.AlignmentFlag.AlignCenter,
                        f"{pnl:+}",
                    )


                                                                                   
                          
                                                                                   

__all__ = ["CalendarWidget"]
