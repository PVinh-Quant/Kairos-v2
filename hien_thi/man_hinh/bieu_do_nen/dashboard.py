"""bieu_do_nen/dashboard.py — CandlestickChartWidget: toolbar + chart + bảng lệnh + bus."""
import sys
import bisect
import polars as pl
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QApplication, QSplitter,
)
from PyQt6.QtCore import Qt
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from hien_thi.giao_dien.theme import Theme
from .tien_ich import to_datetime
from .worker import BacktestWorker, DataProcessorWorker
from .bang import TradesTableWidget
from .chart import CoreCandlestickChart
class CandlestickChartWidget(QWidget):
    def __init__(self):
        """Khởi tạo widget chính bao gồm toolbar, biểu đồ nến, và bảng lệnh."""
        super().__init__()
        self.setMinimumSize(1200, 700)
        self.setStyleSheet(f"background-color: {Theme.BG};")

        self.dict_dfs = {}
        self.raw_trades = []
        self.current_symbol = "UNKNOWN"
        self.df_base_1m = pl.DataFrame()
        self.worker = None
        self.phien = None                                                                      
        self._active_strategy = None                                                            
        self._active_strategy_label = ""

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

        self.table = TradesTableWidget()
        self.table.cellClicked.connect(self.on_table_click)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.table)
                                                                                
                                                                   
        self.splitter.setSizes([1000, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(1, False)

    def setup_toolbar(self):
        """Tạo toolbar với nút chạy backtest, combo chọn symbol và các nút timeframe."""
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(45)
        self.toolbar.setStyleSheet(
            f"background: {Theme.CARD}; border-bottom: 1px solid {Theme.BORDER};"
        )
        tb_layout = QHBoxLayout(self.toolbar)

        self.btn_load = QPushButton("▶ Chạy Vector Backtest")
        self.btn_load.setStyleSheet(
            f"background-color: {Theme.ACCENT}; color: #FFF; font-weight: bold; padding: 6px 15px; border-radius: 4px; border: none;"
        )
        self.btn_load.clicked.connect(self.run_backtest)
        tb_layout.addWidget(self.btn_load)

                                                                                         
        self.btn_chay_cl = QPushButton("▶ Chạy chiến lược này")
        self.btn_chay_cl.setStyleSheet(
            f"background-color: {Theme.WIN}; color: #FFF; font-weight: bold; padding: 6px 15px; border-radius: 4px; border: none;"
        )
        self.btn_chay_cl.setEnabled(False)
        self.btn_chay_cl.clicked.connect(self.run_chien_luoc_active)
        tb_layout.addWidget(self.btn_chay_cl)

        self.combo_symbol = QComboBox()
        self.combo_symbol.setStyleSheet(
            f"background: {Theme.BG}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BORDER}; padding: 4px; min-width: 100px;"
        )
        self.combo_symbol.currentTextChanged.connect(self.on_symbol_changed)
        tb_layout.addWidget(self.combo_symbol)

        self.lbl_info = QLabel("San sang.")
        self.lbl_info.setStyleSheet(
            f"color: {Theme.TEXT_SUB}; font-weight: bold; padding-left: 10px;"
        )
        tb_layout.addWidget(self.lbl_info)

        self.lbl_chien_luoc = QLabel("Chiến lược: (toàn bộ)")
        self.lbl_chien_luoc.setStyleSheet(
            f"color: {Theme.ACCENT}; font-weight: bold; padding-left: 14px;"
        )
        tb_layout.addWidget(self.lbl_chien_luoc)
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

    def run_backtest(self):
        """Slot nút '▶ Chạy Vector Backtest' — chạy TOÀN BỘ chiến lược active (như cũ)."""
        self._chay_worker(None, "toàn bộ")

    def run_chien_luoc_active(self):
        """Chạy ĐÚNG chiến lược đang nhận từ bus (màn Tối ưu gửi sang)."""
        if not self._active_strategy:
            self.lbl_info.setText("Chua co chien luoc tu Toi uu.")
            return
        self._chay_worker(self._active_strategy, self._active_strategy_label)

    def _chay_worker(self, strategy_config, nhan):
        """Khởi động BacktestWorker (None = toàn bộ; dict = 1 chiến lược) ở luồng nền."""
        self.lbl_info.setText(f"Dang xu ly Vector... [{nhan}]")
        self.btn_load.setEnabled(False)
        self.btn_chay_cl.setEnabled(False)
        self.btn_load.setText("⏳ Đang chạy...")
        self.worker = BacktestWorker(strategy_config)
        self.worker.finished.connect(self.on_backtest_finished)
        self.worker.error.connect(self.on_backtest_error)
        self.worker.start()

                                                                               
    def gan_phien(self, phien):
        """Nhận bus phiên: lắng nghe chiến lược active do màn Tối ưu gửi sang."""
        self.phien = phien
        if phien is None:
            return
        phien.strategy_changed.connect(self._nhan_chien_luoc)
        if phien.active_strategy:                                               
            self._nhan_chien_luoc(phien.active_strategy)

    def _nhan_chien_luoc(self, result):
        """Lưu chiến lược active từ bus + cập nhật nhãn/nút. KHÔNG tự chạy (tránh backtest
        nặng mỗi lần optimizer xong) — người dùng bấm '▶ Chạy chiến lược này' để xem."""
        if not result:
            self._active_strategy = None
            self._active_strategy_label = ""
            self.lbl_chien_luoc.setText("Chiến lược: (toàn bộ)")
            self.btn_chay_cl.setEnabled(False)
            return
        self._active_strategy = result.get("best_params", result)
        self._active_strategy_label = (
            result.get("combo_label") or result.get("strategy_key") or "active"
        )
        self.lbl_chien_luoc.setText(f"Chiến lược: {self._active_strategy_label}")
        worker = getattr(self, "worker", None)
        if not (worker is not None and worker.isRunning()):
            self.btn_chay_cl.setEnabled(True)

    def on_backtest_finished(self, trades, dict_dfs):
        """Xử lý kết quả backtest, cập nhật combo symbol và render lại biểu đồ."""
        self.raw_trades = (
            trades.to_dicts()
            if hasattr(trades, "to_dicts")
            else trades if isinstance(trades, list) else []
        )
        if not dict_dfs:
            self.lbl_info.setText("Du lieu trong.")
            self.btn_load.setEnabled(True)
            self.btn_chay_cl.setEnabled(bool(self._active_strategy))
            self.btn_load.setText("▶ Chạy Vector Backtest")
            return

        self.dict_dfs = dict_dfs
        self.combo_symbol.blockSignals(True)
        self.combo_symbol.clear()
        self.combo_symbol.addItems(list(self.dict_dfs.keys()))
        self.combo_symbol.blockSignals(False)
        if self.combo_symbol.count() > 0:
            self.on_symbol_changed(self.combo_symbol.currentText())
        self.btn_load.setEnabled(True)
        self.btn_chay_cl.setEnabled(bool(self._active_strategy))
        self.btn_load.setText("▶ Chạy Vector Backtest")

    def on_backtest_error(self, err):
        """Hiển thị thông báo lỗi và kích hoạt lại nút chạy backtest."""
        self.lbl_info.setText(f"Loi: {err}")
        self.btn_load.setEnabled(True)
        self.btn_chay_cl.setEnabled(bool(self._active_strategy))
        self.btn_load.setText("▶ Chạy Vector Backtest")

    def calculate_hold_time(self, en_t, ex_t):
        """Tính thời gian giữ lệnh dạng chuỗi (vd: 2h 30m, 15m)."""
        if not en_t or not ex_t:
            return "-"
        delta = ex_t - en_t
        hours, rem = divmod(delta.total_seconds(), 3600)
        return f"{int(hours)}h {int(rem // 60)}m" if hours > 0 else f"{int(rem // 60)}m"

    def process_and_extract_trades(self, raw_trades, df_base):
        """Chuẩn hóa danh sách lệnh từ nhiều định dạng về cấu trúc thống nhất để vẽ lên chart."""
        symbol = self.combo_symbol.currentText()
        symbol_trades = [t for t in (raw_trades or []) if t.get("Symbol") == symbol]

                                                                                                    
        symbol_trades.sort(key=lambda x: x.get("Entry_Time") if x.get("Entry_Time") else x.get("Time"))

        clean_trades = []
        for i, t in enumerate(symbol_trades):
            en_t = to_datetime(t.get("Entry_Time"))
            ex_t = to_datetime(t.get("Time"))
            if not en_t or not ex_t:
                continue

            hold_time_str = self.calculate_hold_time(en_t, ex_t)
            
            clean_trades.append({
                "id": i + 1,
                "direction": "Long" if str(t.get("Loại")).upper() in ("BUY", "LONG") else "Short",
                "entry_time": en_t,
                "exit_time": ex_t,
                "entry_price": float(t.get("Giá vào", 0.0)),
                "exit_price": float(t.get("Giá đóng", 0.0)),
                "price_change": float(t.get("PnL", 0.0)),                                   
                "hold_time": hold_time_str,
            })
        return clean_trades

    def on_symbol_changed(self, symbol):
        """Cập nhật dữ liệu biểu đồ và lệnh khi người dùng chọn symbol khác."""
        df = self.dict_dfs.get(symbol)
        if df is None:
            return

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

                                                                                    
        self.chart.trades = self.process_and_extract_trades(
            self.raw_trades, self.df_base_1m
        )
        self.change_timeframe("1m")

    def change_timeframe(self, tf):
        """Chuyển timeframe biểu đồ và khởi động DataProcessorWorker resample dữ liệu."""
        for btn in self.btn_group:
            btn.setStyleSheet(
                f"background: {Theme.BORDER}; color: {Theme.TEXT_MAIN}; font-weight: bold;"
                if btn.text() == tf
                else f"background: transparent; color: {Theme.TEXT_SUB}; font-weight: bold;"
            )

        self.lbl_info.setText(f"Dang tai khung {tf}...")
        self.chart.current_tf = tf

        self.resample_worker = DataProcessorWorker(self.df_base_1m, tf)
        self.resample_worker.finished.connect(self.on_resample_finished)
        self.resample_worker.start()

    def on_resample_finished(self, df_resampled, timestamps):
        """Cập nhật biểu đồ và bảng lệnh sau khi DataProcessorWorker hoàn thành."""
        self.chart.df_current = df_resampled
        self.chart.current_timestamps = timestamps
        self.chart.scroll_offset = 0

        closed_trades = [t for t in self.chart.trades if "exit_time" in t]

        self.lbl_info.setText(
            f" {self.combo_symbol.currentText()} | {self.chart.current_tf} | {df_resampled.height} nen | Lenh: {len(closed_trades)}"
        )

        self.table.load_trades(self.chart.trades)
        self.chart.update()

    def on_table_click(self, row, col):
        """Scroll biểu đồ đến nến entry của lệnh được click trong bảng."""
        if not self.chart.current_timestamps or row >= self.table.rowCount():
            return
        t_id = self.table.item(row, 0).text()
        trade = next((t for t in self.chart.trades if str(t.get("id")) == t_id), None)
        if not trade or "entry_time" not in trade:
            return

        idx = bisect.bisect_left(self.chart.current_timestamps, trade["entry_time"])
        if idx < len(self.chart.current_timestamps):
            visible = (self.chart.width() - 70) // (
                self.chart.candle_width + self.chart.candle_gap
            )
            self.chart.scroll_offset = max(
                0, len(self.chart.current_timestamps) - idx - int(visible / 2)
            )
            self.chart.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CandlestickChartWidget()
    window.setWindowTitle("KAIROS Professional Quant UI")
    window.show()
    sys.exit(app.exec())
