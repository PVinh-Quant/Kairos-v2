"""backtest/dashboard.py — DraggableDashboard: vỏ màn Backtest (dock kéo-thả)."""
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
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from .dinh_nghia import *
from .tien_ich import funny_quant_runner
from .worker import BacktestWorker, ProcessWorkerThread
from .bieu_do import *
from .lich import CalendarWidget
from .bang import *
from hien_thi.dich_vu.chay_chien_luoc import ChienLuocActiveMixin
from chuc_nang.tai_dung_lenh_vector import la_file_dump_vector, tai_dung_lenh_tu_dump
class DraggableCard(QDockWidget):
    def __init__(self, title, widget, parent=None):
        """Khởi tạo DockWidget có thể kéo thả với tiêu đề và widget nội dung."""
        super().__init__(title, parent)
        self.setWidget(widget)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self.setWindowTitle(title.upper())
        self.setTitleBarWidget(None)

        self.setStyleSheet(f"""
            QDockWidget {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                color: {TEXT_MAIN};
            }}
            QDockWidget::title {{
                background: {CARD_BG};
                text-align: left;
                padding-left: 12px;
                padding-top: 8px;
                padding-bottom: 8px;
                border-bottom: 1px solid {BORDER_COLOR};
                color: {TEXT_SUB};
                font-family: "Segoe UI";
                font-weight: bold;
                font-size: 11px;
            }}
            QDockWidget::close-button, QDockWidget::float-button {{
                border: none;
                background: transparent;
                padding: 0px;
                icon-size: 14px;
                subcontrol-position: right;
                subcontrol-origin: margin;
                right: 5px;
            }}
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
                background: #333;
                border-radius: 3px;
            }}
        """)





class DraggableDashboard(ChienLuocActiveMixin, QMainWindow):
    def __init__(self):
        """Khởi tạo cửa sổ dashboard backtest với toolbar, dock widgets và bộ lọc."""
        super().__init__()
        self.setWindowTitle("Backtest Dashboard")
        self.resize(1600, 900)


        bg = BG_COLOR if "BG_COLOR" in globals() else "#0e0e0e"
        self.setStyleSheet(f"background-color: {bg};")
        self.setDockNestingEnabled(True)


        self.all_trades_raw = []
        self.all_trades_df = pl.DataFrame()
        self.initial_capital = 10000.0
        self.is_started = False
        self.has_finished_once = False
        self.is_ui_paused = False
        self.latest_data_cache = {}
        self.is_filtering = False

        self.worker = None

        self.active_filters = {
            "date": None,
            "symbol": None,
            "side": None,
            "weekday": None,
            "hour": None,
        }


        from concurrent.futures import ThreadPoolExecutor

        self.executor_pool = ThreadPoolExecutor(max_workers=1)
        self.current_worker = None


        self._init_ui_elements()
        self._init_widgets()
        self._init_layout()


        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_status_animation)
        self.anim_timer.setInterval(100)








    def _init_ui_elements(self):
        """Khởi tạo Toolbar và các nút điều khiển"""
        c_bg = CARD_BG if "CARD_BG" in globals() else "#141414"
        b_color = BORDER_COLOR if "BORDER_COLOR" in globals() else "#2a2a2a"
        acc_color = ACCENT_COLOR if "ACCENT_COLOR" in globals() else "#C8AA6E"
        t_sub = TEXT_SUB if "TEXT_SUB" in globals() else "#999999"

        toolbar = QToolBar("Main Toolbar")
        toolbar.setStyleSheet(
            f"background: {c_bg}; border-bottom: 1px solid {b_color}; spacing: 10px; padding: 5px;"
        )
        self.addToolBar(toolbar)


        self.btn_control = QPushButton("▶ Bắt đầu Backtest")
        self.btn_control.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_control.setStyleSheet(
            f"background-color: {acc_color}; color: #000; font-weight: bold; padding: 6px 15px; border-radius: 4px;"
        )
        self.btn_control.clicked.connect(self.on_btn_control_clicked)
        toolbar.addWidget(self.btn_control)


        self.btn_load_csv = QPushButton("📂 Mở File CSV")
        self.btn_load_csv.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_load_csv.setStyleSheet(
            "background-color: #2962FF; color: #FFF; font-weight: bold; padding: 6px 15px; border-radius: 4px;"
        )
        self.btn_load_csv.clicked.connect(self.on_btn_load_csv_clicked)
        toolbar.addWidget(self.btn_load_csv)

        self.lbl_status = QLabel("  Sẵn sàng.")
        self.lbl_status.setStyleSheet(
            f"color: {t_sub}; font-weight: bold; margin-left: 10px;"
        )
        toolbar.addWidget(self.lbl_status)
        self.setCentralWidget(QLabel(""))
        self.centralWidget().setVisible(False)

    def _init_widgets(self):
        """Khởi tạo tất cả các Widget biểu đồ và bảng"""
        self.widget_pnl = DailyPnLBarChart()
        self.widget_cal = CalendarWidget()
        self.widget_stats = BacktestSummaryWidget()
        self.widget_coins = CoinResultWidget()
        self.widget_dist_w = self.create_dist_widget()
        self.widget_asset = TotalAssetChart()
        self.widget_history = TradeHistoryWidget()
        self.widget_Scatter = TradeScatterWidget()
        self.widget_ls = LongShortWidget()


        self.widget_cal.date_selected.connect(self.handle_date_filter)
        self.widget_pnl.date_clicked.connect(self.handle_date_filter)
        self.widget_coins.coin_selected_signal.connect(self.handle_coin_filter)
        self.widget_ls.side_clicked.connect(self.handle_side_filter)
        self.day_dist.bar_clicked.connect(self.handle_dist_filter)
        self.hour_dist.bar_clicked.connect(self.handle_dist_filter)

    def create_dist_widget(self):
        """Hàm bọc cho hai biểu đồ phân phối lệnh"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self.day_dist = DistributionChart("day")
        self.hour_dist = DistributionChart("hour")
        layout.addWidget(self.day_dist)
        layout.addWidget(self.hour_dist)
        return container

    def _init_layout(self):
        """Sắp xếp các DockWidget trên màn hình chính"""
        self.dock_pnl = DraggableCard("Lãi Lỗ Hằng Ngày", self.widget_pnl)
        self.dock_cal = DraggableCard("Lịch Giao Dịch", self.widget_cal)
        self.dock_stats = DraggableCard("Chỉ Số Hiệu Suất", self.widget_stats)
        self.dock_coins = DraggableCard("Kết Quả Theo Coin", self.widget_coins)
        self.dock_dist = DraggableCard("Phân Phối Lệnh", self.widget_dist_w)
        self.dock_asset = DraggableCard("Tổng Tài Sản", self.widget_asset)
        self.dock_history = DraggableCard("Chi Tiết Lệnh", self.widget_history)
        self.dock_Scatter = DraggableCard("Phân tích giữ lệnh", self.widget_Scatter)
        self.dock_ls = DraggableCard("Long vs Short", self.widget_ls)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_stats)
        self.splitDockWidget(self.dock_stats, self.dock_coins, Qt.Orientation.Vertical)

        self.tabifyDockWidget(self.dock_coins, self.dock_ls)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_pnl)
        self.splitDockWidget(self.dock_pnl, self.dock_dist, Qt.Orientation.Horizontal)
        self.splitDockWidget(self.dock_dist, self.dock_asset, Qt.Orientation.Vertical)

        self.tabifyDockWidget(self.dock_dist, self.dock_Scatter)
        self.splitDockWidget(self.dock_pnl, self.dock_history, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_pnl, self.dock_cal, Qt.Orientation.Horizontal)

        self.resizeDocks(
            [self.dock_pnl, self.dock_Scatter, self.dock_stats],
            [1050, 350, 300],
            Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [self.dock_pnl, self.dock_history], [250, 450], Qt.Orientation.Vertical
        )
        self.resizeDocks(
            [self.dock_Scatter, self.dock_dist], [300, 400], Qt.Orientation.Vertical
        )
        self.resizeDocks(
            [self.dock_stats, self.dock_coins, self.dock_ls],
            [250, 400, 150],
            Qt.Orientation.Vertical,
        )




    def process_new_data(self, data):
        """Chuẩn hóa DataFrame lệnh với các cột filter và gọi apply_filters."""
        trades = data.get("trades", [])
        self.initial_capital = float(data.get("initial_capital", 10000.0))
        if not trades:
            return

        df = pl.DataFrame(trades)

        for col in ["time_close", "time_open"]:
            if col in df.columns and df[col].dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col(col).str.strptime(pl.Datetime, strict=False)
                )

        self.all_trades_df = df.with_columns(
            [
                pl.col("time_close").dt.date().alias("filter_date"),
                pl.col("time_close").dt.weekday().alias("filter_weekday"),
                pl.col("time_close").dt.hour().alias("filter_hour"),
                pl.when(pl.col("side").str.to_lowercase().str.strip_chars() == "buy")
                .then(pl.lit("long"))
                .when(pl.col("side").str.to_lowercase().str.strip_chars() == "sell")
                .then(pl.lit("short"))
                .otherwise(pl.col("side").str.to_lowercase())
                .alias("filter_side"),
                pl.col("symbol").str.to_uppercase().str.strip_chars(),
            ]
        )

        self.apply_filters()

    def handle_date_filter(self, d):
        """Toggle bộ lọc theo ngày và áp dụng lại toàn bộ filter."""
        self.active_filters["date"] = (
            None if self.active_filters.get("date") == d else d
        )
        self.apply_filters()

    def apply_filters(self):
        """Khởi động ProcessWorkerThread để lọc dữ liệu trong luồng nền."""
        if self.all_trades_df.is_empty() or self.is_filtering:
            return

        self.is_filtering = True
        self.current_worker = ProcessWorkerThread(
            self.all_trades_df,
            self.active_filters,
            self.initial_capital,
            self.executor_pool,
        )
        self.current_worker.filter_finished.connect(self.on_filtering_finished)
        self.current_worker.start()

    def on_filtering_finished(self, filtered_trades, equity_curve, coin_list_trades):
        """Nhận kết quả từ worker thread và cập nhật toàn bộ UI."""
        self.update_ui_filtered(filtered_trades, equity_curve, coin_list_trades)
        self.is_filtering = False
        self.lbl_status.setText(f"✅ Đã lọc: {len(filtered_trades)} lệnh")

    def update_ui_filtered(self, trades, equity, coin_list_trades):
        """Cập nhật tất cả widget với dữ liệu đã lọc, chuẩn hóa kiểu dữ liệu trước."""

        df_trades = pl.DataFrame(trades)
        df_coin_list = pl.DataFrame(coin_list_trades)


        if not df_trades.is_empty():
            cols_to_fix = []

            if (
                "time_close" in df_trades.columns
                and df_trades["time_close"].dtype == pl.Utf8
            ):
                cols_to_fix.append(
                    pl.col("time_close").str.strptime(pl.Datetime, strict=False)
                )


            if (
                "time_open" in df_trades.columns
                and df_trades["time_open"].dtype == pl.Utf8
            ):
                cols_to_fix.append(
                    pl.col("time_open").str.strptime(pl.Datetime, strict=False)
                )


            if "pnl_usd" in df_trades.columns:
                cols_to_fix.append(pl.col("pnl_usd").cast(pl.Float64))

            if cols_to_fix:
                df_trades = df_trades.with_columns(cols_to_fix)

        packet = {"trades": trades, "equity_curve": equity}
        self.widget_stats.update_data(packet)
        self.widget_asset.update_data(equity)

        wd_val = self.active_filters["weekday"]
        wd_idx = (wd_val - 1) if wd_val is not None else None


        widgets_to_update = [
            (self.widget_pnl, "update_data", df_trades),
            (self.widget_ls, "update_data", df_trades, self.active_filters["side"]),
            (self.widget_Scatter, "update_data", df_trades),
            (
                self.widget_coins,
                "update_data",
                df_coin_list,
                self.active_filters["symbol"],
            ),

            (self.day_dist, "update_data", df_trades, wd_idx),
            (self.hour_dist, "update_data", df_trades, self.active_filters["hour"]),
        ]

        for widget, method, *args in widgets_to_update:
            try:

                if hasattr(widget, method):
                    getattr(widget, method)(*args)
            except Exception as e:
                print(f"Lỗi render tại {widget.__class__.__name__}: {e}")


        recent_trades = trades[-100:] if len(trades) > 100 else trades
        self.widget_history.update_data(recent_trades)


        self.widget_cal.set_trades(trades, self.active_filters["date"])




    def on_btn_control_clicked(self):
        """Xử lý click nút điều khiển: bắt đầu backtest mới hoặc tạm dừng."""
        if getattr(self, "is_view_mode", False):
            self.is_view_mode = False
            self.is_started = False


        if not self.is_started:
            self.start_backtest_process()
            self.btn_control.setText("⏸ Tạm dừng")
        else:

            pass

    def start_backtest_process(self):
        """Xóa dữ liệu cũ, khởi tạo BacktestWorker mới và bắt đầu chạy."""
        if self.is_started:
            return


        self.reset_dashboard_data()


        self.lbl_status.setText("🚀 Đang khởi động Backtest...")
        self.is_started = True
        self.btn_control.setText("⏸ Tạm dừng")



        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait()
            self.worker = None


        self._ap_dung_chien_luoc_ghi_de()


        self.worker = BacktestWorker()


        self.worker.progress_signal.connect(self.on_live_update)
        self.worker.finished_signal.connect(self.on_process_finished)
        if hasattr(self.worker, "error_signal"):
            self.worker.error_signal.connect(self.on_worker_error)


        self.worker.start()

        if hasattr(self, "anim_timer"):
            self.anim_timer.start()

    def on_live_update(self, data):
        """Nhận cập nhật trực tiếp từ BacktestWorker.

        TIẾT LƯU (throttle): KHÔNG dựng lại DataFrame + render toàn bộ widget trên MỖI
        lệnh đóng — backtest hàng nghìn lệnh sẽ phát tín hiệu dồn dập làm nghẽn event loop
        → UI treo, "giữa chừng không hiện gì". Chỉ render tối đa ~2-3 lần/giây; dữ liệu mới
        nhất luôn được cache và kết quả cuối cùng được render đầy đủ ở on_process_finished.
        """
        self.latest_data_cache = data
        if self.is_ui_paused:
            return
        import time
        now = time.monotonic()
        if now - getattr(self, "_last_live_render", 0.0) < 0.4:
            return
        self._last_live_render = now
        self.process_new_data(data)

    def on_process_finished(self, result):
        """Xử lý kết quả cuối cùng khi backtest hoàn tất và cập nhật nút điều khiển."""
        self.is_started = False
        self.btn_control.setText("✔️ Xong")
        self.btn_control.setEnabled(False)
        if hasattr(self, "anim_timer"):
            self.anim_timer.stop()
        if result:

            self._last_live_render = 0.0
            self.is_filtering = False
            self.process_new_data(result)

    def update_status_animation(self):
        """Cập nhật animation ASCII trên thanh trạng thái khi backtest đang chạy."""
        if not self.is_ui_paused:
            self.lbl_status.setText(funny_quant_runner())

    def safe_update_widget(self, widget, method, *args):
        """Gọi method của widget một cách an toàn nếu method tồn tại."""
        if hasattr(widget, method):
            getattr(widget, method)(*args)

    def handle_coin_filter(self, c):
        """Toggle bộ lọc theo coin và áp dụng lại toàn bộ filter."""
        self.active_filters["symbol"] = (
            None if self.active_filters.get("symbol") == c else c
        )
        self.apply_filters()

    def handle_dist_filter(self, i, t):
        """Toggle bộ lọc theo ngày trong tuần hoặc giờ từ biểu đồ phân phối."""
        if t == "day":
            val = (i + 1) if i != -1 else None
            self.active_filters["weekday"] = val
        else:
            val = i if i != -1 else None
            self.active_filters["hour"] = val

        self.apply_filters()

    def handle_side_filter(self, s):
        """Toggle bộ lọc theo chiều lệnh (long/short) và áp dụng lại filter."""
        norm_s = s.lower() if s else None
        self.active_filters["side"] = (
            None if self.active_filters.get("side") == norm_s else norm_s
        )
        self.apply_filters()




    def on_btn_load_csv_clicked(self):
        """Mở dialog chọn file CSV, reset dashboard rồi load dữ liệu vào."""
        if self.worker is not None:
            self.worker = None

        self.is_started = False
        if hasattr(self, "anim_timer"):
            self.anim_timer.stop()
        self.btn_control.setText("▶ Bắt đầu Backtest")


        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file CSV", "", "CSV Files (*.csv)"
        )

        if file_path:

            self.reset_dashboard_data()

            self.load_csv_data(file_path)
        else:
            self.lbl_status.setText("Đã hủy chọn file.")


    VECTOR_COL_MAP = {
        "Symbol": "symbol",
        "Loại": "side",
        "Giá vào": "entry",
        "Giá đóng": "exit",
        "Leverage": "leverage",
        "PnL": "pnl_usd",
        "Time": "time_close",
        "Balance": "balance",
        "Strategy": "strategy",
        "Entry_Time": "time_open",
        "SL_pct": "sl_pct",
        "TP_pct": "tp_pct",
        "Exit_Reason": "reason",
        "Regime": "regime",
    }

    def _chuan_hoa_lenh_vector(self, df: pl.DataFrame) -> pl.DataFrame:
        """Chuẩn hóa file kết quả backtest vector về schema của engine bar-to-bar.

        Engine bar-to-bar lưu cột lowercase (symbol, side, pnl_usd…); còn vector trả về
        cột tiếng Việt viết hoa (Symbol, Loại, Giá vào, PnL…). Nếu df đã đúng schema engine
        thì giữ nguyên; nếu là file vector thì đổi tên cột, map chiều lệnh LONG/SHORT -> buy/sell
        và suy ra ROI (pnl_pct) vì vector không lưu sẵn cột này.
        """

        if not any(c in df.columns for c in ("PnL", "Giá vào", "Loại")):
            return df

        rename_map = {k: v for k, v in self.VECTOR_COL_MAP.items() if k in df.columns}
        df = df.rename(rename_map)


        if "side" in df.columns:
            side_norm = pl.col("side").cast(pl.Utf8).str.to_uppercase().str.strip_chars()
            df = df.with_columns(
                pl.when(side_norm == "LONG")
                .then(pl.lit("buy"))
                .when(side_norm == "SHORT")
                .then(pl.lit("sell"))
                .otherwise(pl.col("side").cast(pl.Utf8).str.to_lowercase())
                .alias("side")
            )


        if "pnl_pct" not in df.columns and all(
            c in df.columns for c in ("entry", "exit", "leverage", "side")
        ):
            df = df.with_columns(
                pl.when(pl.col("entry") == 0)
                .then(0.0)
                .when(pl.col("side") == "buy")
                .then((pl.col("exit") - pl.col("entry")) / pl.col("entry"))
                .otherwise((pl.col("entry") - pl.col("exit")) / pl.col("entry"))
                .mul(pl.col("leverage").cast(pl.Float64))
                .alias("pnl_pct")
            )

        return df

    def load_csv_data(self, file_path):
        """Đọc file CSV (engine bar-to-bar, backtest vector, HOẶC dump OHLCV vector), chuẩn hóa cột rồi nạp vào dashboard."""
        try:
            self.lbl_status.setText(f"⏳ Đang đọc file: {file_path}...")


            header_cols = pl.read_csv(file_path, n_rows=1).columns

            if la_file_dump_vector(header_cols):


                self.lbl_status.setText("⏳ Đang tái dựng lệnh từ file dump OHLCV vector…")
                QApplication.processEvents()
                df = tai_dung_lenh_tu_dump(file_path)
                if df.is_empty():
                    self.lbl_status.setText(
                        "⚠️ File dump vector không tạo ra lệnh nào (không có tín hiệu vào lệnh trong khoảng dữ liệu)."
                    )
                    return
            else:
                df = pl.read_csv(file_path, infer_schema_length=10000)


            df = self._chuan_hoa_lenh_vector(df)

            required_columns = ["symbol", "side", "time_close", "pnl_usd"]
            thieu_cot = [c for c in required_columns if c not in df.columns]
            if thieu_cot:
                self.lbl_status.setText(
                    f"⚠️ File CSV không hợp lệ — thiếu cột: {', '.join(thieu_cot)}"
                )
                return

            trades_list = df.to_dicts()

            data_packet = {
                "trades": trades_list,
                "initial_capital": 10000.0,
                "equity_curve": [],
            }

            self.process_new_data(data_packet)

            self.lbl_status.setText(f"📂 Chế độ xem file: {len(trades_list)} lệnh")

            self.btn_control.setText("▶ Chạy Backtest Mới")
            self.btn_control.setEnabled(True)

            self.latest_data_cache = {}
            self.is_started = False

        except Exception as e:
            print(f"Lỗi: {e}")

    def on_worker_error(self, err_msg):
        """Hiển thị dialog lỗi và reset trạng thái nút khi backtest gặp exception."""
        self.is_started = False
        self.anim_timer.stop()
        self.btn_control.setText("▶ Bắt đầu Backtest")
        self.lbl_status.setText("❌ Đã xảy ra lỗi!")

        QMessageBox.critical(self, "Lỗi Backtest", err_msg)

    def reset_dashboard_data(self):
        """Xóa toàn bộ dữ liệu và reset tất cả widget về trạng thái rỗng."""
        self.all_trades_df = pl.DataFrame()
        self.latest_data_cache = {}
        self.active_filters = {
            "date": None,
            "symbol": None,
            "side": None,
            "weekday": None,
            "hour": None,
        }

        empty_df = pl.DataFrame()
        empty_list = []

        self.safe_update_widget(self.widget_pnl, "update_data", empty_df)
        self.safe_update_widget(self.widget_asset, "update_data", empty_list)
        self.safe_update_widget(
            self.widget_stats, "update_data", {"trades": [], "equity_curve": []}
        )
        self.safe_update_widget(self.widget_history, "update_data", empty_list)
        self.safe_update_widget(self.widget_coins, "update_data", empty_df, None)
        self.safe_update_widget(self.widget_ls, "update_data", empty_df, None)
        self.safe_update_widget(self.widget_Scatter, "update_data", empty_df)

        self.widget_cal.set_trades([], None)

        self.safe_update_widget(self.day_dist, "update_data", empty_df, None)
        self.safe_update_widget(self.hour_dist, "update_data", empty_df, None)

        self.lbl_status.setText("🧹 Đã xóa dữ liệu cũ.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = DraggableDashboard()
    window.show()
    sys.exit(app.exec())
