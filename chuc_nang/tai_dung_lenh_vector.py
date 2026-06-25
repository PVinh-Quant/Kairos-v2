"""
chuc_nang/tai_dung_lenh_vector.py — Tái dựng lịch sử LỆNH từ file CSV dump OHLCV của vector.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
File trong du_lieu/du_lieu_vectorized/<SYMBOL>/<SYMBOL>_1m_backtest_*.csv KHÔNG chứa
cột lệnh (symbol, side, time_close, pnl_usd) — nó chứa OHLCV + cột tín hiệu mỗi nến
(timestamp, open, high, low, close, signal, regime, entry_signal, sl_pct, tp_pct,
leverage…). Module này "truy vấn" lại danh sách lệnh bằng cách REPLAY ĐÚNG vòng lặp
của chuc_nang/vectorized_backtest.py trên các cột đó, rồi trả về DataFrame theo schema
cột tiếng Việt (Symbol, Loại, PnL, Time…) — y hệt định dạng mà dashboard backtest đã
biết chuẩn hóa qua _chuan_hoa_lenh_vector. Nhờ vậy "Mở File CSV" nạp được file dump.

LƯU Ý: đây là bản sao logic của vòng lặp trong vectorized_backtest() (vào lệnh ở nến sau
tín hiệu, thoát theo SL→TP→LIQUIDATION→đảo chiều, cùng mô hình phí/slippage/cooldown/
warm-up). Nếu sửa engine kia thì cập nhật cả file này để 2 bên đồng bộ.
"""

import os
import re

import numpy as np
import polars as pl

from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao

                                                                                    
WARMUP_NEN = 43200

                                                                                     
COT_CAN = [
    "timestamp", "open", "high", "low", "close",
    "signal", "sl_pct", "tp_pct", "leverage", "regime",
]


def la_file_dump_vector(columns) -> bool:
    """True nếu danh sách cột là file dump OHLCV của vector (cần tái dựng lệnh).

    Nhận diện: có timestamp + close + (signal hoặc entry_signal) NHƯNG thiếu cột lệnh.
    """
    cols = set(columns)
    co_ohlcv = {"timestamp", "close"}.issubset(cols) and bool(
        cols & {"signal", "entry_signal"}
    )
    khong_phai_file_lenh = not ({"PnL", "Loại", "pnl_usd"} & cols)
    return co_ohlcv and khong_phai_file_lenh


def _doan_symbol_tu_ten(file_path: str) -> str:
    """Suy ra tên cặp từ tên file dump, vd 'BNB_USDT_1m_backtest_...' -> 'BNB_USDT'."""
    ten = os.path.basename(file_path)
    m = re.match(r"([A-Za-z0-9]+_[A-Za-z0-9]+)", ten)
    return m.group(1) if m else os.path.splitext(ten)[0]


def tai_dung_lenh_tu_dump(file_path: str) -> pl.DataFrame:
    """Đọc file dump OHLCV của vector và tái dựng danh sách lệnh (schema cột tiếng Việt).

    Trả về pl.DataFrame rỗng nếu không có lệnh nào.
    """
    cfg_ao = lay_cau_hinh_ao()
    cfg_gd = lay_cau_hinh_giao_dich()

    VON_BAN_DAU = float(cfg_ao.get("so_du_ban_dau", 10000))
    PHI_GD = float(cfg_ao.get("phi_giao_dich", 0.001))
    SLIPPAGE = float(cfg_ao.get("do_truot_gia", 0.001))
    DON_BAY = int(cfg_gd.get("don_bay", 1))
    VON_MOI_LENH = float(cfg_gd.get("von_moi_lenh_usdt", 100))
    COOLDOWN_NEN = int(cfg_gd.get("cooldown_nen", 5))

    symbol = _doan_symbol_tu_ten(file_path)

                                                                                     
    header = pl.read_csv(file_path, n_rows=1).columns
    need = [c for c in COT_CAN if c in header]
    df = pl.read_csv(file_path, columns=need, infer_schema_length=10000)
    n = len(df)
    if n == 0:
        return pl.DataFrame()

                                                                     
    signals = df["signal"].to_numpy() if "signal" in df.columns else np.zeros(n, dtype=int)
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy() if "high" in df.columns else closes.copy()
    lows = df["low"].to_numpy() if "low" in df.columns else closes.copy()
    times = df["timestamp"].to_numpy()
    sl_pcts = df["sl_pct"].to_numpy() if "sl_pct" in df.columns else np.full(n, 0.05)
    tp_pcts = df["tp_pct"].to_numpy() if "tp_pct" in df.columns else np.full(n, 0.10)
    leverages = df["leverage"].to_numpy() if "leverage" in df.columns else np.full(n, DON_BAY)
    regimes = df["regime"].to_numpy() if "regime" in df.columns else np.zeros(n, dtype=int)

                                                                               
    lich_su = []
    von_hien_tai = VON_BAN_DAU
    vi_the = 0
    co_tin_hieu = 0
    don_bay_vao = DON_BAY
    gia_vao = 0.0
    sl_gia = tp_gia = 0.0
    thoi_gian_vao = None
    sl_pct_vao = tp_pct_vao = 0.0
    regime_vao = 0
    dem_cooldown = 0

    signal_indices = np.where(signals != 0)[0]
    num_signals = len(signal_indices)
    sig_ptr = 0

    idx_start = WARMUP_NEN if n > WARMUP_NEN else 0
    i = idx_start
    while i < n:
        if dem_cooldown > 0:
            dem_cooldown -= 1

                                                                                      
        if vi_the == 0 and co_tin_hieu == 0 and dem_cooldown == 0:
            while sig_ptr < num_signals and signal_indices[sig_ptr] < i:
                sig_ptr += 1
            if sig_ptr >= num_signals:
                break
            i = signal_indices[sig_ptr]

        tin_hieu_hien_tai = signals[i]
        tin_hieu_raw = signals[i]                                                 
        gia_open = opens[i]
        gia_high = highs[i]
        gia_low = lows[i]
        thoi_gian = times[i]
        don_bay_i = int(leverages[i])

                                               
        if co_tin_hieu != 0 and vi_the == 0:
            if von_hien_tai < VON_MOI_LENH:
                co_tin_hieu = 0
                i += 1
                continue
            vi_the = co_tin_hieu
            don_bay_vao = don_bay_i
            regime_vao = int(regimes[i - 1]) if i > 0 else 0
            phi_truot = gia_open * SLIPPAGE
            gia_vao = gia_open + phi_truot if vi_the == 1 else gia_open - phi_truot
            sl_pct_i = sl_pcts[i - 1] if i > 0 else 0.05
            tp_pct_i = tp_pcts[i - 1] if i > 0 else 0.10
            if vi_the == 1:
                sl_gia = gia_vao * (1 - sl_pct_i)
                tp_gia = gia_vao * (1 + tp_pct_i)
            else:
                sl_gia = gia_vao * (1 + sl_pct_i)
                tp_gia = gia_vao * (1 - tp_pct_i)
            von_hien_tai -= (VON_MOI_LENH * don_bay_vao) * PHI_GD
            co_tin_hieu = 0
            thoi_gian_vao = thoi_gian
            sl_pct_vao = sl_pct_i
            tp_pct_vao = tp_pct_i

                                                    
        if vi_the != 0:
            can_thoat = False
            loai = "LONG" if vi_the == 1 else "SHORT"
            gia_dong = closes[i]
            ly_do_thoat = ""

            if vi_the == 1:
                liq_price = gia_vao * (1 - 1 / don_bay_vao)
                if gia_low <= sl_gia:
                    can_thoat, gia_dong, ly_do_thoat = True, sl_gia, "SL"
                elif gia_high >= tp_gia:
                    can_thoat, gia_dong, ly_do_thoat = True, tp_gia, "TP"
                elif gia_low <= liq_price:
                    can_thoat, gia_dong, ly_do_thoat = True, liq_price, "LIQUIDATION"
                elif tin_hieu_raw == -1:
                    can_thoat, ly_do_thoat = True, "SIGNAL"
            else:
                liq_price = gia_vao * (1 + 1 / don_bay_vao)
                if gia_high >= sl_gia:
                    can_thoat, gia_dong, ly_do_thoat = True, sl_gia, "SL"
                elif gia_low <= tp_gia:
                    can_thoat, gia_dong, ly_do_thoat = True, tp_gia, "TP"
                elif gia_high >= liq_price:
                    can_thoat, gia_dong, ly_do_thoat = True, liq_price, "LIQUIDATION"
                elif tin_hieu_raw == 1:
                    can_thoat, ly_do_thoat = True, "SIGNAL"

            if can_thoat:
                if ly_do_thoat != "LIQUIDATION":
                    phi_truot_dong = gia_dong * SLIPPAGE
                    gia_dong = gia_dong - phi_truot_dong if vi_the == 1 else gia_dong + phi_truot_dong

                if ly_do_thoat == "LIQUIDATION":
                    pnl_raw = -VON_MOI_LENH
                    phi_dong = 0.0
                else:
                    pnl_raw = (
                        (gia_dong - gia_vao) / gia_vao
                        if vi_the == 1
                        else (gia_vao - gia_dong) / gia_vao
                    ) * (VON_MOI_LENH * don_bay_vao)
                    phi_dong = (VON_MOI_LENH * don_bay_vao) * PHI_GD
                phi_mo_lenh = (VON_MOI_LENH * don_bay_vao) * PHI_GD
                pnl_net = pnl_raw - phi_dong - phi_mo_lenh
                von_hien_tai += (pnl_raw - phi_dong)

                lich_su.append({
                    "Symbol": symbol,
                    "Loại": loai,
                    "Regime": regime_vao,
                    "Giá vào": gia_vao,
                    "Giá đóng": gia_dong,
                    "Leverage": don_bay_vao,
                    "PnL": pnl_net,
                    "Time": thoi_gian,
                    "Balance": von_hien_tai,
                    "Strategy": "",
                    "Entry_Time": thoi_gian_vao,
                    "SL_pct": sl_pct_vao,
                    "TP_pct": tp_pct_vao,
                    "Exit_Reason": ly_do_thoat,
                })
                vi_the = 0
                dem_cooldown = COOLDOWN_NEN

                                  
        if vi_the == 0 and co_tin_hieu == 0 and tin_hieu_hien_tai != 0 and dem_cooldown == 0:
            co_tin_hieu = tin_hieu_hien_tai

        i += 1

    if not lich_su:
        return pl.DataFrame()

                                                                      
    lich_su.sort(key=lambda x: str(x.get("Time", "")))
    bal = VON_BAN_DAU
    for t in lich_su:
        bal += t.get("PnL", 0.0)
        t["Balance"] = bal

    return pl.DataFrame(lich_su)
