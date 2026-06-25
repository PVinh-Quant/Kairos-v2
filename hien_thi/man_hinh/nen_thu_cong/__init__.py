"""hien_thi/man_hinh/nen_thu_cong/ — Màn 'Chỉ báo thủ công'.

Giống màn Tối ưu ở chỗ chọn nhiều chỉ báo + khung + logic, NHƯNG người dùng tự
NHẬP TAY tham số cho từng chỉ báo (không kéo-thả, không để Optuna dò ngưỡng). Bấm
'Chạy' → dựng chiến lược từ tham số tay → backtest vectorized → vẽ KẾT QUẢ là
biểu đồ nến + bảng lệnh ở dưới (tái dùng máy biểu đồ của màn Biểu đồ nến).
"""
from .dashboard import BieuDoNenThuCong

__all__ = ["BieuDoNenThuCong"]
