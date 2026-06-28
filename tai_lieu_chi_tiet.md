# Hướng dẫn Kỹ Thuật Chi Tiết — Kairos-v2

Đây là complete technical reference cho bản base (open source).

**Phạm vi:** Architecture, modules, components, design patterns.

**Đối tượng:** Developers, quants, researchers muốn hiểu và mở rộng hệ thống.

**Cập nhật:** 2026-06-26 — tất cả code examples và diagrams đều đúng với source hiện tại.

**Lưu ý:** Bản high (closed source) được tham chiếu trong [so_sanh_phien_ban.md](so_sanh_phien_ban.md) để so sánh quy mô; không mô tả thuật toán nội bộ.

---

## Bắt đầu nhanh

Nếu bạn chỉ cần:

- Hiểu cấu trúc module → Xem [1. Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
- Chạy một backtest → Xem [3. Tầng dữ liệu](#3-tầng-dữ-liệu)
- Thêm indicator riêng → Xem [4. Engine chỉ báo](#4-engine-chỉ-báo-kỹ-thuật) + [11. Cách mở rộng](#11-cách-mở-rộng-dự-án)
- Kiểm định chiến lược → Xem [8. Tối ưu hóa tham số](#8-tối-ưu-hóa-tham-số)

---

## Mục lục

- [1. Tổng quan hệ thống](#tong-quan)
- [2. Cấu hình và quy ước chạy](#cau-hinh)
- [3. Tầng dữ liệu](#du-lieu)
- [4. Engine chỉ báo kỹ thuật](#indicator)
- [5. Chiến lược, thực thi lệnh và backtest](#chien-luoc)
- [6. ML phân loại trạng thái thị trường](#ml)
- [7. Giao diện, dashboard và runner](#ui)
- [8. Tối ưu hóa tham số](#toi-uu)
- [9. Lưu trữ, log và phân tích SQL](#luu-tru)
- [10. Bản base vs bản high](#edition)
- [11. Cách mở rộng dự án](#mo-rong)

---

<a name="tong-quan"></a>

## 1. Tổng quan hệ thống

Kairos-v2 là một hệ thống giao dịch định lượng theo mô-đun:

- **`lay_du_lieu/`**: lấy dữ liệu thị trường, snapshot và macro.
- **`Indicator/`**: bộ chỉ báo kỹ thuật đa khung.
- **`chien_luoc/`**: quản lý chiến lược, optimizer và routing tín hiệu.
- **`thuc_thi_lenh/`**: mở/đóng lệnh, quản lý vị thế và kết nối sàn.
- **`chuc_nang/`**: runner realtime, demo, backtest.
- **`ml/`**: phân loại regime và huấn luyện model.
- **`hien_thi/`**: giao diện PyQt6 và dashboard.
- **`toi_uu_hoa/`**: tối ưu hóa tham số, backtest engine và kiểm định.
- **`utils/`**: cấu hình, logging, kho dữ liệu DuckDB, tiện ích chung.

Điểm mạnh của kiến trúc hiện tại là:

- tách rõ **data → feature → signal → execution → analytics**;
- dùng **Polars** cho xử lý dữ liệu nặng;
- có cả **realtime**, **demo**, **backtest bar-to-bar** và **vectorized backtest**;
- ML được dùng như một lớp **regime gating** để định tuyến chiến lược.

---

<a name="cau-hinh"></a>

## 2. Cấu hình và quy ước chạy

### 2.1 Các file cấu hình chính

| File | Vai trò |
|---|---|
| `config/cau_hinh_giao_dich.yaml` | Danh sách symbol, đòn bẩy, vốn mỗi lệnh, cooldown, tham số giao dịch |
| `config/thong_tin_san.yaml` | Thông số theo sàn: fee, min notional, max leverage |
| `config/cau_hinh_ao_config.json` | Cấu hình paper trading / backtest |
| `config/tai_khoan_api.json` | API key thật, không commit lên git |
| `config/tai_khoan_api.json.example` | Mẫu cấu hình API |

### 2.2 Loader cấu hình

Mọi module nên đọc cấu hình qua `utils/doc_cau_hinh.py` thay vì hardcode:

```python
from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao, lay_thong_tin_san

trade_cfg = lay_cau_hinh_giao_dich()
backtest_cfg = lay_cau_hinh_ao()
san_info = lay_thong_tin_san()
```

### 2.3 Quy ước môi trường

`utils/doc_cau_hinh.py` hỗ trợ một số biến môi trường để chạy theo ngữ cảnh:

- `KAIROS_RUN_SYMBOLS`: giới hạn danh sách symbol khi chạy một chiến lược;
- `KAIROS_RUN_TU_NGAY`: giới hạn ngày bắt đầu backtest;
- `KAIROS_RUN_DEN_NGAY`: giới hạn ngày kết thúc backtest.

### 2.4 Entrypoint chính

- `python main.py`: launcher terminal.
- `python ml/main.py`: launcher cho luồng ML.
- `chuc_nang/chay_realtime.py`: chạy realtime.
- `chuc_nang/chay_demo.py`: chạy demo/paper trading.

---

<a name="du-lieu"></a>

## 3. Tầng dữ liệu

### 3.1 OHLCV đa khung

File chính: `lay_du_lieu/lay_ohlcv.py`

Chức năng:

- lấy OHLCV từ sàn qua CCXT;
- gộp nến bằng Polars;
- nạp dữ liệu lịch sử 1m cho backtest;
- chuẩn bị bộ dữ liệu đa khung cho vectorized backtest.

#### Các hàm quan trọng

- `fetch_raw(exchange, symbol, timeframe, limit=1000)`
- `gop_nen(df, timeframe_dich)`
- `lay_du_lieu_nen(ten_san, symbol)`
- `tai_du_lieu_lich_su(symbol, start_str, end_str)`
- `chuan_bi_du_lieu_da_khung(df_goc, current_time, limit_lookback=43200)`

#### Ý nghĩa thực tế

- **Realtime / demo**: lấy bộ khung 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d.
- **Backtest bar-to-bar**: cắt dữ liệu đến thời điểm hiện tại rồi gộp nến theo từng bước.
- **Vectorized backtest**: dựng toàn bộ khung từ 1m gốc để mô phỏng tốc độ cao.

### 3.2 Market snapshot realtime

File chính: `lay_du_lieu/lay_marketsnapshot.py`

`KairosDataManager` quản lý các luồng WebSocket cho từng symbol:

- `aggTrade`: trade flow, CVD;
- `markPrice`: giá mark và funding rate;
- `depth5`: top 5 order book, imbalance;
- `forceOrder`: liquidation;
- `bookTicker`: best bid/ask.

Các hàm tiện ích:

- `mo_theo_doi(cap_giao_dich)`
- `dong_theo_doi(cap_giao_dich)`

### 3.3 Thông tin tài khoản

File chính: `lay_du_lieu/lay_thong_tin_tai_khoan.py`

- `lay_so_du_kha_dung(ten_san, asset="USDT")`
- `lay_vi_the_hien_tai(ten_san, symbol)`

### 3.4 Macro / sentiment

File chính: `lay_du_lieu/lay_macro.py`

- `lay_du_lieu_cam_xuc()`: Fear & Greed Index;
- `lay_du_lieu_io(symbol="BTC/USDT", period="5m", limit=30)`: Open Interest.

---

<a name="indicator"></a>

## 4. Engine chỉ báo kỹ thuật

### 4.1 Cấu trúc module (Bản Base / PoC)

Thư mục `Indicator/` gồm 7 module (tổng **2,847 dòng code**, **49 hàm `pt_*`**):

| Module | Dòng code | Mô tả |
|---|---:|---|
| `xu_huong.py` | 640 | Xu hướng (EMA/SMA/ADX/DMI/Ichimoku/SuperTrend/Aroon/Vortex) |
| `cau_truc_gia.py` | 412 | Cấu trúc giá (Breakout/Fractals/Pivot/FVG/Heikin Ashi) |
| `dong_luong_dao_chieu.py` | 366 | Động lượng & đảo chiều (RSI/Stoch/MFI/Ultimate Osc) |
| `bien_dong.py` | 552 | Biến động (ATR/BB Squeeze/Keltner/Donchian/HistVol/Chaikin Vol) |
| `khoi_luong.py` | 667 | Khối lượng (Volume/OBV/VWAP/Volume Profile/CMF/A-D/MFI Vol/EoM) |
| `vi_the.py` | 67 | Vị thế/sentiment (CVD/Funding/OB Imbalance) |
| `chu_ky.py` | 143 | Phiên & chu kỳ (Asian/London/NY session) |
| **Tổng** | **2,847** | **49 chỉ báo** |

> **Ghi chú:** Bản Base này đi kèm repository công khai, hỗ trợ tính năng HTF confirmed/flat để người dùng nghiên cứu và chạy thử nghiệm đầy đủ toàn bộ pipeline hệ thống.

### 4.2 Nhóm chỉ báo (chi tiết)

#### Xu hướng (2,052 dòng, ~15 hàm)

File: `Indicator/xu_huong.py`

- **EMA / SMA** (exponential & simple moving average)
- **ADX / DMI** (average directional index)
- **Ichimoku** (Kumo, Tenkan, Kijun, Chikou)
- **SuperTrend** (trend follower)
- **MACD** (momentum oscillator)
- **PSAR** (parabolic SAR)
- **Aroon** (trend direction)
- **Vortex** (directional strength)
- **HMA / KAMA / ALMA / VWMA** (advanced moving averages)

#### Động lượng & đảo chiều (1,787 dòng, ~12 hàm)

File: `Indicator/dong_luong_dao_chieu.py`

- **RSI** (relative strength index)
- **Stochastic** (K/D lines)
- **MFI** (money flow index)
- **Ultimate Oscillator**
- **Stoch RSI** (stochastic applied to RSI)
- **STC** (Schaff trend cycle)
- **CCI** (commodity channel index)

#### Biến động (1,295 dòng, ~13 hàm)

File: `Indicator/bien_dong.py`

- **ATR** (average true range)
- **Bollinger Squeeze** (squeeze detection)
- **Keltner Channel** (volatility channel)
- **Donchian Channel** (high/low breakout)
- **Historical Volatility**
- **Chaikin Volatility**
- **ATR Bands** (bands based on ATR)
- **Chandelier Exit** (volatility stop)
- **Choppiness Index**

#### Khối lượng (1,130 dòng, ~11 hàm)

File: `Indicator/khoi_luong.py`

- **Volume** (raw & moving average)
- **OBV** (on-balance volume)
- **VWAP** (volume-weighted average price)
- **Volume Profile** (distribution analysis)
- **CMF** (Chaikin money flow)
- **A/D Line** (accumulation/distribution)
- **MFI Volume** (volume-based momentum)
- **Ease of Movement**
- **PVT** (price-volume trend)
- **Chaikin Oscillator**

#### Cấu trúc giá (1,766 dòng, ~8 hàm)

File: `Indicator/cau_truc_gia.py`

- **Breakout** (support/resistance breakout)
- **Fractals** (local high/low detection)
- **Pivot Points** (classical & modern pivots)
- **Fair Value Gaps (FVG)** (market microstructure)
- **Heikin Ashi** (smoothed OHLC)
- **Order Block** (supply/demand zones)

#### Vị thế / sentiment (251 dòng, ~3 hàm)

File: `Indicator/vi_the.py`

- **Elder Ray** (bull & bear power)
- **CVD** (cumulative volume delta)

#### Chu kỳ & phiên (131 dòng, ~2 hàm)

File: `Indicator/chu_ky.py`

- Kiểm tra ngày / giờ
- Session giao dịch (Asian/London/New York)
- Session range & open

### 4.3 Cách xử lý đa khung ở bản base

Điểm quan trọng nhất của bản base là:

- chỉ báo khung cao được tính trên **nến đã đóng** của khung đó;
- sau đó giá trị được **forward-fill** xuống trục thời gian thấp hơn;
- nhờ vậy tránh look-ahead bias;
- đổi lại, giá trị HTF trong bản base **không cập nhật live intrabar**.

Nói ngắn gọn:

- **base** = an toàn, confirmed, dễ kiểm định;
- **high** = có thể live/chi tiết hơn, nhưng không có source public trong repo.

### 4.4 Quy ước đặt tên cột

Hầu hết chỉ báo sinh cột theo dạng:

- `rsi_1m`, `rsi_5m`
- `adx_15m`
- `bb_width_1h`
- `fvg_top_4h`

Điều này giúp pipeline downstream nhận biết được:

- chỉ báo nào;
- trên khung nào;
- trạng thái có phải từ HTF hay không.

### 4.5 Các hàm trợ giúp cốt lõi

Nhiều module dùng chung kỹ thuật:

- tính trên 1m làm gốc;
- gộp nến HTF;
- `join_asof(..., strategy="backward")`;
- hạn chế đụng vào dữ liệu tương lai.

---

<a name="chien-luoc"></a>

## 5. Chiến lược, thực thi lệnh và backtest

### 5.1 Signal engine

Các chiến lược được tổ chức trong `chien_luoc/`:

- `base_strategy.py`
- `json_strategy.py`
- `quan_ly_chien_luoc_bar_to_bar.py`
- `quan_ly_chien_luoc_vectorized.py`
- `optimizer/`
- `user_strategies/`

Ý tưởng chung:

- gom feature từ nhiều indicator;
- cho điểm tín hiệu;
- kết hợp filter theo regime và HTF;
- sinh quyết định vào lệnh / đứng ngoài / thoát lệnh.

### 5.2 Thực thi lệnh

Thư mục `thuc_thi_lenh/` chịu trách nhiệm:

- chọn sàn;
- mở lệnh;
- đóng lệnh;
- quản lý danh mục;
- theo dõi cooldown và trạng thái vị thế.

Các file đáng chú ý:

- `bo_may_thuc_thi.py`
- `chon_san_giao_dich.py`
- `mo_lenh.py`
- `dong_lenh.py`
- `quan_ly_lenh.py`
- `quan_ly_danh_muc.py`
- `theo_doi_lenh.py`
- `ket_noi_san/*.py`

### 5.3 Chạy realtime và demo

`chuc_nang/chay_realtime.py`:

- quét thị trường;
- lấy snapshot;
- gọi chiến lược;
- quản lý vị thế;
- ghi log và lưu kết quả.

`chuc_nang/chay_demo.py`:

- chạy pipeline giống realtime;
- nhưng ở chế độ paper trading / mô phỏng.

### 5.4 Backtest

Có 3 hướng backtest chính:

#### Bar-to-bar

- `chuc_nang/backtest_daluong.py`
- `chuc_nang/backtest_donluong.py`

Ưu điểm:

- mô phỏng gần với realtime;
- dễ gắn điều kiện thực thi lệnh;
- thích hợp kiểm thử logic.

#### Vectorized backtest

- `chuc_nang/vectorized_backtest.py`
- `chuc_nang/tai_dung_lenh_vector.py`

Ưu điểm:

- chạy nhanh trên toàn bộ dataset;
- phù hợp khi cần quét nhiều cấu hình;
- tích hợp tốt với tối ưu hóa tham số.

#### Luồng dữ liệu đi qua backtest

1. tải OHLCV 1m;
2. dựng khung thời gian;
3. sinh indicator;
4. tạo tín hiệu;
5. tính SL/TP, phí, slippage, đòn bẩy;
6. ghi kết quả vào kho dữ liệu.

---

<a name="ml"></a>

## 6. ML phân loại trạng thái thị trường (mục này đang có bug và chỉ là tham khảo hạn chế dùng đến)

### 6.1 Mục tiêu

ML trong Kairos-v2 không thay thế chiến lược; nó đóng vai trò:

- phân loại **regime**;
- chọn chiến lược phù hợp theo bối cảnh thị trường;
- lọc các trạng thái không nên trade.

### 6.2 Cấu trúc ML hiện tại

Thư mục `ml/trang_thai_thi_truong_ml/` gồm:

- `tao_feature.py`
- `ml_model.py`
- `ml_predict.py`
- `ml_compare.py`
- `ml_deploy.py`

Các model chính:

- `AI_Engine`
- `TradingMLP`
- `ResBlock`
- `MyTorchScaler`

### 6.3 Input / output của model

Theo file model info hiện tại:

- **Input dim**: `80`
- **Output dim**: `8`

Feature đầu vào gồm:

- 8 context state `ctx_last_state_0..7`;
- bộ feature trên 5m / 15m / 1h / 4h.

### 6.4 8 regime của thị trường

File `ml/trang_thai_thi_truong_ml/ml_predict.py` đang định nghĩa:

| State | Tên |
|---|---|
| `0` | `Đóng_Băng` |
| `1` | `Nén_Chặt` |
| `2` | `Đầu_Xu_Hướng` |
| `3` | `Xu_Hướng_Mạnh` |
| `4` | `Cao_Trào` |
| `5` | `Hồi_Quy` |
| `6` | `Nhiễu_Động` |
| `7` | `Quét_Thanh_Khoản` |

Ánh xạ chiến lược:

- `0` → không trade
- `1` → `Squeeze`
- `2` → `Breakout`
- `3` → `Trend_following`
- `4` / `5` → `Mean_reversion`
- `6` → `Scalping`
- `7` → không trade

### 6.5 Luồng dự đoán

`du_doan_trang_thai_ml(...)`:

- nhận 4 khung `5m / 15m / 1h / 4h`;
- dựng feature dataset;
- gọi `AI_Engine.predict()`;
- trả về packet gồm `state_id`, `state_name`, `confidence`, `strategy`.

`du_doan_trang_thai_ml_vector(...)`:

- chạy batch trên `1m` để phục vụ backtest / inference hàng loạt.

### 6.6 Huấn luyện

`ml/main.py` là launcher cho:

- tạo model lần đầu;
- training;
- tự học từ log;
- lọc dữ liệu.

`ml/trang_thai_thi_truong_ml/ml_model.py` hỗ trợ:

- huấn luyện từ DataFrame đã gán nhãn;
- lưu `model_pytorch.pth`;
- lưu scaler / metadata / training info.

---

<a name="ui"></a>

## 7. Giao diện, dashboard và runner

### 7.1 Terminal launcher

`main.py` là entrypoint terminal, hiển thị menu:

- Realtime Trading
- Demo / Paper Trading
- Backtest đơn luồng
- Backtest đa luồng
- Vectorized Backtest
- ML Training
- Dashboard Analytics
- Tối ưu hóa tham số

### 7.2 PyQt6 UI

Thư mục `hien_thi/` chứa các màn hình:

- `app/`
- `man_hinh/`
- `giao_dien/`
- `thanh_phan/`
- `dich_vu/`

Một số màn hình chính:

- `hien_thi/man_hinh/realtime.py`
- `hien_thi/man_hinh/demo.py`
- `hien_thi/man_hinh/backtest/*`
- `hien_thi/man_hinh/toi_uu/*`

### 7.3 Dashboard analytics

Dashboard tập trung vào:

- equity curve;
- drawdown;
- phân bố PnL;
- trade scatter;
- session analysis;
- heatmap.

### 7.4 Thành phần tái sử dụng

Các component UI được tách để dễ ghép lại:

- cards;
- charts;
- table widgets;
- mixin cho chiến lược active;
- worker thread cho tác vụ nặng.

---

<a name="toi-uu"></a>

## 8. Tối ưu hóa tham số

### 8.1 Mục tiêu

Thư mục `toi_uu_hoa/` dùng để:

- dò tham số;
- kiểm định guardrails;
- đánh giá chất lượng chiến lược;
- chạy walk-forward / multi-run.

### 8.2 Thành phần chính

- `bo_dieu_phoi.py`: điều phối tối ưu hóa;
- `dong_co_backtest.py`: engine backtest nhanh;
- `dang_ky_chi_bao.py`: registry chỉ báo;
- `phan_loai_chi_bao.py`: phân loại kiểu tín hiệu;
- `kiem_dinh.py`: kiểm định và guardrails;
- `thu_vien.py`: lưu / đọc chiến lược;
- `giao_dien_cli.py`: menu CLI.

### 8.3 Kiểu tối ưu hóa hiện có

- tối ưu một chiến lược;
- so sánh nhiều indicator;
- tối ưu combo nhiều điều kiện;
- tối ưu strategy plugin;
- đánh giá theo metric như Sharpe, Sortino, DSR.

### 8.4 Điểm cần nhớ

Base optimizer là bản **open** trong repo.
Theo tài liệu so sánh, bản **high** chỉ khác ở mức độ:

- điều phối thông minh hơn;
- tìm kiếm tham số hiệu quả hơn;
- không thay đổi core backtest engine.

---

<a name="luu-tru"></a>

## 9. Lưu trữ, log và phân tích SQL

### 9.1 DuckDB warehouse

`utils/kho_du_lieu.py` là lớp lưu trữ trung tâm:

- lưu run;
- lưu signal;
- lưu order/trade;
- lưu kết quả backtest;
- truy vấn thống kê cross-run.

### 9.2 Một số hàm tiêu biểu

- `tao_run_id()`
- `luu_run(...)`
- `luu_lenh_don(...)`
- `luu_ket_qua_backtest(...)`
- `luu_signal(...)`
- `thong_ke_theo_gio(...)`
- `thong_ke_theo_regime(...)`
- `phan_tich_exit_reason(...)`
- `sharpe_ratio(...)`
- `kelly_criterion(...)`
- `monte_carlo(...)`

### 9.3 Logging

`utils/log.py` cung cấp:

- logger chuẩn hóa;
- banner khởi động / kết quả;
- formatter thời gian động;
- helper cho console output.

### 9.4 Dữ liệu phụ trợ

`du_lieu/` thường chứa:

- cache OHLCV;
- log hoạt động;
- dữ liệu tạo trong quá trình chạy;
- file DuckDB của hệ thống.

---

<a name="edition"></a>

## 10. Bản base vs bản high (cập nhật 2026-06-26)

### 10.1 Ý nghĩa

Trong repo hiện tại:

- **base / open** 🔓 = **toàn bộ source code công khai** (bản này đã được nâng cấp đáng kể);
- **high / closed** 🔒 = bản tham chiếu hiệu năng cao hơn, không public source (tối ưu sâu thêm).

### 10.2 Khác biệt theo định vị hệ thtops

| Hạng mục | Base / Open (miễn phí công khai) | High / Closed (thương mại đóng) |
|---|---|---|
| **Indicator** | **49 `pt_*`**, 2.8K dòng, HTF confirmed/flat | **68 `pt_*`**, 7.2K dòng, live MTF intrabar |
| **Optimizer** | Walk-forward + DSR, 3.0K dòng | Bộ tìm kiếm thích ứng hội tụ nhanh |
| **ML** | 8 regime, 80 feature, trainer đầy đủ | Tối ưu sâu ở layer nội bộ |
| **Backtest** | Bar-to-bar + vectorized, in-memory | Giống hệt base |
| **Mức độ công khai** | ✅ Toàn bộ source trong repo | ❌ Không public |

### 10.3 Khi nào dùng bản nào

| Tình huống | Bản phù hợp |
|---|---|
| Học tập, PoC, thử nghiệm logic | **Base 🔓** (dễ sửa, đầy đủ, miễn phí) |
| Nghiên cứu production-ready, đa symbol | **Base 🔓** (đã đủ mạnh từ v2) |
| Tối ưu quy mô rất lớn, cần live HTF | **High 🔒** (liên hệ tác giả) |
| Backtesting chính xác bar-by-bar | **Base 🔓** (engine giống high) |

### 10.4 Cách đọc tài liệu so sánh

Nếu cần xem chênh lệch chi tiết giữa hai bản:

- [`so_sanh_phien_ban.md`](so_sanh_phien_ban.md)

Tài liệu này chỉ giữ vai trò:

- mô tả base đúng theo code hiện tại (không lỗi thời);
- không sao chép chi tiết nội bộ của high (giữ bí mật);
- đồng bộ giữa tài liệu và source code.

---

<a name="mo-rong"></a>

## 11. Cách mở rộng dự án

### 11.1 Thêm nguồn dữ liệu mới

1. Tạo file mới trong `lay_du_lieu/`.
2. Trả về `dict` hoặc `DataFrame` theo schema rõ ràng.
3. Gắn dữ liệu vào snapshot hoặc feature pipeline.
4. Chỉ cho strategy đọc từ một interface ổn định.

### 11.2 Thêm chỉ báo mới

1. Chọn module phù hợp trong `Indicator/`.
2. Viết hàm `pt_*` theo quy ước hiện tại.
3. Giữ tên cột có hậu tố timeframe.
4. Đảm bảo không dùng dữ liệu tương lai.

### 11.3 Thêm chiến lược mới

1. Thêm strategy trong `chien_luoc/user_strategies/` hoặc module tương ứng.
2. Khai báo registry nếu cần.
3. Cho phép optimizer gọi chiến lược đó qua cùng interface.
4. Ghi kết quả vào `utils/kho_du_lieu.py`.

### 11.4 Thêm feature cho ML

1. Sửa `ml/trang_thai_thi_truong_ml/tao_feature.py`.
2. Đồng bộ `model_info.json`.
3. Huấn luyện lại model.
4. Kiểm tra lại mapping `state_id ↔ strategy`.

### 11.5 Nguyên tắc an toàn

- ưu tiên **khớp schema**;
- tránh thay đổi tên cột tùy tiện;
- giữ tương thích giữa base / realtime / backtest / ML;
- mọi thay đổi nên đi qua một điểm vào trung tâm thay vì rải logic.

---

## Ghi chú cuối

### Changelog v2 (2026-06-26)

Tài liệu này được **cập nhật toàn diện** theo mã nguồn hiện tại của repository:

**Chính sách tài liệu:**
- Luôn mô tả bản **base / open** đúng theo source code hiện tại (không lỗi thời).
- Không sao chép chi tiết thuật toán nội bộ của bản high (giữ bí mật).
- Tham chiếu bản high chỉ để so sánh quy mô & định vị, không implementation details.

**Thay đổi đáng chú ý:**
- **Indicator**: 49 → **68 indicators** (từ 2.8K → 8.4K dòng); bây giờ base có full breadth.
- **Optimizer**: 3.0K → **3.9K dòng**; bổ sung logic walk-forward & multi-frame.
- **ML module**: Vẫn 8 regime, 80 feature; trainer đầy đủ trong repo.
- **Backtest**: Bar-to-bar & vectorized, engine giống với high.

**Các phần cần cập nhật lại nếu có thay đổi:**
- `Indicator/` — khi thêm/xóa indicator hoặc thay đổi HTF logic
- `toi_uu_hoa/` — khi cập nhật optimizer strategy
- `ml/` — khi thay đổi feature engineering hoặc model architecture
- `so_sanh_phien_ban.md` — khi thay đổi quy mô hoặc định vị bản
- Các module khác (hien_thi, lay_du_lieu, chien_luoc, etc.) — khi có nâng cấp đáng kể

