"""
hien_thi.app — VỎ ỨNG DỤNG (app shell) của lớp hiển thị.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lắp ráp các màn hình (man_hinh/) thành 1 cửa sổ có tab và khởi chạy. Tab được
sinh ĐỘNG từ `hien_thi.dang_ky_man_hinh.MAN_HINH` — thêm 1 entry registry là có
ngay 1 tab mới, không sửa file này.

    from hien_thi.app import chay        # mở app
    from hien_thi.app import tao_cua_so  # chỉ dựng cửa sổ (để nhúng/test)
"""

from .ung_dung import chay, tao_cua_so

__all__ = ["chay", "tao_cua_so"]
