"""backtest/bieu_do.py — biểu đồ phân tích backtest (phân phối/PnL/tài sản/scatter/LS)."""
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
class DistributionChart(QWidget):
    bar_clicked = pyqtSignal(int, str)

    def __init__(self, chart_type="day"):
        """Khởi tạo biểu đồ phân phối theo ngày hoặc giờ (chart_type='day'/'hour')."""
        super().__init__()
        self.chart_type = chart_type
        self.setMinimumHeight(150)
        self.selected_index = None

        if self.chart_type == "day":
            self.labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            self.data = [0.0] * 7
        else:
            self.labels = [f"{i}h" for i in range(24)]
            self.data = [0.0] * 24

        self.update_data()

    def update_data(self, df: pl.DataFrame = None, current_filter_idx=None):
        """Tính tổng PnL theo ngày/giờ từ DataFrame và cập nhật dữ liệu vẽ."""
        self.selected_index = current_filter_idx
        count = 7 if self.chart_type == "day" else 24

                         
        if df is None or df.is_empty():
            self.data = [0.0] * count
            self.update()
            return

        try:
            col_name = "filter_weekday" if self.chart_type == "day" else "filter_hour"

            if col_name not in df.columns:
                self.update()
                return

            grp = df.group_by(col_name).agg(
                pl.col("pnl_usd").sum().round(2).alias("sum_pnl")
            )

            grp_dict = dict(zip(grp[col_name].to_list(), grp["sum_pnl"].to_list()))

            if self.chart_type == "day":
                self.data = [float(grp_dict.get(i + 1, 0.0)) for i in range(7)]
            else:
                self.data = [float(grp_dict.get(i, 0.0)) for i in range(24)]

        except Exception as e:
            print(f"Lỗi DistributionChart ({self.chart_type}): {e}")
            self.data = [0.0] * count

        self.update()

    def mousePressEvent(self, event):
        """Toggle lọc theo cột được click, emit bar_clicked với index hoặc -1 khi bỏ chọn."""
        w = self.width()
        margin = 16
        draw_w = w - 2 * margin
        count = len(self.data)
        if count == 0:
            return

        col_w = draw_w / count
        mouse_x = event.position().x() - margin

        index = int(mouse_x // col_w)

        if 0 <= index < count:
            if self.selected_index == index:
                self.selected_index = None
                self.bar_clicked.emit(-1, self.chart_type)
            else:
                self.selected_index = index
                self.bar_clicked.emit(index, self.chart_type)
            self.update()

    def paintEvent(self, event):
        """Vẽ biểu đồ cột phân phối PnL theo ngày/giờ với màu xanh/đỏ và highlight."""
        if not hasattr(self, "data") or not self.data:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(CARD_BG))
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(CARD_BG))

        w, h = self.width(), self.height()
        margin = 16
        draw_rect = QRectF(margin, margin, w - 2 * margin, h - 2 * margin - 10)

        bar_count = len(self.data)
        if bar_count == 0:
            return

        bar_w_total = draw_rect.width() / bar_count
        bar_gap = 6 if self.chart_type == "day" else 2
        bar_w = bar_w_total - bar_gap

        max_abs_val = max([abs(x) for x in self.data]) or 1.0
        zero_y = draw_rect.center().y()

        painter.setPen(QPen(QColor(GRID_COLOR), 1, Qt.PenStyle.DashLine))
        painter.drawLine(
            int(draw_rect.left()), int(zero_y), int(draw_rect.right()), int(zero_y)
        )

        for i, val in enumerate(self.data):
            x = draw_rect.left() + i * bar_w_total + bar_gap / 2
            h_val = (abs(val) / max_abs_val) * (draw_rect.height() / 2)

                      
            if val >= 0:
                color = QColor(COLOR_WIN)
                rect = QRectF(x, zero_y - h_val, bar_w, h_val)
            else:
                color = QColor(COLOR_LOSS)
                rect = QRectF(x, zero_y, bar_w, h_val)

                                            
            if self.selected_index is not None:
                if self.selected_index == i:
                    color.setAlpha(255)           
                    painter.setPen(QPen(QColor("#FFFFFF")))              
                else:
                    color.setAlpha(50)         
                    painter.setPen(Qt.PenStyle.NoPen)
            else:
                color.setAlpha(200)            
                painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(color)
            painter.drawRect(rect)

                                                   
            if self.chart_type == "day" or (self.chart_type == "hour" and i % 2 == 0):
                if i < len(self.labels):                    
                    painter.setPen(QColor(TEXT_SUB))
                    painter.setFont(FONT_SUB)
                    label = self.labels[i]
                    text_rect = QRectF(x - 5, draw_rect.bottom() + 5, bar_w + 10, 15)

                    if self.selected_index == i:
                        painter.setPen(QColor(ACCENT_COLOR))
                        f = QFont(FONT_SUB)
                        f.setBold(True)
                        painter.setFont(f)

                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)


                                                                                   
                         
                                                                                   
class BacktestSummaryWidget(QWidget):
    def __init__(self):
        """Khởi tạo widget tóm tắt chỉ số hiệu suất backtest (winrate, PnL, drawdown...)."""
        super().__init__()
        self.setMinimumSize(250, 380)
        self.update_data()

    def update_data(self, data_packet=None):
        """Tính toán và cập nhật các chỉ số hiệu suất từ data_packet chứa danh sách lệnh."""
                                                                                            
        result = data_packet if data_packet else {}
        trades = result.get("trades", [])

        total_trades = len(trades)

        if total_trades > 0:
            df = pl.DataFrame(trades)

                                  
            df = df.with_columns(pl.col("pnl_usd").cast(pl.Float64))

                                   
            total_profit = df["pnl_usd"].sum()

            wins = df.filter(pl.col("pnl_usd") > 0)
            losses = df.filter(pl.col("pnl_usd") <= 0)

            win_rate = (wins.height / total_trades) * 100 if total_trades else 0

            avg_win = wins["pnl_usd"].mean() or 0.0
            avg_loss = abs(losses["pnl_usd"].mean() or 0.0)

            profit_factor = (
                wins["pnl_usd"].sum() / abs(losses["pnl_usd"].sum())
                if losses.height > 0 and losses["pnl_usd"].sum() != 0
                else 0.0
            )

            rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
            expectancy = df["pnl_usd"].mean() or 0.0

                                      
            df = (
                df.with_columns(pl.col("pnl_usd").cum_sum().alias("cumsum"))
                .with_columns(pl.col("cumsum").cum_max().alias("peak"))
                .with_columns((pl.col("cumsum") - pl.col("peak")).alias("drawdown"))
            )

            max_dd_val = df["drawdown"].min() or 0.0

        else:
            total_profit = 0.0
            win_rate = 0.0
            profit_factor = 0.0
            expectancy = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            rr_ratio = 0.0
            max_dd_val = 0.0

                                       
        self.perf_data = [
            (
                "Tỷ lệ thắng",
                f"{win_rate:.1f}%",
                COLOR_WIN if win_rate > 50 else COLOR_LOSS,
            ),
            ("Hệ số lợi nhuận", f"{profit_factor:.2f}", TEXT_MAIN),
            ("Sụt giảm (PnL)", f"{max_dd_val:,.2f}$", COLOR_LOSS),
            ("Kỳ vọng / lệnh", f"{expectancy:+.2f}$", TEXT_MAIN),
            ("Lợi nhuận TB", f"{avg_win:+.2f}$", COLOR_WIN),
            ("Thua lỗ TB", f"-{avg_loss:.2f}$", COLOR_LOSS),
            ("Tỷ lệ R:R", f"{rr_ratio:.2f}", TEXT_MAIN),
        ]

        c_profit = COLOR_WIN if total_profit >= 0 else COLOR_LOSS
        self.summary_data = [
            ("TỔNG LỢI NHUẬN", f"{total_profit:+,.2f}$", c_profit),
            ("TỔNG SỐ LỆNH", f"{total_trades}", TEXT_MAIN),
        ]

        self.update()

    def paintEvent(self, event):
        """Vẽ hai section: chỉ số hiệu suất và tổng kết lợi nhuận/số lệnh."""
        if not hasattr(self, "perf_data") or not self.perf_data:
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

        w, h = self.width(), self.height()
        margin = 14
        gap = 6

        box1_h = h * 0.62
        box2_h = h - box1_h - margin - gap

        self.draw_section(
            painter,
            QRectF(margin, margin, w - 2 * margin, box1_h),
            title=None,
            data=self.perf_data,
        )

        self.draw_section(
            painter,
            QRectF(margin, margin + box1_h + gap, w - 2 * margin, box2_h),
            title="TỔNG KẾT",
            data=self.summary_data,
            is_summary=True,
        )

    def draw_section(self, painter, rect, title, data, is_summary=False):
        """Vẽ một section gồm tiêu đề và danh sách cặp label-value trong rect cho trước."""
        header_h = 24 if title else 0

        if title:
            painter.setPen(QColor(TEXT_SUB))
            font_title = FONT_LABEL
            font_title.setBold(True)
            painter.setFont(font_title)
            painter.drawText(int(rect.left()), int(rect.top() + 15), title)

            line_y = rect.top() + header_h
            painter.setPen(QPen(QColor(GRID_COLOR), 1))
            painter.drawLine(
                int(rect.left()), int(line_y), int(rect.right()), int(line_y)
            )
        else:
            line_y = rect.top()

        content_rect = QRectF(
            rect.left(),
            line_y + (8 if title else 0),
            rect.width(),
            rect.height() - header_h,
        )

        row_h = min(34, content_rect.height() / len(data)) if len(data) > 0 else 34

        for i, (label, value, color_str) in enumerate(data):
            y = content_rect.top() + i * row_h
            row_rect = QRectF(content_rect.left(), y, content_rect.width(), row_h)

            painter.setPen(QColor(TEXT_SUB))
            painter.setFont(FONT_LABEL)
            painter.drawText(
                row_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            painter.setPen(QColor(color_str))
            painter.setFont(FONT_VAL_BIG if is_summary and i == 0 else FONT_VAL_NORM)
            painter.drawText(
                row_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                value,
            )


                                                                                   
                            
                                                                                   
class DailyPnLBarChart(QWidget):
    date_clicked = pyqtSignal(object)

    def __init__(self):
        """Khởi tạo biểu đồ cột lãi/lỗ theo ngày với hỗ trợ click xem chi tiết intraday."""
        super().__init__()
        self.setMinimumSize(300, 250)
        self.chart_data = []
        self.intra_day_trades = []
        self.selected_index = None
        self.selected_date = None
        self.total_pnl_str = "$0.00"
        self.setMouseTracking(True)
        self.df_trades = pl.DataFrame()                    

    def update_data(self, df_trades: pl.DataFrame):
        """Tính toán PnL theo ngày từ DataFrame và cập nhật dữ liệu vẽ biểu đồ cột."""
        if df_trades is None or df_trades.is_empty():
            self.chart_data = []
            self.total_pnl_str = "$0.00"
            self.update()
            return

        self.df_trades = df_trades
        try:
                                                                  
            daily_stats = (
                self.df_trades.group_by("filter_date")
                .agg(
                    [
                        pl.col("pnl_usd").sum().round(2).alias("total_pnl"),
                        pl.col("pnl_usd")
                        .filter(pl.col("filter_side") == "long")
                        .sum()
                        .round(2)
                        .fill_null(0)
                        .alias("long_pnl"),
                        pl.col("pnl_usd")
                        .filter(pl.col("filter_side") == "short")
                        .sum()
                        .round(2)
                        .fill_null(0)
                        .alias("short_pnl"),
                        pl.len().alias(
                            "count"
                        ),                                                      
                    ]
                )
                .sort("filter_date")
            )

                                                             
            self.chart_data = [
                {
                    "date": r["filter_date"],
                    "total_pnl": r["total_pnl"],
                    "long_pnl": r["long_pnl"],
                    "short_pnl": r["short_pnl"],
                    "count": r["count"],
                }
                for r in daily_stats.tail(50).to_dicts()
            ]

            total_pnl = self.df_trades["pnl_usd"].sum()
            self.total_pnl_str = f"{total_pnl:+,.2f}$"

        except Exception as e:
            print(f"Lỗi Daily PnL: {e}")
        self.update()

    def mousePressEvent(self, event):
        """Toggle xem chi tiết intraday khi click vào cột ngày, click lại để quay về."""
        if not self.chart_data:
            return

                                                                   
        if self.selected_date:
            self.selected_date = None
            self.selected_index = None
            self.date_clicked.emit(None)
            self.update()
            return

        margin = 16
        chart_w = self.width() - margin * 2
        slot_w = chart_w / len(self.chart_data)
        mouse_x = event.position().x() - margin
        index = int(mouse_x // slot_w)

        if 0 <= index < len(self.chart_data):
            self.selected_index = index
            self.selected_date = self.chart_data[index]["date"]

                                                                        
            day_df = self.df_trades.filter(
                pl.col("filter_date") == self.selected_date
            ).sort("time_close")
            self.intra_day_trades = day_df.to_dicts()

            self.date_clicked.emit(self.selected_date)
            self.update()

    def paintEvent(self, event):
        """Vẽ biểu đồ cột ngày hoặc đường intraday tùy trạng thái đang chọn."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(CARD_BG))

        w, h = self.width(), self.height()
        margin = 16
        chart_top = 85
        chart_h = h - chart_top - 30
        zero_y = chart_top + chart_h / 2

                                  
        painter.setFont(FONT_VAL_BIG)
        painter.setPen(QColor(COLOR_WIN if "+" in self.total_pnl_str else COLOR_LOSS))
        painter.drawText(margin, 40, self.total_pnl_str)

                                                                    
        if self.selected_date and self.intra_day_trades:
            self.draw_intraday_line(painter, margin, chart_top, w - margin * 2, chart_h)
        else:
                                                     
            self.draw_daily_bars(
                painter, margin, chart_top, w - margin * 2, chart_h, zero_y
            )

    def draw_intraday_line(self, painter, x, y, w, h):
        """Vẽ đường equity curve nội ngày từ danh sách lệnh intraday."""
                                       
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(ACCENT_COLOR))
        painter.drawText(
            x,
            65,
            f"CHI TIẾT: {self.selected_date.strftime('%d/%m/%Y')} (Click để quay lại)",
        )

                                            
        pnl_values = [t["pnl_usd"] for t in self.intra_day_trades]
        equity_points = [0]
        curr = 0
        for v in pnl_values:
            curr += v
            equity_points.append(curr)

        max_v = max(equity_points) if equity_points else 1
        min_v = min(equity_points) if equity_points else -1
        range_v = max(abs(max_v), abs(min_v)) or 1

                       
        zero_y = y + h / 2
        painter.setPen(QPen(QColor(GRID_COLOR), 1, Qt.PenStyle.DotLine))
        painter.drawLine(x, int(zero_y), x + w, int(zero_y))

                 
        path = QPainterPath()
        step_x = w / (len(equity_points) - 1) if len(equity_points) > 1 else w

        points = []
        for i, val in enumerate(equity_points):
            px = x + i * step_x
                                
            py = zero_y - (val / range_v * (h / 2.2))
            points.append(QPointF(px, py))
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

                                    
        fill_path = QPainterPath(path)
        fill_path.lineTo(points[-1].x(), zero_y)
        fill_path.lineTo(points[0].x(), zero_y)
        painter.fillPath(fill_path, QColor(60, 180, 255, 30))

                        
        painter.setPen(QPen(QColor("#3498db"), 2))
        painter.drawPath(path)

                          
        painter.setBrush(QColor("#3498db"))
        painter.drawEllipse(points[-1], 3, 3)

    def draw_daily_bars(self, painter, margin, chart_top, chart_w, chart_h, zero_y):
        """Vẽ cột lãi/lỗ mỗi ngày: XANH nếu ngày LÃI, ĐỎ nếu ngày LỖ (theo total_pnl), kèm số lệnh.

        Màu = lãi/lỗ (đúng tiêu đề "LÃI LỖ HẰNG NGÀY"); phân tích theo chiều lệnh xem ở panel
        LONG VS SHORT. Trước đây tô theo chiều lệnh (long=xanh/short=đỏ) nên ngày LONG-lỗ vẫn ra xanh.
        """
        if not self.chart_data:
            return

        max_val = max(abs(d["total_pnl"]) for d in self.chart_data) or 1
        slot_w = chart_w / len(self.chart_data)
        bar_gap = 6
        bar_w = max(3, slot_w - bar_gap)

        painter.setPen(QPen(QColor(GRID_COLOR), 1, Qt.PenStyle.DashLine))
        painter.drawLine(margin, int(zero_y), margin + chart_w, int(zero_y))

        for i, d in enumerate(self.chart_data):
            x = margin + i * slot_w + bar_gap / 2

            pnl = d["total_pnl"]
            la_lai = pnl >= 0
            height = (abs(pnl) / (max_val * 1.2)) * (chart_h / 2)

                                                                               
            rect = QRectF(x, zero_y - height if la_lai else zero_y, bar_w, height)
            painter.fillRect(rect, QColor(COLOR_WIN if la_lai else COLOR_LOSS))

                              
            painter.setPen(QColor(TEXT_SUB))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(
                QRectF(x - 5, zero_y + (chart_h / 2) + 5, bar_w + 10, 15),
                Qt.AlignmentFlag.AlignCenter,
                str(d["count"]),
            )


                                                                                   
                 
                                                                                   
class TotalAssetChart(QWidget):
    def __init__(self):
        """Khởi tạo widget equity curve với gradient fill và thông tin balance/PnL."""
        super().__init__()
        self.setMinimumSize(300, 200)
        self.chart_color = QColor("#2962FF")

                                                
        self.data = []
        self.total_val = 0.0
        self.pnl_val = 0.0
        self.pnl_pct = 0.0

                                                
        self.update_data()

    def downsample_data(self, balances, max_points=300):
        """Hàm rút gọn dữ liệu để biểu đồ mượt hơn (Instance method)"""
        n = len(balances)
        if n <= max_points:
            return balances

        bucket_size = n / max_points
        result = []
        for i in range(max_points):
            start = int(i * bucket_size)
            end = int((i + 1) * bucket_size)
            chunk = balances[start:end]
            if not chunk:
                continue
                                                                               
            result.append(min(chunk))
            result.append(max(chunk))
        return result

    def update_data(self, equity_curve=None):
        """Cập nhật dữ liệu equity curve, tính PnL tổng và trigger repaint."""
        if not equity_curve:
            self.data = []
            self.total_val = self.pnl_val = self.pnl_pct = 0.0
            self.update()
            return

                                               
        balances = [item["balance"] for item in equity_curve]

        if len(balances) > 0:
                                           
            self.data = self.downsample_data(balances, 300)

            start_val = balances[0]
            self.total_val = balances[-1]
            self.pnl_val = self.total_val - start_val
            self.pnl_pct = (self.pnl_val / start_val * 100) if start_val != 0 else 0.0

        self.update()

    def paintEvent(self, event):
        """Vẽ đường equity curve với gradient fill, balance và PnL header."""
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
        w, h = self.width(), self.height()
        margin = 16

        painter.setPen(QColor(TEXT_MAIN))
        painter.setFont(FONT_VAL_BIG)
        str_balance = f"${self.total_val:,.2f}"
        painter.drawText(margin, margin + 25, str_balance)

        fm = QFontMetrics(FONT_VAL_BIG)
        balance_width = fm.horizontalAdvance(str_balance)

        painter.setFont(FONT_VAL_NORM)
        if self.pnl_val >= 0:
            color = QColor(COLOR_WIN)
            sign = "+"
        else:
            color = QColor(COLOR_LOSS)
            sign = ""

        painter.setPen(color)
        pnl_str = f"{sign}{self.pnl_val:,.2f}$ ({sign}{self.pnl_pct:.2f}%)"
        painter.drawText(margin + balance_width + 10, margin + 25, pnl_str)

        painter.setPen(QColor(TEXT_SUB))
        painter.setFont(FONT_SUB)

        chart_top = 60
        chart_h = h - chart_top

        if not self.data:
            return

        max_v = max(self.data)
        min_v = min(self.data)
        range_v = max_v - min_v if max_v != min_v else 1

        path = QPainterPath()
        step_x = w / (len(self.data) - 1) if len(self.data) > 1 else w
        points = []

        for i, val in enumerate(self.data):
            x = i * step_x
            y = h - ((val - min_v) / range_v * (chart_h - 10)) - 5
            p = QPointF(x, y)
            points.append(p)
            if i == 0:
                path.moveTo(p)
            else:
                path.lineTo(p)

        fill_path = QPainterPath(path)
        fill_path.lineTo(points[-1].x(), h)
        fill_path.lineTo(points[0].x(), h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, chart_top, 0, h)
        c_base = QColor(COLOR_WIN) if self.pnl_val >= 0 else QColor(COLOR_LOSS)

        c1 = QColor(c_base)
        c1.setAlpha(80)
        c2 = QColor(c_base)
        c2.setAlpha(0)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.fillPath(fill_path, QBrush(grad))

        painter.setPen(QPen(c_base, 2))
        painter.drawPath(path)


                                                                                   
                                
                                                                                   
class TradeScatterWidget(QWidget):
    def __init__(self):
        """Khởi tạo scatter plot phân tích thời gian giữ lệnh vs PnL với tooltip hover."""
        super().__init__()
        self.setMinimumSize(300, 200)
        self.points = []
        self.max_duration = 1
        self.max_pnl_abs = 1

                                                 
        self.MIN_DURATION_DISPLAY = 1

                                            
        self.setMouseTracking(True)
        self.hover_point = None

    def format_duration(self, minutes):
        """Format thời gian dễ đọc (vd: 5m, 2h 30m)"""
        if minutes < 1:
            return f"{int(minutes*60)}s"
        if minutes < 60:
            return f"{int(minutes)}m"
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if hours < 24:
            return f"{hours}h {mins}m"
        days = int(hours // 24)
        rem_hours = hours % 24
        return f"{days}d {rem_hours}h"

    def update_data(self, df: pl.DataFrame | None = None):
        """Tính toán duration, PnL từ DataFrame và chuẩn bị danh sách điểm vẽ scatter."""
        self.points = []
        self.hover_point = None

        if df is None or df.is_empty():
            self.update()
            return

        try:
                                            
            if "time_close" not in df.columns or "time_open" not in df.columns:
                print("ScatterPlot: Thiếu cột time_close hoặc time_open")
                self.update()
                return

                                                                 
            df_plot = df.select(
                [
                    pl.col("time_close"),
                    pl.col("time_open"),
                    pl.col("pnl_usd").cast(pl.Float64).alias("pnl"),
                    pl.col("symbol").fill_null("Unknown").alias("pair"),
                ]
            ).with_columns(
                (
                    (pl.col("time_close") - pl.col("time_open"))
                    .dt.total_minutes()
                    .fill_null(0)
                    .clip(lower_bound=self.MIN_DURATION_DISPLAY)
                ).alias("duration")
            )

                                              
            max_dur = df_plot["duration"].max()
            max_pnl = df_plot["pnl"].abs().max()

            self.max_duration = max_dur if max_dur and max_dur > 1 else 1
            self.max_pnl_abs = max_pnl if max_pnl and max_pnl > 0 else 1

                                                 
            rows = df_plot.select(["duration", "pnl", "pair"]).to_dicts()

            for r in rows:
                self.points.append(
                    {
                        "dur": r["duration"],
                        "pnl": r["pnl"],
                        "pair": r["pair"],
                        "color": (
                            QColor(COLOR_WIN) if r["pnl"] >= 0 else QColor(COLOR_LOSS)
                        ),
                    }
                )

        except Exception as e:
            print(f"Lỗi logic Scatter Plot: {e}")

        self.update()

    def get_x_pos(self, duration, plot_width, margin_left):
        """Tính tọa độ X logarit cho một giá trị duration trên trục thời gian."""
                                                               
        safe_dur = max(self.MIN_DURATION_DISPLAY, duration)

        min_log = math.log10(self.MIN_DURATION_DISPLAY)

                                                                  
        real_max = max(self.max_duration * 1.1, self.MIN_DURATION_DISPLAY * 2)
        max_log = math.log10(real_max)

        current_log = math.log10(safe_dur)

        range_log = max_log - min_log
        if range_log == 0:
            range_log = 1

                             
        ratio = (current_log - min_log) / range_log
        return margin_left + (ratio * plot_width)

    def mouseMoveEvent(self, event):
        """Xử lý hover chuột để hiện Tooltip"""
        if not self.points:
            return

        mx, my = event.position().x(), event.position().y()
        w, h = self.width(), self.height()

        m_left, m_bottom, m_top, m_right = 50, 30, 20, 20
        plot_w = w - m_left - m_right
        plot_h = h - m_top - m_bottom
        center_y = m_top + plot_h / 2
        scale_y = (plot_h / 2) / self.max_pnl_abs

        closest_dist = 15         
        found = None

        for p in self.points:
                                       
            px = self.get_x_pos(p["dur"], plot_w, m_left)
            py = center_y - (p["pnl"] * scale_y)

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
        """Vẽ scatter plot với trục log, lưới thời gian, các điểm và tooltip hover."""
        if not hasattr(self, "points") or not self.points:
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

        w, h = self.width(), self.height()
        m_left, m_bottom, m_top, m_right = 50, 30, 20, 20
        plot_w = w - m_left - m_right
        plot_h = h - m_top - m_bottom
        center_y = m_top + plot_h / 2

                                     
        painter.setPen(QPen(QColor(BORDER_COLOR), 1))
        painter.drawLine(m_left, m_top, m_left, h - m_bottom)          
        painter.drawLine(m_left, h - m_bottom, w - m_right, h - m_bottom)          

                  
        painter.setPen(QPen(QColor("#444"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(m_left, int(center_y), w - m_right, int(center_y))

                                                     
        time_markers = [1, 5, 15, 60, 240, 1440, 4320]
        painter.setFont(FONT_SUB)

        for tm in time_markers:
            if tm > self.max_duration * 1.5:
                break

                                                          
            if tm < self.MIN_DURATION_DISPLAY:
                continue

                                        
            x_line = self.get_x_pos(tm, plot_w, m_left)

                             
            painter.setPen(QPen(QColor(GRID_COLOR), 1, Qt.PenStyle.DotLine))
            painter.drawLine(int(x_line), m_top, int(x_line), h - m_bottom)

                     
            painter.setPen(QColor(TEXT_SUB))
            label = self.format_duration(tm)
            painter.drawText(int(x_line) + 3, h - m_bottom - 5, label)

                                   
        painter.setFont(FONT_LABEL)
        painter.setPen(QColor(COLOR_WIN))
        painter.drawText(5, m_top + 10, f"+{self.max_pnl_abs:.1f}$")
        painter.setPen(QColor(COLOR_LOSS))
        painter.drawText(5, h - m_bottom, f"-{self.max_pnl_abs:.1f}$")
        painter.setPen(QColor(TEXT_SUB))
        painter.drawText(5, int(center_y) + 5, "0$")

        if not self.points:
            painter.drawText(w // 2 - 20, h // 2, "No Data")
            return

                                         
        scale_y = (plot_h / 2) / self.max_pnl_abs
        painter.setPen(Qt.PenStyle.NoPen)

        for p in self.points:
                                        
            x = self.get_x_pos(p["dur"], plot_w, m_left)
            y = center_y - (p["pnl"] * scale_y)

                                     
            if y < m_top:
                y = m_top
            if y > h - m_bottom:
                y = h - m_bottom

            is_hover = self.hover_point == p
            radius = 6 if is_hover else 4

            c = QColor(p["color"])
            c.setAlpha(255 if is_hover else 180)
            painter.setBrush(c)

            if is_hover:
                painter.setPen(QPen(QColor("white"), 1))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawEllipse(QPointF(x, y), radius, radius)

                               
        if self.hover_point:
            hp = self.hover_point
            tip_text = f"{hp['pair']}\nPnL: {hp['pnl']:+.2f}$\nTime: {self.format_duration(hp['dur'])}"

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

            painter.setPen(QPen(QColor(ACCENT_COLOR), 1))
            painter.setBrush(QColor(20, 20, 20, 240))
            painter.drawRoundedRect(QRectF(bx, by, max_w, box_h), 5, 5)

            painter.setPen(QColor(TEXT_MAIN))
            for i, line in enumerate(lines):
                painter.drawText(int(bx + 10), int(by + 15 + i * fm.height()), line)


                                                                                   
                                                                     
                                                                                   
class LongShortWidget(QWidget):
                                                                
    side_clicked = pyqtSignal(object)

    def __init__(self):
        """Khởi tạo widget so sánh hiệu suất lệnh Long vs Short."""
        super().__init__()
        self.setMinimumSize(250, 150)
        self.stats = {
            "long": {"win": 0, "total": 0, "pnl": 0},
            "short": {"win": 0, "total": 0, "pnl": 0},
        }
        self.selected_side = None                             

    def update_data(self, df: pl.DataFrame | None = None, current_filter_side=None):
        """Tính winrate và PnL cho mỗi bên Long/Short từ DataFrame và cập nhật widget."""
        self.selected_side = current_filter_side
        self.stats = {
            "long": {"win": 0, "total": 0, "pnl": 0.0},
            "short": {"win": 0, "total": 0, "pnl": 0.0},
        }

        if df is None or df.is_empty():
            self.update()
            return

        try:
                                                                 
            agg = (
                df.group_by("filter_side")
                .agg(
                    [
                        pl.len().alias("total"),
                        pl.col("pnl_usd").sum().round(2).alias("pnl"),
                        pl.col("pnl_usd")
                        .filter(pl.col("pnl_usd") > 0)
                        .len()
                        .alias("win"),
                    ]
                )
                .to_dicts()
            )

            for row in agg:
                side = row["filter_side"]                                           
                if side in self.stats:
                    self.stats[side]["total"] = row["total"]
                    self.stats[side]["pnl"] = float(row["pnl"])
                    self.stats[side]["win"] = int(row["win"])
        except Exception as e:
            print(f"Lỗi LongShortWidget: {e}")

        self.update()

    def mousePressEvent(self, event):
        """Toggle lọc theo Long hoặc Short khi người dùng click vào vùng tương ứng."""
        y = event.position().y()

        clicked_side = None

                                                  
        if 0 <= y <= 75:
            clicked_side = "long"

                                                
        elif 85 <= y <= 150:
            clicked_side = "short"

                                                                                           
        if clicked_side is None:
            return

                                                           
        if self.selected_side == clicked_side:
            self.selected_side = None               
        else:
            self.selected_side = clicked_side

                                               
        self.side_clicked.emit(self.selected_side)
        self.update()

    def paintEvent(self, event):
        """Vẽ hai thanh progress Long/Short với winrate, số lệnh và PnL."""
        if not self.stats or (
            self.stats["long"]["total"] == 0 and self.stats["short"]["total"] == 0
        ):
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
        w, h = self.width(), self.height()
        margin = 16
        bar_height = 40

                 
        self.draw_bar(
            painter,
            margin,
            30,
            w - 2 * margin,
            bar_height,
            "LONG",
            self.stats["long"],
            QColor("#4CAF50"),
            is_selected=(self.selected_side == "long"),
        )

                  
        self.draw_bar(
            painter,
            margin,
            30 + bar_height + 20,
            w - 2 * margin,
            bar_height,
            "SHORT",
            self.stats["short"],
            QColor("#FF5252"),
            is_selected=(self.selected_side == "short"),
        )

    def draw_bar(self, painter, x, y, w, h, title, data, color, is_selected=False):
        """Vẽ một thanh progress bar với winrate, hiệu ứng highlight và dim."""
                                    
        if is_selected:
            painter.setPen(QPen(QColor(ACCENT_COLOR), 1))
            c_highlight = QColor(ACCENT_COLOR)
            c_highlight.setAlpha(30)
            painter.setBrush(c_highlight)
                                      
            painter.drawRoundedRect(QRectF(x - 5, y - 25, w + 10, 45), 6, 6)

        painter.setPen(QColor(TEXT_MAIN))
        painter.setFont(FONT_LABEL)
        total = data["total"]
        winrate = (data["win"] / total * 100) if total > 0 else 0.0
        pnl = data["pnl"]

                                                       
        if self.selected_side is not None and not is_selected:
            painter.setOpacity(0.3)
        else:
            painter.setOpacity(1.0)

        text = f"{title}: {total} lệnh | Win: {winrate:.1f}% | PnL: {pnl:+.2f}$"
        painter.drawText(int(x), int(y - 5), text)

        bg_rect = QRectF(x, y, w, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#333"))
        painter.drawRoundedRect(bg_rect, 5, 5)

        if total > 0:
            win_w = w * (winrate / 100)
            if win_w < 5 and winrate > 0:
                win_w = 5
            win_rect = QRectF(x, y, win_w, 10)
            painter.setBrush(color)
            painter.drawRoundedRect(win_rect, 5, 5)

        painter.setOpacity(1.0)


                                                                                   
                                                              
                                                                                   

__all__ = ["DistributionChart", "BacktestSummaryWidget", "DailyPnLBarChart", "TotalAssetChart", "TradeScatterWidget", "LongShortWidget"]
