"""
hien_thi — Lớp HIỂN THỊ (UI/PyQt6) của Kairos v2.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Đây là FAÇADE (cổng công khai duy nhất) của package. Code bên ngoài chỉ nên
import từ đây, KHÔNG import sâu vào từng `dashboard_*.py`:

    from hien_thi import DashboardToiUu, MainDashboard_demo      # ✅ nên
    from hien_thi.man_hinh.toi_uu import DashboardToiUu          # ❌ tránh

Lợi ích: tách rời nơi-dùng khỏi cách bố trí file bên trong → đổi/chẻ nhỏ module
sau này không phá vỡ nơi gọi.

NẠP LƯỜI (lazy, PEP 562): chỉ `import hien_thi` thì KHÔNG kéo PyQt6 và KHÔNG
chạy side-effect của 5 module nặng. Module chỉ được nạp khi truy cập đúng class
(vd `hien_thi.DashboardToiUu`) — giữ nguyên hành vi "nạp theo yêu cầu" hiện có.

Danh mục màn hình lấy từ `dang_ky_man_hinh.MAN_HINH` (nguồn-sự-thật-duy-nhất).
"""

import importlib

from .dang_ky_man_hinh import MAN_HINH

                                                             
_LOP_TOI_MODULE = {m["lop"]: m["module"] for m in MAN_HINH}
                                                
_KHOA_TOI_LOP = {m["khoa"]: m["lop"] for m in MAN_HINH}

__all__ = list(_LOP_TOI_MODULE) + ["danh_sach_man_hinh", "lay_lop"]


def __getattr__(ten):
    """Nạp lười class màn hình khi được truy cập lần đầu (PEP 562)."""
    module = _LOP_TOI_MODULE.get(ten)
    if module is not None:
        mod = importlib.import_module(f"{__name__}.{module}")
        return getattr(mod, ten)
    raise AttributeError(f"module {__name__!r} không có thuộc tính {ten!r}")


def __dir__():
    return sorted(__all__)


def danh_sach_man_hinh():
    """Trả về danh mục màn hình (bản sao) để dựng menu/tab động.

    Mỗi phần tử là dict: {khoa, module, lop, nhan, nhom}. Dùng cùng `lay_lop`
    để nạp class tương ứng mà không cần biết tên file.
    """
    return [dict(m) for m in MAN_HINH]


def lay_lop(khoa):
    """Nạp (lười) class màn hình theo khóa máy, vd `lay_lop("toi_uu")`."""
    lop = _KHOA_TOI_LOP.get(khoa)
    if lop is None:
        hop_le = ", ".join(_KHOA_TOI_LOP)
        raise KeyError(f"Không có màn hình khóa {khoa!r}. Hợp lệ: {hop_le}")
    return __getattr__(lop)
