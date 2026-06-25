# Kiến trúc `hien_thi/` — Frontend app (PyQt6)

Lớp **hiển thị** của Kairos v2, tổ chức theo kiến trúc frontend phân lớp chuẩn:
**app shell → views → components → theme → services**, lái bởi 1 **registry**.

## Bố cục

```
hien_thi/                      ◄ package "frontend app"
├── __init__.py                FAÇADE — cổng công khai duy nhất (nạp lười PEP 562)
├── duong_dan.py               Đường dẫn chuẩn: PROJECT_ROOT, DU_LIEU
├── dang_ky_man_hinh.py        REGISTRY — nguồn-sự-thật-duy-nhất các màn hình
├── KIEN_TRUC.md               tài liệu này
│
├── app/                       VỎ ỨNG DỤNG (app shell)
│   ├── __init__.py            xuất chay(), tao_cua_so()
│   └── ung_dung.py            dựng cửa sổ + tab ĐỘNG theo registry, chạy Qt
│
├── man_hinh/                  MÀN HÌNH (views/pages) — mỗi file 1 màn hình
│   ├── realtime.py            → MainDashboard_realtime
│   ├── demo.py                → MainDashboard_demo
│   ├── backtest.py            → DraggableDashboard
│   ├── bieu_do_nen.py         → CandlestickChartWidget
│   └── toi_uu.py              → DashboardToiUu
│
├── thanh_phan/                COMPONENTS — widget UI dùng chung   (scaffold)
├── giao_dien/                 THEME — màu/font/QSS dùng chung      (scaffold)
└── dich_vu/                   SERVICES — worker/data access        (scaffold)
```

## Luồng phụ thuộc (1 chiều, sạch)

```
app ─▶ façade(__init__) ─▶ registry ─▶ man_hinh ─▶ (thanh_phan, giao_dien, dich_vu)
                                                    └─▶ duong_dan
```
Code ngoài (vd `main.py`) chỉ chạm **façade**:
```python
from hien_thi import DashboardToiUu                 # nạp lười 1 class
from hien_thi import danh_sach_man_hinh, lay_lop     # duyệt registry
from hien_thi.app import chay                        # mở app (tab động)
```

## ➕ Thêm một màn hình mới (3 bước, không sửa chỗ khác)

1. Tạo `hien_thi/man_hinh/<ten>.py`, xuất 1 widget gốc.
   - Cần đọc/ghi dữ liệu? `from hien_thi.duong_dan import PROJECT_ROOT, DU_LIEU`.
2. Thêm 1 entry vào `MAN_HINH` (`dang_ky_man_hinh.py`).
3. Xong: dùng được `from hien_thi import <Class>` **và** tự thành 1 tab trong app.

## Ghi chú đường dẫn (vì sao có `duong_dan.py`)

Các màn hình vốn tự tính gốc dự án bằng `__file__/".."`. Khi dời vào `man_hinh/`
(sâu 2 cấp), dòng đó đã chỉnh thành `"../../"` để vẫn trỏ đúng gốc — nhờ vậy
`dashboard_toi_uu` đọc/ghi đúng `du_lieu/bo_du_lieu.json`, `du_lieu/cache_ohlcv`,
`du_lieu/history_uu_hoa`. Code MỚI thì dùng `duong_dan.PROJECT_ROOT` thay vì tự
tính, để chỉ còn **một nguồn đường dẫn**.

## Roadmap (Phase sau — dọn trùng lặp, cần test kỹ vì đổi hành vi)

- Trích `Theme` (trùng ở `bieu_do_nen` & `toi_uu`) → `giao_dien/theme.py`.
- Trích `DraggableCard`, `TableBase`... (trùng ở demo/realtime/backtest) → `thanh_phan/`.
- Trích `BacktestWorker`, `DataProcessorWorker`... → `dich_vu/worker.py`.
- Hợp nhất `demo` ↔ `realtime` (đang **lệch 147 dòng**) thành base + 2 lớp mỏng.
- Gỡ bootstrap `sys.path` trong từng màn hình, thay bằng `duong_dan`.
- Cho `main.py:chay_dashboard()` uỷ quyền sang `hien_thi.app.chay()`.
