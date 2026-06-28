"""backtest/worker.py — QThread chạy backtest + lọc dữ liệu (luồng nền)."""
import sys
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QRunnable, QThreadPool
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from .tien_ich import execute_filtering_task
try:
    from chuc_nang.backtest_donluong import chay_backtest
except ImportError:
    chay_backtest = None
class BacktestWorker(QThread):
    progress_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(dict)

    def run(self):
        """Chạy backtest trong luồng nền và emit signal cập nhật tiến độ."""

        def on_live_update(data):
            self.progress_signal.emit(data)

        try:
            result = chay_backtest(return_data=True, callback=on_live_update)
            self.finished_signal.emit(result)
        except Exception as e:
            print(f"Lỗi Backtest: {e}")
            self.finished_signal.emit({})





class ProcessWorkerThread(QThread):

    filter_finished = pyqtSignal(list, list, list)

    def __init__(self, df_main, filters, initial_capital, executor_pool):
        """Khởi tạo worker thread với DataFrame, bộ lọc, vốn ban đầu và ThreadPoolExecutor."""
        super().__init__()
        self.df_main = df_main
        self.filters = filters
        self.initial_capital = initial_capital
        self.executor = executor_pool

    def run(self):
        """Gửi execute_filtering_task vào ThreadPool và emit kết quả khi xong."""

        future = self.executor.submit(
            execute_filtering_task, self.df_main, self.filters, self.initial_capital
        )
        try:
            result = future.result()
            self.filter_finished.emit(*result)
        except Exception as e:
            print(f"Lỗi thực thi Thread: {e}")
            self.filter_finished.emit([], [], [])






__all__ = ["BacktestWorker", "ProcessWorkerThread"]
