"""bieu_do_nen/worker.py — QThread chạy vector backtest + resample khung (luồng nền)."""
import sys
import polars as pl
from PyQt6.QtCore import QThread, pyqtSignal
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from .tien_ich import to_datetime

try:
    from chuc_nang.vectorized_backtest import vectorized_backtest
except ImportError:
    vectorized_backtest = None
class BacktestWorker(QThread):
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, strategy_config=None, dataset=None, parent=None):
        """strategy_config: best_params 1 chiến lược (None = chạy toàn bộ theo config)."""
        super().__init__(parent)
        self.strategy_config = strategy_config
        self.dataset = dataset

    def run(self):
        """Chạy vectorized backtest trong luồng nền và emit kết quả khi xong."""
        try:
            if vectorized_backtest is None:
                self.error.emit("Không tìm thấy hàm vectorized_backtest")
                return
            strategies = None
            if self.strategy_config:
                                                                                        
                from chien_luoc.quan_ly_chien_luoc_vectorized import xay_strategies_tu_config
                strategies = xay_strategies_tu_config(self.strategy_config)
            trades, dict_dfs = vectorized_backtest(strategies=strategies, dataset=self.dataset)
            self.finished.emit(trades, dict_dfs)
        except Exception as e:
            self.error.emit(str(e))


class DataProcessorWorker(QThread):
    finished = pyqtSignal(object, list)

    def __init__(self, df_base, tf):
        """Khởi tạo worker xử lý resample dữ liệu sang timeframe đích."""
        super().__init__()
        self.df_base = df_base
        self.tf = tf

    def run(self):
        """Resample DataFrame sang timeframe đích và emit kết quả cùng danh sách timestamp."""
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

                                                     
                for col_name in ["signal", "entry_signal", "buy_score", "sell_score"]:
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


                                            
                              
