# Kế hoạch: Chạy đồng thời nhiều chiến lược (mỗi chiến lược một vị thế độc lập)

> Trạng thái: **BẢN KẾ HOẠCH — chưa triển khai.** Soạn ngày 2026-06-23.
> Mục tiêu: ở tab "Đã lưu", chọn N chiến lược rồi chạy đồng thời trên Backtest / Biểu đồ nến / Demo / Live,
> mỗi chiến lược vào–ra lệnh **độc lập** (không gộp union, không phải "A thoát mới được vào B").

---

## 0. TL;DR

- Hiện tại **mọi engine đều đơn-chiến-lược**: nhiều chiến lược bị **gộp union thành 1 tín hiệu / 1 vị thế**, risk lấy của chiến lược đầu tiên.
- Có **3 nút thắt phần mềm** + **1 ràng buộc vật lý của sàn** (sàn net 1 vị thế ròng/symbol).
- Giải pháp: tách **"vị thế ảo theo chiến lược"** khỏi **"lệnh thật theo tài khoản"**, đổi khóa vị thế từ `symbol` → `(chiến_lược, symbol)`.
- Triển khai **theo pha**. Khuyến nghị làm **Pha 0 + Pha 1 (mô phỏng)** trước: giá trị cao, không chạm ràng buộc sàn, rủi ro thấp.

---

## 1. Hiện trạng — vì sao chưa chạy song song được

### 1.1 Ba nút thắt phần mềm

| # | Nút thắt | Vị trí | Bản chất |
|---|---|---|---|
| 1 | Bus đơn-chiến-lược | `hien_thi/dich_vu/phien_nghien_cuu.py:60` — `set_active_strategy` (số ít), `_active_strategy` | UI chỉ phát được **1** chiến lược lên bus phiên |
| 2 | Lõi tín hiệu **union** | bar-to-bar: `chien_luoc/quan_ly_chien_luoc_bar_to_bar.py:187-193` (gặp tín hiệu ≠ 0 đầu tiên là `break`)<br>vectorized: `chien_luoc/quan_ly_chien_luoc_vectorized.py:216-225` (union từng nến) + risk lấy `strats.values()[0]` ở `:229` | N chiến lược → **1 cột `signal`**, SL/TP/đòn bẩy/regime lấy của chiến lược **#0** |
| 3 | State lệnh **khóa theo symbol** | `thuc_thi_lenh/quan_ly_lenh.py:61` — `danh_sach_lenh_dang_chay = {symbol: order_info}`; chốt chặn entry `chuc_nang/chay_realtime.py:90` — `if kiem_tra_ton_tai(symbol): continue` | Mỗi symbol **chỉ 1 vị thế**; chiến lược B không mở được trên symbol đã có vị thế của A |

Ghi chú: `order_info` **có** lưu trường `"chien_luoc"` (tên chiến lược) tại `chay_realtime.py:173` — tức đã có *attribution*, nhưng **khóa lưu trữ vẫn là `symbol`**, nên không phân biệt được 2 vị thế cùng symbol.

### 1.2 Ràng buộc vật lý của sàn (KHÔNG sửa bằng code được)

Binance Futures **net 1 vị thế ròng / symbol** ở chế độ one-way (hoặc tối đa 1 long + 1 short / symbol ở hedge mode).

→ Trong **cùng 1 tài khoản**, không thể cho chiến lược A và B cùng giữ **2 lệnh long độc lập** trên cùng `BTCUSDT` — sàn sẽ gộp thành 1 vị thế ròng.

Đây là lý do kế hoạch phải **tách 2 thế giới**:
- **Mô phỏng** (Backtest / Biểu đồ nến): tự do, vị thế ảo độc lập bao nhiêu cũng được.
- **Lệnh thật** (Demo / Live): bị ràng buộc net → cần phân hoạch symbol hoặc lớp allocator.

### 1.3 Bản đồ 4 engine (xác nhận qua đọc code)

| Engine | Lõi tín hiệu | Mô hình vị thế |
|---|---|---|
| Biểu đồ nến (vectorized) | `tong_hop_tin_hieu` | 1 cột `signal` hợp nhất |
| Backtest (đơn/đa luồng) | `chien_luoc_vao_lenh` → `danh_gia_tin_hieu_bar` | 1 vị thế / symbol; mô phỏng máy trạng thái `vi_the` ở `vectorized_backtest.py:101` |
| Demo | `luong_quet_thi_truong_demo` → `chien_luoc_vao_lenh` | 1 vị thế / symbol |
| Live/Realtime | `luong_quet_thi_truong` → `chien_luoc_vao_lenh`; quản vị thế theo symbol ở `chay_realtime.py:199` | 1 vị thế / symbol |

"Đa luồng" trong backtest = song song theo **symbol**, KHÔNG phải theo chiến lược.

---

## 2. Nguyên tắc thiết kế cốt lõi

> **Tách "vị thế ảo theo chiến lược" khỏi "lệnh thật theo tài khoản".**

1. **Đổi khóa vị thế:** `symbol` → `pos_id` hoặc khóa kép `(chien_luoc, symbol)`. Mỗi chiến lược có sổ vị thế + PnL riêng.
2. **Risk theo từng chiến lược:** bỏ việc lấy `strats.values()[0]`; mỗi chiến lược dùng đúng SL/TP/đòn bẩy/regime của nó.
3. **Lớp Allocator (chỉ live, khi cần cùng symbol):** gom *target exposure* của mọi chiến lược trên cùng symbol → **nét thành 1 lệnh thật**; logic chiến lược vẫn độc lập, chỉ khâu khớp sàn là gộp.

---

## 3. Lộ trình theo PHA

### Pha 0 — Nền tảng (bắt buộc, nhỏ)
- Bus: thêm `active_strategies: list` song song `active_strategy` (giữ tương thích ngược).
- Launch: `dat_chien_luoc_ghi_de(configs: list)` → `STRATEGIES` giữ nhiều; `_ap_dung_chien_luoc_ghi_de` nhận list (`hien_thi/dich_vu/chay_chien_luoc.py:83`).
- UI thư viện: multi-select thẻ + nút "Chạy N chiến lược".

### Pha 1 — Mô phỏng đa-chiến-lược: Backtest + Biểu đồ nến ⭐ (ROI cao nhất, không vướng sàn)
Đây là nơi **"song song thật" khả thi 100%** vì là mô phỏng.
- `tong_hop_tin_hieu` (`quan_ly_chien_luoc_vectorized.py:168`): bỏ union → trả **N cột signal riêng**; giữ risk/SL/TP/đòn bẩy **theo từng chiến lược** (không lấy strat[0]).
- `vectorized_backtest.py:100-298`: nâng máy trạng thái 1 vị thế → **vòng lặp N vị thế ảo độc lập** (mỗi chiến lược 1 bộ `vi_the/gia_vao/sl/tp`); điền trường `"Strategy"` (đang để rỗng tại `:282`).
- Gộp **equity portfolio**: vốn chung hoặc chia sleeve vốn/chiến lược; báo cáo PnL theo từng chiến lược + tổng.

→ Kết quả: A và B **vào/ra lệnh hoàn toàn độc lập, song song**, mỗi cái SL/TP/PnL riêng.

### Pha 2 — Live/Demo qua **phân hoạch symbol** (MVP an toàn, vị thế thật độc lập)
- Mỗi chiến lược sở hữu **rổ symbol rời nhau** (A: BTC/ETH, B: SOL/BNB) → khác symbol → **không đụng ràng buộc net** → vị thế thật độc lập tự nhiên.
- Re-key state sang `(chien_luoc, symbol)` ở `quan_ly_lenh.py:172-192` (luu/xoa/kiem_tra/cooldown), file JSON trạng thái, và `PositionsTable` UI.
- `MAX_OPEN_ORDERS` + phân bổ vốn tính ở cấp **portfolio** (tổng) và theo từng chiến lược.

### Pha 3 — Live cùng symbol (nâng cao, tùy chọn — chỉ làm nếu thực sự cần)
- **3a. Allocator / net-executor:** mỗi chiến lược giữ vị thế **ảo**; allocator nét tổng exposure → 1 lệnh thật/symbol; PnL phân bổ ngược về từng chiến lược. (Chuẩn tổ chức, nhiều việc nhất.)
- **3b. Hedge mode:** tối đa 1 long + 1 short/symbol (2 chiến lược ngược chiều).
- **3c. Sub-account / chiến lược:** cô lập thật, nhưng nặng vận hành (API key riêng, vốn phân mảnh).

---

## 4. Thay đổi cụ thể theo layer

| Layer | File | Pha | Thay đổi |
|---|---|---|---|
| Bus | `hien_thi/dich_vu/phien_nghien_cuu.py` | 0 | thêm `active_strategies` (list) |
| Launch | `hien_thi/dich_vu/chay_chien_luoc.py`, `chien_luoc/quan_ly_chien_luoc_bar_to_bar.py:73` | 0 | ghi đè nhận list config |
| UI thư viện | `hien_thi/man_hinh/toi_uu/dashboard.py` (StrategyCard) | 0 | multi-select + nút chạy N |
| Lõi vectorized | `chien_luoc/quan_ly_chien_luoc_vectorized.py:168` | 1 | N cột signal, risk per-strat |
| Sim backtest | `chuc_nang/vectorized_backtest.py:100` | 1 | N vị thế ảo, attribution `"Strategy"` |
| Lõi bar-to-bar | `chien_luoc/quan_ly_chien_luoc_bar_to_bar.py:167` | 2 | bỏ `break`, trả list (tín hiệu, risk) theo từng chiến lược |
| Entry/Exit live | `chuc_nang/chay_realtime.py:75/199`, `chuc_nang/chay_demo.py` | 2 | loop theo `(chien_luoc, symbol)` |
| State lệnh | `thuc_thi_lenh/quan_ly_lenh.py` | 2 | re-key `pos_id`; đổi schema file JSON; cooldown theo khóa mới |
| Allocator (mới) | `thuc_thi_lenh/phan_bo_lenh.py` | 3 | nét exposure đa-chiến-lược → lệnh thật |

---

## 5. Rủi ro chính & điểm cần lưu ý

- **Re-key state (Pha 2)** đụng cả: file JSON trạng thái đang lưu (`trang_thai_lenh_realtime.json` / `_demo.json`), UI bảng vị thế (`PositionsTable`), và theo dõi lệnh sàn (`kiem_tra_trang_thai_vi_the(SAN, symbol)` query theo symbol). → cần **migration schema + test kỹ**.
- **Phân bổ vốn:** N chiến lược chia sẻ vốn → cần quy tắc sizing và `MAX_OPEN_ORDERS` ở cấp portfolio, tránh vào lệnh vượt vốn.
- **Đồng bộ 3 engine:** optimizer / vectorized / bar-to-bar dùng chung lõi tín hiệu (`ket_hop_tin_hieu_spec`). Mọi thay đổi phải giữ test `kiem_thu/test_dong_bo_tin_hieu.py` xanh.
- **Live cùng symbol:** nếu 2 chiến lược ra lệnh ngược chiều trên cùng symbol mà không có allocator → xung đột / net về 0. Pha 2 (phân hoạch symbol) né được; Pha 3 mới xử lý triệt để.

---

## 6. Trả lời trực tiếp câu hỏi "vào/ra lệnh như nào"

| Phạm vi | Cơ chế vào/ra |
|---|---|
| Hiện tại | Union: N chiến lược → 1 tín hiệu → 1 vị thế/symbol; risk của #0. Không song song, không tuần tự A→B. |
| Sau Pha 1 (mô phỏng) | **Song song độc lập hoàn toàn**: A và B mỗi cái có entry/exit/SL/TP/PnL riêng; có thể cùng mở vị thế một lúc. |
| Sau Pha 2 (live khác symbol) | Song song độc lập **trên các symbol khác nhau** (vị thế thật). |
| Sau Pha 3 (live cùng symbol) | Độc lập về *logic & PnL ảo*; allocator nét thành 1 lệnh thật/symbol khi khớp sàn. |

---

## 7. Khuyến nghị

Làm **Pha 0 + Pha 1** trước — đáp ứng đúng nhu cầu phân tích "chạy nhiều chiến lược cùng lúc" mà không chạm ràng buộc sàn, rủi ro thấp, giá trị cao. Tách Live (Pha 2/3) sang giai đoạn sau khi đã hài lòng với kết quả mô phỏng.
