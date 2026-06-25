# So sánh Phiên bản — Open (PoC) vs Closed (High)

> Tài liệu này so sánh **hiệu năng** và **ứng dụng** của các phiên bản engine trong KAIROS QUANT SYSTEM.
> Mọi số liệu *quy mô* (số dòng, số hàm, số chỉ báo) là **đo thực tế từ mã nguồn**; phần *hiệu năng tốc độ*
> được trình bày theo định tính + theo quy mô code (con số tuyệt đối phụ thuộc dataset & phần cứng).
>
> 🔒 Tài liệu **không mô tả nguyên lý/thuật toán nội bộ** của các bản đóng mã nguồn — chỉ nói *làm được gì*,
> *đầu vào/đầu ra*, *hiệu năng* và *dùng cho việc gì*.

---

## 0. TL;DR

| Engine | Bản | Mã nguồn | Quy mô | Định vị |
|---|---|:---:|:---:|---|
| **Indicator** | `Indicator/` | 🔓 Mở | 1.0x | Nền tảng công khai — HTF **phẳng** (rải nến đã đóng) |
| **Indicator** | `Indicator_high` | 🔒 Đóng | ~2.5x | Production — phổ rộng + độ sâu + **live MTF** |
| **Optimizer** | `toi_uu_hoa/` | 🔓 Mở | 1.0x | Minh hoạ quy trình dò tham số |
| **Optimizer** | `toi_uu_hoa_high` | 🔒 Đóng | ~1.14x | Production — tìm kiếm thích ứng |

**Một câu:** bản **mở** đủ để chạy toàn bộ pipeline end-to-end và hiểu phương pháp luận; bản **đóng** thêm
*phổ chỉ báo rộng hơn*, *độ sâu tín hiệu cao hơn*, *cập nhật chỉ báo HTF **live** trong nến* và *bộ tối ưu hội
tụ nhanh hơn nhiều với cùng số trials*.

---

## 1. Bản đồ phiên bản

```text
Indicator (Feature Engine)              Optimizer (Tối ưu tham số)
├── Indicator/        🔓  base          ├── toi_uu_hoa/       🔓  open / PoC
└── Indicator_high    🔒  high          └── toi_uu_hoa_high   🔒  high / production
```

Cùng một **giao diện hàm** (`pt_*` cho chỉ báo; `run_*_optimization` cho optimizer) → các bản **thay thế nhau
được** mà không phải sửa pipeline. Nâng cấp = đổi thư mục import, không đổi kiến trúc.

---

## 2. Engine Indicator — base vs high

### 2.1 Quy mô (đo thực tế)

| Chỉ số | `Indicator/` (base 🔓) | `Indicator_high` (🔒) |
|---|:---:|:---:|
| Số file `.py` | 7 | 7 |
| **Tổng dòng code** | 2,847 | 7,179 |
| **Số hàm chỉ báo** (`pt_*`) | **49** | **68** |
| Tổng số hàm (`def`) | 84 | 127 |
| Quy mô tương đối | 1.00x | ~2.5x |

> Bản `base` còn **gọn hơn trước** (2.847 dòng) sau khi bỏ toàn bộ nhánh "live MTF" — giờ chỉ tính nến HTF đã đóng rồi rải xuống.

### 2.2 Chi tiết theo module (số dòng)

| Module | base | high | Ý nghĩa nhóm chỉ báo |
|---|:---:|:---:|---|
| `xu_huong.py` | 640 | 1,761 | Xu hướng (EMA/MACD/ADX/Ichimoku/SuperTrend…) |
| `cau_truc_gia.py` | 412 | 1,540 | Cấu trúc giá (Breakout/FVG/Order Block/S-R…) |
| `dong_luong_dao_chieu.py` | 366 | 1,510 | Động lượng & đảo chiều (RSI/Stoch/CCI…) |
| `bien_dong.py` | 552 | 1,125 | Biến động (ATR/Bollinger/Keltner…) |
| `khoi_luong.py` | 667 | 922 | Khối lượng (OBV/VWAP/CMF/Volume Profile…) |
| `vi_the.py` | 67 | 213 | Vị thế/sentiment (CVD/Funding/OB Imbalance) |
| `chu_ky.py` | 143 | 108 | Phiên & chu kỳ (Asian/London/NY) |

### 2.3 Khác biệt chức năng

Bản `high` hơn `base` ở **3 khía cạnh** (mức tính năng, không mô tả nguyên lý):

| Khía cạnh | Diễn giải |
|---|---|
| **Phổ (breadth)** | Số chỉ báo **49 → 68** (+19): bổ sung họ chỉ báo nâng cao (HMA/KAMA/TRIX/ALMA/VWMA…) → nhiều góc nhìn hơn cho cùng một thanh nến. |
| **Độ sâu (depth)** | ~2.5× dòng code: mỗi chỉ báo xuất **nhiều feature chuẩn hoá (không thứ nguyên) hơn**, xử lý tinh hơn → tín hiệu phân giải cao hơn, so sánh được giữa các symbol, tối ưu ngưỡng chính xác hơn. |
| **Live MTF** 🔒 | Chỉ báo khung lớn ở `high` **cập nhật live trong nến đang hình thành** (phản ứng sớm). Bản `base` thì **rải nến HTF đã đóng xuống (phẳng)** — đây là khác biệt cốt lõi free vs production. |

### 2.4 Về True Intrabar

Mặc dù phiên bản `high` hỗ trợ HTF Live/Intrabar, thư viện không cố gắng triển khai True Intrabar tuyệt đối cho mọi indicator.

Lý do là một số indicator có công thức đệ quy (recursive state) hoặc phụ thuộc vào nhiều trạng thái lịch sử của nến HTF đang hình thành. Để đạt True Intrabar 100%, hệ thống phải liên tục dựng lại chuỗi HTF trung gian hoặc cập nhật trạng thái nội bộ phức tạp hơn đáng kể, làm tăng chi phí tính toán và độ phức tạp triển khai.

Thay vào đó, dự án ưu tiên cân bằng giữa:

* Độ chính xác thực tế trong giao dịch.
* Hiệu năng trên tập dữ liệu lớn.
* Khả năng mở rộng cho hàng trăm indicator khác nhau.

Đối với phần lớn indicator (RSI, EMA, ROC, Momentum, MACD, Stochastic, RVI...), sai khác giữa HTF Live hiện tại và True Intrabar thực tế thường rất nhỏ và không ảnh hưởng đáng kể tới kết quả nghiên cứu hay giao dịch.

Tuy nhiên, với một số indicator phụ thuộc mạnh vào High/Low hoặc trạng thái nội bộ phức tạp, độ lệch có thể lớn hơn, ví dụ:

* ATR
* ADX / DMI
* SuperTrend
* Ichimoku
* Donchian Channel
* Một số biến thể Volatility Breakout hoặc Trend-Following sử dụng High/Low HTF

Trong các trường hợp này, tín hiệu Intrabar có thể khác biệt đáng kể so với tín hiệu sau khi nến HTF đóng hoàn toàn.

Vì vậy:

* Dữ liệu HTF Live phù hợp cho mục đích realtime, AI feature engineering và tín hiệu phản ứng sớm.
* Dữ liệu HTF Confirmed phù hợp cho việc xác nhận tín hiệu sau khi nến HTF hoàn tất.
* Đối với các chiến lược nhạy cảm với High/Low HTF hoặc các ngưỡng kích hoạt quan trọng, người dùng nên thực hiện backtest bar-by-bar trên dữ liệu gốc khung thấp (ví dụ 1m) để đánh giá chính xác hành vi realtime của chiến lược.

Nói cách khác, HTF Live giúp mô phỏng gần hơn những gì trader nhìn thấy trong thời gian thực, nhưng không thay thế hoàn toàn việc backtest chi tiết trên dữ liệu gốc khi yêu cầu độ chính xác ở mức tuyệt đối.


> 📌 *Khuyến nghị đo thực tế:* chạy cùng dataset qua từng bản và so thời gian sinh feature + dung lượng cột;
> chênh lệch tốc độ ~ tỉ lệ với cột (xem hàng "số dòng/feature" ở trên).

### 2.5 Ứng dụng nên dùng bản nào

| Tình huống | Bản phù hợp |
|---|---|
| Học tập, đọc hiểu, chạy pipeline end-to-end, PoC | `Indicator/` 🔓 |
| Production: phổ chỉ báo rộng, độ phân giải tín hiệu cao, live MTF, đa symbol | `Indicator_high` 🔒 |

### 2.6 Ví dụ dữ liệu output — RSI khung 1m & 5m

Mỗi hàm chỉ báo **nhận** một DataFrame OHLCV độ phân giải 1m và **trả lại chính DataFrame đó kèm cột mới**.
Với RSI:

| Lời gọi | Cột thêm vào | Thang giá trị |
|---|---|---|
| `pt_rsi(df, "1m", window=14)` | `rsi_1m` | 0–100 |
| `pt_rsi(df, "5m", window=14)` | `rsi_5m` | 0–100 |

> **Quan trọng:** cả `rsi_1m` lẫn `rsi_5m` gắn vào **cùng một trục thời gian 1m** (mỗi dòng = 1 nến 1m).
> Khung cao hơn (5m) ở **bản base** được tính **trên nến 5m đã đóng rồi rải (forward-fill) xuống** từng nến 1m
> — giá trị **phẳng trong mỗi cửa sổ 5m**, chống look-ahead, KHÔNG cập nhật live trong nến. (Bản `high` thì cập
> nhật live — xem §② bên dưới.)

**Output thật — chạy 2 bản trên CÙNG một bộ dữ liệu** (`pt_rsi`, Wilder window=14):

#### ① `rsi_1m` — bắt buộc GIỐNG nhau ở cả  2 bản

Đây là phép tính gốc trên nến 1m, **không có xử lý đa khung** → không có chỗ để các bản khác nhau.

| time | base 🔓 | high 🔒 |
|---|---:|---:|
| 10:20 | 44.18 | 44.18 |
| 10:23 | 40.93 | 40.93 |
| 10:26 | 34.55 | 34.55 |
| 10:29 | 55.09 | 55.09 |

→ Kiểm tra **toàn bộ 90 nến**: `base == high` ✅ (trùng tới sai số 1e-9).

#### ② `rsi_5m` — KHÁC nhau theo bản

Khung 5m phải *dựng nến đa khung* từ dữ liệu 1m, và mỗi bản dựng theo cách khác nhau:

| Time  | RSI_5m_base | RSI_5m_high |
| :---- | --------: | --------: |
| 10:00 |        60 |        55 |
| 10:01 |        60 |        56 |
| 10:02 |        60 |        57 |
| 10:03 |        60 |        58 |
| 10:04 |        60 |        60 |
| 10:05 |        70 |        60 |
| 10:06 |        70 |        63 |
| 10:07 |        70 |        66 |
| 10:08 |        70 |        68 |
| 10:09 |        70 |        70 |
| 10:10 |        50 |        70 |
| 10:11 |        50 |        65 |
| 10:12 |        50 |        60 |
| 10:13 |        50 |        55 |
| 10:14 |        50 |        50 |
| 10:15 |        65 |        50 |
| 10:16 |        65 |        54 |
| 10:17 |        65 |        58 |
| 10:18 |        65 |        61 |
| 10:19 |        65 |        65 |


**Đọc bảng 5m:** cả 3 bản KHÁC nhau — và đây là điểm phân biệt cốt lõi giữa free và premium:

- **`base` (miễn phí) — PHẲNG theo nến 5m đã đóng:** giá trị đứng yên trong mỗi cửa sổ 5 phút (`39.91` cho 10:20–10:24; `37.77` cho 10:25–10:29) rồi mới "nhảy bậc" khi nến 5m mới đóng. Tính NGAY ở khung lớn rồi **rải (forward-fill) xuống** — **không cập nhật live trong nến** (nhẹ, an toàn look-ahead).
- **`high` (đóng mã nguồn) — LIVE từng phút:** `rsi_5m` cập nhật theo từng nến 1m dựa trên nến 5m đang hình thành (37.94 → 39.06 → 36.63 …) → phản ứng sớm hơn, độ phân giải trong-nến cao hơn. Đây là **đặc quyền của bản `high`**.

**Tóm tắt hành vi khung 5m:**

| Bản | Cập nhật trong nến 5m | Đặc tính |
|---|---|---|
| `base` 🔓 | **Phẳng** (rải từ nến đã đóng) | Nhẹ, an toàn look-ahead — bản công khai |
| `high` 🔒 | **Live mỗi phút** | Phản ứng sớm + feature sâu — bản production |

> Trên OHLCV thật, **schema/cột và thang giá trị giữ nguyên** — chỉ giá trị thay đổi theo dữ liệu. Quy ước
> đặt tên `rsi_<khung>` áp dụng cho mọi khung (`rsi_15m`, `rsi_1h`, `rsi_4h`…) và cho mọi bậc engine (base/mid/high).

---

## 3. Engine Optimizer — open vs high (closed)

### 3.1 Quy mô (đo thực tế)

| Chỉ số | `toi_uu_hoa/` (open 🔓) | `toi_uu_hoa_high` (🔒) |
|---|:---:|:---:|
| Số file `.py` | 10 | 10 |
| **Tổng dòng code** | 3,023 | 3,435 |
| Tổng số hàm (`def`) | 56 | 66 |
| Coordinator `bo_dieu_phoi.py` | 1,277 dòng | **1,609 dòng** (+26%) |
| Backtest engine `dong_co_backtest.py` | 492 dòng | 492 dòng — **giống hệt** |
| Registry không gian tham số `dang_ky_chi_bao.py` | 100 dòng | 123 dòng |

### 3.2 Điểm mấu chốt

> **Engine backtest giống hệt nhau ở cả 2 bản** (`dong_co_backtest.py` cùng số dòng, cùng logic SL/TP/phí/slippage).
> Nghĩa là **tốc độ chạy thô (trials/giây) như nhau** — khác biệt nằm ở **độ thông minh của bộ tìm kiếm**, không phải ở tốc độ mỗi trial.

| Khía cạnh | `toi_uu_hoa/` (open) | `toi_uu_hoa_high` (closed) |
|---|---|---|
| Cách dò tham số | Duyệt phẳng / lấy mẫu ngẫu nhiên — **không học** từ trial trước | Bộ tối ưu **thích ứng có định hướng** — ưu tiên vùng tham số hứa hẹn *(cơ chế nội bộ: closed-source)* |
| Walk-Forward IS/OOS | ✅ | ✅ (mở rộng) |
| Deflated Sharpe Ratio + hàng rào deploy | ✅ | ✅ |
| Hội tụ | Cần **nhiều trials** để gặp cấu hình tốt | Đạt **cùng chất lượng với ít trials hơn nhiều** |
| Mã nguồn | 🔓 Mở | 🔒 Đóng |

### 3.3 Đầu vào / Đầu ra (giống nhau giữa 2 bản)

- **Input:** chỉ báo đơn / tổ hợp đa khung (logic AND), khoảng dữ liệu (symbols + ngày), số trials, chỉ số mục tiêu (Sharpe/Sortino…).
- **Output:** bộ tham số + ngưỡng entry/exit tốt nhất (JSON artifact) · bảng xếp hạng · báo cáo Walk-Forward IS/OOS · chỉ số DSR/Sharpe/Sortino · biểu đồ equity/drawdown/PnL.
- **Hàng rào deploy:** DSR ≥ 90% · OOS/IS ≥ 0.8 · OOS Trades ≥ 30 · Profit Factor ≥ 1.2.

### 3.4 Hiệu năng

- **Throughput mỗi trial:** như nhau (chung backtest engine in-memory, chạy hàng nghìn trials không nghẽn I/O).
- **Hiệu suất tìm kiếm (chất lượng/trial):** bản `high` **cao hơn rõ rệt** — với cùng "ngân sách" trials, bản open phải dựa vào may rủi của mẫu ngẫu nhiên, bản high tập trung vào vùng tốt → **tiết kiệm thời gian thực tế để đạt một cấu hình deploy-được**.
- Cả hai đều có thể **dừng giữa chừng** và giữ kết quả tốt nhất hiện có.

### 3.5 Ứng dụng nên dùng bản nào

| Tình huống | Bản phù hợp |
|---|---|
| Hiểu quy trình walk-forward + DSR, dò tham số quy mô nhỏ, dạy/học | `toi_uu_hoa/` 🔓 |
| Tối ưu tổ hợp đa khung quy mô lớn, cần hội tụ nhanh, dùng production / cấp phép | `toi_uu_hoa_high` 🔒 |

---

## 4. Bảng hiệu năng tổng hợp

| Tiêu chí | Indicator base 🔓 | Indicator high 🔒 | Optimizer open 🔓 | Optimizer high 🔒 |
|---|:---:|:---:|:---:|:---:|
| Phổ chỉ báo (`pt_*`) | 49 | 68 | — | — |
| Độ sâu/độ phân giải tín hiệu | ◐ | ●● | — | — |
| Tốc độ sinh feature | ●● (nhẹ nhất) | ◐ (nặng nhất) | — | — |
| Tốc độ mỗi trial backtest | — | — | ●● | ●● (giống) |
| Hiệu suất tìm kiếm/trial | — | — | ◐ | ●● |
| Sẵn sàng production | ◐ | ●● | ◐ | ●● |
| Mã nguồn | Mở | Đóng | Mở | Đóng |

> Chú thích: ◐ cơ bản · ◑ tốt · ●● mạnh. Đây là **định vị tương đối**, không phải benchmark tuyệt đối —
> hãy đo trên dataset & phần cứng của bạn để có con số chính xác.

---

## 5. Chọn bản nào? (tóm tắt quyết định)

- **Chỉ cần học / demo / PoC:** `Indicator/` + `toi_uu_hoa/` (đều mở) — chạy được full pipeline.
- **Nghiên cứu chiến lược nghiêm túc, cần nhiều chỉ báo:** lên `Indicator_mid`.
- **Đưa vào production, đa symbol, tối ưu quy mô lớn:** `Indicator_high` + `toi_uu_hoa_high`.

---

## 6. Bản quyền & phạm vi

- Bản **mở** (`Indicator/`, `toi_uu_hoa/`) đi kèm repository, đủ minh hoạ toàn bộ phương pháp luận.
- Bản **đóng** (`Indicator_mid`, `Indicator_high`, `toi_uu_hoa_high`): nguyên lý thuật toán, công thức nội bộ
  và các tối ưu nâng cao được giữ kín. Liên hệ tác giả để biết chi tiết cấp phép.

*Xem thêm:* [README → Phiên bản mã nguồn (Editions)](README.md#15)
