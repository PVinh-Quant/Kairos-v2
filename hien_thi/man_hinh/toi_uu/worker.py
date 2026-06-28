"""toi_uu/worker.py — QThread tối ưu (ComboWorker / StrategyWorker) gọi bo_dieu_phoi."""
from PyQt6.QtCore import QThread, pyqtSignal
class ComboWorker(QThread):
    status = pyqtSignal(str)
    trial_progress = pyqtSignal(int, int, object)
    finished_combo = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, combo, n_trials, objective_metric="sharpe", logic="and", persistence=1, dataset=None, parent=None):
        super().__init__(parent)
        self.combo = combo
        self.n_trials = int(n_trials)
        self.objective_metric = objective_metric
        self.logic = logic
        self.persistence = int(persistence)
        self.dataset = dataset or {}
        self._stop = False

    def stop(self):
        """Yêu cầu dừng — sẽ kết thúc sau bộ tham số hiện tại."""
        self._stop = True

    def run(self):
        try:
            from toi_uu_hoa.bo_dieu_phoi import run_combo_optimization
            label = " + ".join(f"{c['key']}@{c['tf']}" for c in self.combo)
            self.status.emit("Đang tối ưu chiến lược tổ hợp (Walk-Forward)...")
            result = run_combo_optimization(
                self.combo, n_trials=self.n_trials, silent=False,
                progress_cb=lambda done, total, best: self.trial_progress.emit(done, total, best),
                objective_metric=self.objective_metric,
                logic=self.logic, persistence=self.persistence,
                should_stop=lambda: self._stop,
                override_symbols=self.dataset.get("symbols") or None,
                override_start=self.dataset.get("tu_ngay") or None,
                override_end=self.dataset.get("den_ngay") or None,
            )
            print(f"\n{'=' * 76}\n  ✓ HOÀN TẤT\n{'=' * 76}\n", flush=True)
            self.finished_combo.emit(result)
        except SystemExit as e:
            self.failed.emit(f"Tối ưu bị dừng đột ngột (thiếu dữ liệu/cấu hình): {e}")
        except Exception as e:
            self.failed.emit(str(e))


class StrategyWorker(QThread):
    """Worker tối ưu 1 CHIẾN LƯỢC PLUGIN (M1) — mirror ComboWorker, dùng run_strategy_optimization."""
    status = pyqtSignal(str)
    trial_progress = pyqtSignal(int, int, object)
    finished_combo = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, strategy_key, n_trials, objective_metric="sharpe", parent=None):
        super().__init__(parent)
        self.strategy_key = strategy_key
        self.n_trials = int(n_trials)
        self.objective_metric = objective_metric
        self._stop = False

    def stop(self):
        """Yêu cầu dừng — sẽ kết thúc sau bộ tham số hiện tại."""
        self._stop = True

    def run(self):
        try:
            from toi_uu_hoa.bo_dieu_phoi import run_strategy_optimization
            print(f"\n{'=' * 76}\n  ⚙  TỐI ƯU CHIẾN LƯỢC PLUGIN: {self.strategy_key}  ·  {self.n_trials} bộ\n{'=' * 76}", flush=True)
            self.status.emit("Đang tối ưu chiến lược plugin (Walk-Forward)...")
            result = run_strategy_optimization(
                self.strategy_key, n_trials=self.n_trials, silent=False,
                progress_cb=lambda done, total, best: self.trial_progress.emit(done, total, best),
                objective_metric=self.objective_metric,
                should_stop=lambda: self._stop,
            )
            print(f"\n{'=' * 76}\n  ✓ HOÀN TẤT\n{'=' * 76}\n", flush=True)
            self.finished_combo.emit(result)
        except SystemExit as e:
            self.failed.emit(f"Tối ưu bị dừng đột ngột (thiếu dữ liệu/cấu hình): {e}")
        except Exception as e:
            self.failed.emit(str(e))


__all__ = ["ComboWorker", "StrategyWorker"]
