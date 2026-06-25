"""
hien_thi.man_hinh — Các MÀN HÌNH (views/pages) của app.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mỗi file = 1 màn hình cấp cao, xuất ra 1 widget gốc:

    bieu_do_nen.py  → CandlestickChartWidget   (Biểu đồ nến)
    realtime.py     → MainDashboard_realtime   (Realtime)
    demo.py         → MainDashboard_demo        (Demo)
    backtest.py     → DraggableDashboard        (Backtest)
    toi_uu.py       → DashboardToiUu            (Tối ưu hoá)

KHÔNG import trực tiếp từ đây ở code ngoài — dùng façade `from hien_thi import ...`
hoặc `lay_lop(khoa)`. Danh mục + thứ tự lấy từ `hien_thi.dang_ky_man_hinh`.

Lưu ý độ sâu: các file ở đây nằm ở CẤP 2 và tự tính gốc dự án bằng
`__file__/"../../"`. Nếu thêm màn hình mới có đọc/ghi dữ liệu, dùng
`from hien_thi.duong_dan import PROJECT_ROOT, DU_LIEU`.
"""
