import sys
import os
import polars as pl
import pandas as pd
import bisect
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QApplication,
    QSplitter,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import Qt, QRectF, QThread, pyqtSignal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from chuc_nang.vectorized_backtest import vectorized_backtest
except ImportError:
    vectorized_backtest = None


                                            
                                             
                                            
class Theme:
    BG = "#0e0e0e"
    CARD = "#0e0e0e"
    BORDER = "#2A2E39"
    GRID = "#1E222D"
    TEXT_MAIN = "#D1D4DC"
    TEXT_SUB = "#787B86"
    WIN = "#089981"
    LOSS = "#F23645"
    ACCENT = "#C8AA6E"
    ENTRY = "#2962FF"
    EXIT = "#FF9800"
    TRADE_LINE = "#4c525e"

                                        
    REGIME_COLORS = {
        0: "#787B86",                  
        1: "#FFD700",                           
        2: "#00BFFF",                                  
        3: "#089981",                                 
        4: "#FF4500",                               
        5: "#9C27B0",                             
        6: "#8D6E63",                             
        7: "#FF1493",                            
    }


def to_datetime(val):
    """Chuyển đổi giá trị timestamp sang datetime không có timezone."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        return pd.to_datetime(val).replace(tzinfo=None)
    except:
        return None


                                            
                            
                                            
class DataProcessorWorker(QThread):
    finished = pyqtSignal(object, list)

    def __init__(self, df_base, tf):
        super().__init__()
        self.df_base = df_base
        self.tf = tf

    def run(self):
        """Resample dữ liệu theo khung thời gian rồi phát tín hiệu finished."""
        try:
            if self.tf == "1m" or self.df_base.is_empty():
                df_res = self.df_base
            else:
                agg_cols = [
                    pl.col("open").first(),
                    pl.col("high").max(),
                    pl.col("low").min(),
                    pl.col("close").last(),
                    (
                        pl.col("volume").sum()
                        if "volume" in self.df_base.columns
                        else pl.lit(0).alias("volume")
                    ),
                ]

                                                                                                     
                for col_name in [
                    "signal",
                    "entry_signal",
                    "buy_score",
                    "sell_score",
                    "regime",
                ]:
                    if col_name in self.df_base.columns:
                        agg_cols.append(pl.col(col_name).last())

                df_res = self.df_base.group_by_dynamic("timestamp", every=self.tf).agg(
                    agg_cols
                )

            timestamps = [to_datetime(ts) for ts in df_res["timestamp"].to_list()]
            self.finished.emit(df_res, timestamps)
        except Exception as e:
            print(f"Data Worker Error: {e}")
            timestamps = [to_datetime(ts) for ts in self.df_base["timestamp"].to_list()]
            self.finished.emit(self.df_base, timestamps)


                                            
                                       
                                            
class RegimeLegendWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet(
            f"background-color: {Theme.CARD}; border-left: 1px solid {Theme.BORDER};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(12)

        title = QLabel("REGIME MAP")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {Theme.ACCENT}; border: none; margin-bottom: 10px;"
        )
        layout.addWidget(title)

        regime_desc = {
            0: "S0: Đóng_Băng",
            1: "S1: Nén_Chặt",
            2: "S2: Đầu_Xu_Hướng",
            3: "S3: Xu_Hướng_Mạnh",
            4: "S4: Cao_Trào",
            5: "S5: Hồi_Quy",
            6: "S6: Nhiễu_Động",
            7: "S7: Quét_Thanh_Khoản",
        }

        for r_id, desc in regime_desc.items():
            row = QHBoxLayout()
            row.setSpacing(10)

                                  
            color_box = QLabel()
            color_box.setFixedSize(16, 16)
            color_hex = Theme.REGIME_COLORS.get(r_id, "#FFFFFF")
            color_box.setStyleSheet(
                f"background-color: {color_hex}; border-radius: 3px; border: 1px solid #000;"
            )

                        
            label = QLabel(desc)
            label.setFont(QFont("Segoe UI", 10))
            label.setStyleSheet(f"color: {Theme.TEXT_MAIN}; border: none;")

            row.addWidget(color_box)
            row.addWidget(label)
            row.addStretch()

            layout.addLayout(row)

        layout.addStretch()


                                            
                                          
                                            
class CoreCandlestickChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.df_current = pl.DataFrame()
        self.current_timestamps = []
        self.candle_width = 8
        self.candle_gap = 2
        self.scroll_offset = 0
        self.mouse_pos = None
        self.last_mouse_x = 0
        self.is_panning = False
        self.current_tf = "1m"

    def wheelEvent(self, event):
        """Zoom biểu đồ bằng cuộn chuột."""
        delta = event.angleDelta().y()
        self.candle_width = (
            min(40, self.candle_width + 2)
            if delta > 0
            else max(3, self.candle_width - 2)
        )
        self.update()

    def mousePressEvent(self, event):
        """Bắt đầu kéo biểu đồ khi nhấn chuột trái."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.last_mouse_x = event.position().x()

    def mouseReleaseEvent(self, event):
        """Kết thúc kéo biểu đồ khi thả chuột trái."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False

    def mouseMoveEvent(self, event):
        """Cập nhật vị trí chuột và cuộn biểu đồ khi đang kéo."""
        self.mouse_pos = event.position()
        if self.is_panning:
            dx = event.position().x() - self.last_mouse_x
            candles_shifted = int(dx / (self.candle_width + self.candle_gap))
            if candles_shifted != 0:
                self.scroll_offset += candles_shifted
                max_offset = max(0, self.df_current.height - 5)
                self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
                self.last_mouse_x = event.position().x()
        self.update()

    def leaveEvent(self, event):
        """Ẩn crosshair khi chuột rời khỏi widget."""
        self.mouse_pos = None
        self.update()

    def paintEvent(self, event):
        """Vẽ toàn bộ biểu đồ nến màu theo regime, lưới và HUD."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Theme.CARD))

        if self.df_current.is_empty():
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu Regime..."
            )
            return

        w, h = self.width(), self.height()
        margin_top, margin_bottom, margin_right = 25, 40, 70
        chart_w, chart_h = w - margin_right, h - margin_top - margin_bottom
        space_per_candle = self.candle_width + self.candle_gap
        max_visible_candles = int(chart_w // space_per_candle)
        total_candles = self.df_current.height
        end_idx = total_candles - self.scroll_offset
        start_idx = max(0, end_idx - max_visible_candles)

        if start_idx >= end_idx:
            return
        df_view = self.df_current[start_idx:end_idx]

        timestamps = [to_datetime(ts) for ts in df_view["timestamp"].to_list()]
        opens = df_view["open"].to_list()
        highs = df_view["high"].to_list()
        lows = df_view["low"].to_list()
        closes = df_view["close"].to_list()
        volumes = (
            df_view["volume"].to_list()
            if "volume" in df_view.columns
            else [0] * len(opens)
        )

                                    
        regimes = (
            df_view["regime"].to_list()
            if "regime" in df_view.columns
            else [None] * len(opens)
        )

        min_low, max_high = min(lows), max(highs)
        price_range = max_high - min_low if max_high != min_low else 1
        min_low -= price_range * 0.1
        max_high += price_range * 0.1
        price_range = max_high - min_low

        def get_y(price):
            return margin_top + chart_h - ((price - min_low) / price_range) * chart_h

                     
        grid_pen = QPen(QColor(Theme.GRID), 1, Qt.PenStyle.SolidLine)
        painter.setPen(grid_pen)
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(9):
            py = margin_top + (chart_h / 8) * i
            painter.drawLine(0, int(py), int(chart_w), int(py))
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.drawText(
                int(chart_w + 8), int(py + 4), f"{max_high - (price_range / 8) * i:.4f}"
            )
            painter.setPen(grid_pen)

        fm_time = painter.fontMetrics()
        time_step = max(
            1, int(fm_time.horizontalAdvance("00:00 00/00") * 1.5 // space_per_candle)
        )

        for i in range(len(opens)):
            if (start_idx + i) % time_step == 0:
                x = (
                    chart_w
                    - (len(opens) - i) * space_per_candle
                    + self.candle_width / 2
                )
                painter.drawLine(
                    int(x), int(margin_top), int(x), int(margin_top + chart_h)
                )

        hovered_candle_idx = -1
        max_vol = max(volumes) if volumes and max(volumes) > 0 else 1
        vol_max_height = chart_h * 0.25

                                                                          
        for i in range(len(opens)):
            o, hi, lo, c, vol = opens[i], highs[i], lows[i], closes[i], volumes[i]
            x = chart_w - (len(opens) - i) * space_per_candle
            center_x = x + self.candle_width / 2
            yo, yc, yh, yl = get_y(o), get_y(c), get_y(hi), get_y(lo)
            is_up = c >= o

                                                
            regime_val = regimes[i]
            if regime_val is not None and int(regime_val) in Theme.REGIME_COLORS:
                base_color = QColor(Theme.REGIME_COLORS[int(regime_val)])
            else:
                base_color = QColor(Theme.WIN) if is_up else QColor(Theme.LOSS)

            if self.mouse_pos and x <= self.mouse_pos.x() <= x + space_per_candle:
                hovered_candle_idx = i
                painter.fillRect(
                    QRectF(
                        x - self.candle_gap / 2, margin_top, space_per_candle, chart_h
                    ),
                    QColor(255, 255, 255, 8),
                )

                       
            vol_h = (vol / max_vol) * vol_max_height
            vol_brush = QColor(base_color)
            vol_brush.setAlpha(80)
            painter.fillRect(
                QRectF(x, margin_top + chart_h - vol_h, self.candle_width, vol_h),
                vol_brush,
            )

                        
            painter.setPen(QPen(base_color, 1.5))
            painter.drawLine(int(center_x), int(yh), int(center_x), int(yl))

                                                                     
            painter.setPen(Qt.PenStyle.NoPen)
            if is_up:
                painter.setBrush(QColor(Theme.CARD))                     
                painter.drawRect(
                    QRectF(x, min(yo, yc), self.candle_width, max(abs(yo - yc), 1))
                )
                                          
                painter.setPen(QPen(base_color, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    QRectF(x, min(yo, yc), self.candle_width, max(abs(yo - yc), 1))
                )
            else:
                painter.setBrush(base_color)                     
                painter.drawRect(
                    QRectF(x, min(yo, yc), self.candle_width, max(abs(yo - yc), 1))
                )

                   
        for i in range(len(opens)):
            if (start_idx + i) % time_step == 0:
                x = (
                    chart_w
                    - (len(opens) - i) * space_per_candle
                    + self.candle_width / 2
                )
                painter.setPen(QPen(QColor(Theme.BORDER), 1.5))
                painter.drawLine(
                    int(x),
                    int(margin_top + chart_h),
                    int(x),
                    int(margin_top + chart_h + 6),
                )
                painter.setPen(QColor(Theme.TEXT_SUB))
                ts = timestamps[i]
                if ts:
                    time_str = (
                        ts.strftime("%H:%M\n%d/%m")
                        if self.current_tf in ["1m", "3m", "5m", "15m"]
                        else ts.strftime("%d/%m\n%H:%M")
                    )
                    painter.drawText(
                        QRectF(x - 30, margin_top + chart_h + 8, 60, 30),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                        time_str,
                    )

        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.drawLine(int(chart_w), 0, int(chart_w), h)
        painter.drawLine(
            0, int(margin_top + chart_h), int(chart_w), int(margin_top + chart_h)
        )

                                                    
                                         
                                                    
        if self.mouse_pos and hovered_candle_idx != -1:
            mx, my = self.mouse_pos.x(), self.mouse_pos.y()
            mx = max(0, min(mx, chart_w))
            my = max(margin_top, min(my, margin_top + chart_h))
            hover_x = (
                chart_w
                - (len(opens) - hovered_candle_idx) * space_per_candle
                + self.candle_width / 2
            )

            painter.setPen(QPen(QColor(Theme.TEXT_SUB), 1, Qt.PenStyle.DashLine))
            painter.drawLine(
                int(hover_x), int(margin_top), int(hover_x), int(margin_top + chart_h)
            )
            painter.drawLine(0, int(my), int(chart_w), int(my))

            ho, hh, hl, hc = (
                opens[hovered_candle_idx],
                highs[hovered_candle_idx],
                lows[hovered_candle_idx],
                closes[hovered_candle_idx],
            )
            hover_time = timestamps[hovered_candle_idx]
            hover_regime = regimes[hovered_candle_idx]

            hud_lines = [
                "📌 INFO",
                f"T: {hover_time.strftime('%m-%d %H:%M') if hover_time else ''}",
                f"O: {ho:.2f} | C: {hc:.2f}",
                f"H: {hh:.2f} | L: {hl:.2f}",
            ]

            if hover_regime is not None:
                hud_lines.insert(2, f"Regime: {int(hover_regime)}")

            font_hud = QFont("Consolas", 9)
            painter.setFont(font_hud)
            fm_hud = painter.fontMetrics()

            max_w = max([fm_hud.horizontalAdvance(line) for line in hud_lines]) + 15
            box_h = len(hud_lines) * 16 + 10

            hud_x, hud_y = mx + 20, my + 20
            if mx > chart_w * 0.6:
                hud_x = mx - max_w - 20
            if my > chart_h * 0.6:
                hud_y = my - box_h - 20

            bg_hud = QColor(Theme.CARD)
            bg_hud.setAlpha(240)
            painter.setPen(QPen(QColor(Theme.BORDER), 1))
            painter.setBrush(bg_hud)
            painter.drawRoundedRect(
                int(hud_x), int(hud_y), int(max_w), int(box_h), 4, 4
            )

            curr_y = hud_y + 16
            for line in hud_lines:
                color = Theme.ACCENT if "📌" in line else Theme.TEXT_MAIN
                if (
                    "Regime:" in line
                    and hover_regime is not None
                    and int(hover_regime) in Theme.REGIME_COLORS
                ):
                    color = Theme.REGIME_COLORS[int(hover_regime)]
                painter.setPen(QColor(color))
                painter.drawText(int(hud_x + 10), int(curr_y), line)
                curr_y += 16

            cross_price = max_high - ((my - margin_top) / chart_h) * price_range
            painter.setBrush(QColor(Theme.TEXT_MAIN))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(chart_w), int(my - 10), margin_right, 20)
            painter.setPen(QColor(Theme.BG))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(int(chart_w + 6), int(my + 4), f"{cross_price:.4f}")


                                            
                                   
                                            
class CandlestickChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1200, 700)
        self.setStyleSheet(f"background-color: {Theme.BG};")

        self.current_symbol = "UNKNOWN"
        self.df_base_1m = pl.DataFrame()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

                            
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)

        self.setup_toolbar()

        self.chart = CoreCandlestickChart()
        self.left_layout.addWidget(self.chart)

                                       
        self.legend = RegimeLegendWidget()

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.legend)

                                                
        self.splitter.setSizes([950, 250])

    def setup_toolbar(self):
        """Tạo thanh công cụ chọn khung thời gian."""
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(45)
        self.toolbar.setStyleSheet(
            f"background: {Theme.CARD}; border-bottom: 1px solid {Theme.BORDER};"
        )
        tb_layout = QHBoxLayout(self.toolbar)

        self.lbl_info = QLabel("Sẵn sàng.")
        self.lbl_info.setStyleSheet(
            f"color: {Theme.TEXT_SUB}; font-weight: bold; padding-left: 10px;"
        )
        tb_layout.addWidget(self.lbl_info)
        tb_layout.addStretch()

        self.btn_group = []
        for tf in ["1m", "3m", "5m", "15m", "1h", "4h", "1d"]:
            btn = QPushButton(tf)
            btn.setFixedSize(40, 26)
            btn.clicked.connect(lambda checked, t=tf: self.change_timeframe(t))
            btn.setStyleSheet(
                f"background: {Theme.BORDER}; color: {Theme.TEXT_MAIN};"
                if tf == "1m"
                else f"background: transparent; color: {Theme.TEXT_SUB};"
            )
            tb_layout.addWidget(btn)
            self.btn_group.append(btn)

        self.left_layout.addWidget(self.toolbar)

    def load_regime_data(self, df: pl.DataFrame, symbol="Regime_Chart"):
        """Nạp DataFrame có cột regime vào biểu đồ và kích hoạt khung 1m."""
        if isinstance(df, pd.DataFrame):
            if "timestamp" not in df.columns:
                df = df.reset_index()
            df = pl.from_pandas(df)

        if df.is_empty():
            return
        if df["timestamp"].dtype == pl.Utf8:
            df = df.with_columns(
                pl.col("timestamp").str.strptime(pl.Datetime, strict=False)
            )

        self.df_base_1m = df.sort("timestamp")
        self.current_symbol = symbol
        self.change_timeframe("1m")

    def change_timeframe(self, tf):
        """Đổi khung thời gian và khởi động worker resample bất đồng bộ."""
        for btn in self.btn_group:
            btn.setStyleSheet(
                f"background: {Theme.BORDER}; color: {Theme.TEXT_MAIN}; font-weight: bold;"
                if btn.text() == tf
                else f"background: transparent; color: {Theme.TEXT_SUB}; font-weight: bold;"
            )

        self.lbl_info.setText(f"⏳ Đang tải khung {tf}...")
        self.chart.current_tf = tf

        self.resample_worker = DataProcessorWorker(self.df_base_1m, tf)
        self.resample_worker.finished.connect(self.on_resample_finished)
        self.resample_worker.start()

    def on_resample_finished(self, df_resampled, timestamps):
        """Cập nhật biểu đồ khi worker resample hoàn thành."""
        self.chart.df_current = df_resampled
        self.chart.current_timestamps = timestamps
        self.chart.scroll_offset = 0
        self.lbl_info.setText(
            f" 📊 {self.current_symbol} | Khung: {self.chart.current_tf} | {df_resampled.height} nến"
        )
        self.chart.update()


def hien_thi_regime_tren_ui(df):
    """Khởi động ứng dụng Qt và hiển thị biểu đồ regime cho DataFrame đầu vào."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    window = CandlestickChartWidget()
    window.load_regime_data(df)
    window.setWindowTitle("KAIROS Regime Visualizer v2.0")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
                                                                   
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = CandlestickChartWidget()
    window.setWindowTitle("KAIROS Regime Visualizer v2.0")
    window.show()
    sys.exit(app.exec())
