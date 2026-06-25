"""
hien_thi/dich_vu/phien_nghien_cuu.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PhienNghienCuu — BUS TRẠNG THÁI DÙNG CHUNG của lớp hiển thị ("phiên nghiên cứu").

Giữ 2 thứ mà mọi màn hình cùng quan tâm:
    • active_dataset  : bộ dữ liệu đang nghiên cứu (DataPool item / dict).
    • active_strategy : chiến lược đang nghiên cứu (result["best_params"] từ Tối ưu).

Màn Tối ưu (GÓC) GHI vào đây; Biểu đồ nến / Backtest / Demo / Realtime ĐỌC ra.
Nhờ tín hiệu Qt, đặt giá trị mới ở 1 nơi → mọi nơi subscribe tự cập nhật → các tab
luôn nói về cùng "chiến lược + dữ liệu" đang nghiên cứu.

Cách dùng:
    phien.dataset_changed.connect(self._on_dataset)    # subscribe (ĐỌC)
    phien.strategy_changed.connect(self._on_strategy)
    phien.set_active_strategy(result)                   # publish (GHI + phát tín hiệu)
    ds = phien.active_dataset                           # đọc giá trị hiện tại

Vòng đời: 1 instance/cửa sổ, do `hien_thi.app.ung_dung` tạo và tiêm vào từng màn
(đặt thuộc tính `widget.phien`, gọi `widget.gan_phien(phien)` nếu màn có định nghĩa).
"""

from PyQt6.QtCore import QObject, pyqtSignal


class PhienNghienCuu(QObject):
    """Bus trạng thái dùng chung giữa các màn hình của 1 cửa sổ ứng dụng."""

                                                                       
    dataset_changed = pyqtSignal(object)
    strategy_changed = pyqtSignal(object)
                                                                                   
                                                                                      
    yeu_cau_xem_man = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_dataset = None
        self._active_strategy = None

                                                                               
    @property
    def active_dataset(self):
        """Bộ dữ liệu đang nghiên cứu (None nếu chưa chọn)."""
        return self._active_dataset

    def set_active_dataset(self, dataset, *, im_lang=False):
        """Đặt bộ dữ liệu đang nghiên cứu. im_lang=True ⇒ không phát tín hiệu."""
        self._active_dataset = dataset
        if not im_lang:
            self.dataset_changed.emit(dataset)

                                                                               
    @property
    def active_strategy(self):
        """Chiến lược đang nghiên cứu — result/best_params từ Tối ưu (None nếu chưa có)."""
        return self._active_strategy

    def set_active_strategy(self, strategy, *, im_lang=False):
        """Đặt chiến lược đang nghiên cứu. im_lang=True ⇒ không phát tín hiệu."""
        self._active_strategy = strategy
        if not im_lang:
            self.strategy_changed.emit(strategy)

                                                                               
    def yeu_cau_xem(self, khoa):
        """Yêu cầu vỏ app chuyển tới màn `khoa` (vd "vectorized")."""
        self.yeu_cau_xem_man.emit(khoa)
