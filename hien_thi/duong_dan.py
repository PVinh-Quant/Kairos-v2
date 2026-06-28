"""
hien_thi/duong_dan.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nguồn ĐƯỜNG DẪN chuẩn cho lớp hiển thị. Mọi code MỚI (app shell, thành phần,
dịch vụ...) cần gốc dự án thì import từ đây — KHÔNG tự tính `__file__/".."` rải rác:

    from hien_thi.duong_dan import PROJECT_ROOT, DU_LIEU

`hien_thi/duong_dan.py` nằm ở cấp 1 của package nên `.. ` luôn trỏ đúng gốc dự án,
bất kể module gọi nằm sâu mấy cấp (man_hinh/, app/, dich_vu/...).

Ghi chú: 5 màn hình trong `man_hinh/` hiện vẫn tự bootstrap `sys.path` riêng (để
chạy độc lập qua khối `if __name__ == "__main__"`); chúng đã được chỉnh để trỏ
đúng gốc khi nằm ở cấp 2. `duong_dan.py` là điểm hợp nhất khi gỡ bỏ bootstrap đó
ở Phase sau.
"""

import os


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


DU_LIEU = os.path.join(PROJECT_ROOT, "du_lieu")


ASSETS_DIR = os.path.join(PROJECT_ROOT, "hien_thi", "assets")
