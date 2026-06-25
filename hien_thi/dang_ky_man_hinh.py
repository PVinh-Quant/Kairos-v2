"""
hien_thi/dang_ky_man_hinh.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NGUỒN-SỰ-THẬT-DUY-NHẤT cho các màn hình (dashboard) của lớp hiển thị.

Mỗi màn hình được khai báo 1 lần ở đây. Façade (`hien_thi/__init__.py`) và mọi
phần mở rộng (menu động, router, tab bar...) đều ĐỌC từ danh sách này — KHÔNG
hard-code tên file/class ở nơi khác nữa.

➕ Thêm 1 màn hình mới:
    1. Đặt file `<ten>.py` trong `hien_thi/man_hinh/`. Nếu màn hình đọc/ghi dữ liệu,
       lấy gốc dự án qua `from hien_thi.duong_dan import PROJECT_ROOT, DU_LIEU`.
    2. Thêm 1 entry vào `MAN_HINH` bên dưới.
    → Class tự động xuất hiện qua façade: `from hien_thi import <TenClass>`,
      và tự thành 1 tab trong `hien_thi.app.ung_dung`.

Mỗi entry:
    khoa   : khóa máy (chữ thường, không dấu) — định danh ổn định để code gọi.
    module : đường dẫn module trong package `hien_thi` (vd "man_hinh.toi_uu").
    lop    : tên class công khai mà module xuất ra.
    nhan   : nhãn hiển thị cho người dùng (tiếng Việt, có dấu).
    nhom   : phân loại để gom nhóm trên UI.

Thứ tự các entry = thứ tự tab hiển thị trong app.
"""

                                                    
NHOM_GIAO_DICH = "giao_dich"                              
NHOM_PHAN_TICH = "phan_tich"                                     
NHOM_BIEU_DO = "bieu_do"                                   
NHOM_HE_THONG = "he_thong"                                 

MAN_HINH = [
    {
        "khoa": "realtime",
        "module": "man_hinh.realtime",
        "lop": "MainDashboard_realtime",
        "nhan": "Realtime",
        "nhom": NHOM_GIAO_DICH,
    },
    {
        "khoa": "demo",
        "module": "man_hinh.demo",
        "lop": "MainDashboard_demo",
        "nhan": "Demo",
        "nhom": NHOM_GIAO_DICH,
    },
    {
        "khoa": "backtest",
        "module": "man_hinh.backtest",
        "lop": "DraggableDashboard",
        "nhan": "Backtest",
        "nhom": NHOM_PHAN_TICH,
    },
    {
        "khoa": "vectorized",
        "module": "man_hinh.bieu_do_nen",
        "lop": "CandlestickChartWidget",
        "nhan": "Biểu đồ nến",
        "nhom": NHOM_BIEU_DO,
    },
    {
        "khoa": "toi_uu",
        "module": "man_hinh.toi_uu",
        "lop": "DashboardToiUu",
        "nhan": "Tối ưu hoá",
        "nhom": NHOM_PHAN_TICH,
    },
    {
        "khoa": "thu_cong",
        "module": "man_hinh.nen_thu_cong",
        "lop": "BieuDoNenThuCong",
        "nhan": "Chỉ báo thủ công",
        "nhom": NHOM_BIEU_DO,
    },
    {
        "khoa": "cai_dat",
        "module": "man_hinh.cai_dat",
        "lop": "ManHinhCaiDat",
        "nhan": "Cài đặt",
        "nhom": NHOM_HE_THONG,
    },
]
