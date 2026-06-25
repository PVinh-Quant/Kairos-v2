"""
kiem_thu/test_dong_bo_tin_hieu.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Golden/regression test (Phase 4a) — KHÓA các thành quả đồng bộ engine, chống trôi lệch:

  B   — Logic kết hợp tín hiệu: ket_hop_tin_hieu_spec PHẢI khớp bản tham chiếu (logic gốc).
        Cả optimizer (_chay_backtest_combo) lẫn JSONStrategy.tinh_tin_hieu_vectorized đều ủy
        thác cho hàm này → pin hàm này = pin cả 2 nhánh.
  D   — Khung ATR cho SL/TP: cách optimizer (them_sl_tp, không truyền tf) PHẢI khớp cách
        vectorized resolve sl_tp_tf (default "15m" + override Q.SL_TP_TIME_FRAME).
  #4/#5 — run_fast_backtest hạch toán nhất quán: tổng trade['pnl'] == (von_cuoi - von_ban_dau)
        (phí mở nằm trong pnl ghi nhận; thanh lý = -von_moi_lenh - phí_mở).
  #6  — run_fast_backtest tôn trọng tham số cooldown_nen (chặn vào lệnh sau khi đóng).

Chạy trực tiếp:  env/Scripts/python.exe kiem_thu/test_dong_bo_tin_hieu.py
Hoặc qua pytest: pytest kiem_thu/test_dong_bo_tin_hieu.py
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import polars as pl
import pandas as pd

from toi_uu_hoa.phan_loai_chi_bao import generate_generic_signals, ket_hop_tin_hieu_spec
import chien_luoc.optimizer.stoploss_takeprofit as SLTP
import chien_luoc.quan_ly_chien_luoc_vectorized as Q
from toi_uu_hoa.dong_co_backtest import run_fast_backtest


                                                                               
                                                                                
                                                                               
def _reference_combine(df, resolved, logic, persistence):
    """Bản sao NGUYÊN VĂN logic kết hợp cũ (trước khi gộp về ket_hop_tin_hieu_spec)."""
    trig_long_list, trig_short_list = [], []
    filt_long_list, filt_short_list = [], []
    for r in resolved:
        tcol = r["tcol"]
        if tcol is None:
            continue
        df_sig = generate_generic_signals(df, r["t_type"], tcol, r["thresholds"])
        sig = df_sig["signal"]
        long_i = (sig == 1); short_i = (sig == -1)
        if r.get("role", "trigger") == "filter":
            filt_long_list.append(long_i); filt_short_list.append(short_i)
        else:
            if persistence and persistence > 1:
                long_i = (long_i.cast(pl.Int8).rolling_max(window_size=persistence, min_samples=1) == 1)
                short_i = (short_i.cast(pl.Int8).rolling_max(window_size=persistence, min_samples=1) == 1)
            trig_long_list.append(long_i); trig_short_list.append(short_i)
    if not trig_long_list:
        return df.with_columns(pl.lit(0).cast(pl.Int64).alias("signal")), False

    def _kh(ds, c):
        out = ds[0]
        for s in ds[1:]:
            out = (out & s) if c == "and" else (out | s)
        return out

    tl = _kh(trig_long_list, logic); ts = _kh(trig_short_list, logic)
    fl = _kh(filt_long_list, "and") if filt_long_list else None
    fs = _kh(filt_short_list, "and") if filt_short_list else None
    finl = tl if fl is None else (tl & fl); fins = ts if fs is None else (ts & fs)
    d = df.with_columns([finl.alias("_fl"), fins.alias("_fs")])
    d = d.with_columns(
        pl.when(pl.col("_fl") & ~pl.col("_fs")).then(1)
        .when(pl.col("_fs") & ~pl.col("_fl")).then(-1)
        .otherwise(0).cast(pl.Int64).alias("signal")
    ).drop(["_fl", "_fs"])
    return d, True


def _df_chi_bao():
    rng = np.random.default_rng(7)
    n = 2000
    return pl.DataFrame({
        "timestamp": np.arange(n),
        "close": 100 + np.cumsum(rng.normal(0, 1, n)),
        "s0_rsi_15m": rng.uniform(0, 100, n),
        "s1_rsi_1h": rng.uniform(0, 100, n),
        "s2_ema_5m": 100 + np.cumsum(rng.normal(0, 1, n)),
    })


def test_b_ket_hop_tin_hieu_khop_tham_chieu():
    df = _df_chi_bao()
    specs = [
        {"t_type": "oscillator", "tcol": "s0_rsi_15m", "thresholds": {"oversold": 30, "overbought": 70}, "role": "trigger"},
        {"t_type": "trend",      "tcol": "s2_ema_5m",  "thresholds": {"dev_above": 1.0, "dev_below": 1.0}, "role": "trigger"},
        {"t_type": "oscillator", "tcol": "s1_rsi_1h",  "thresholds": {"oversold": 40, "overbought": 60}, "role": "filter"},
    ]
    for logic, pers in [("and", 1), ("or", 1), ("and", 3), ("or", 5)]:
        new_df, new_ct = ket_hop_tin_hieu_spec(df, specs, logic=logic, persistence=pers)
        ref_df, ref_ct = _reference_combine(df, specs, logic, pers)
        assert new_df["signal"].equals(ref_df["signal"]), f"signal lệch tham chiếu (logic={logic}, pers={pers})"
        assert new_ct == ref_ct, f"co_trigger lệch (logic={logic}, pers={pers})"

                                                                     
    only_filter = [{"t_type": "oscillator", "tcol": "s1_rsi_1h", "thresholds": {}, "role": "filter"}]
    nf_df, nf_ct = ket_hop_tin_hieu_spec(df, only_filter, logic="and", persistence=1)
    assert nf_ct is False
    assert int((nf_df["signal"] != 0).sum()) == 0


                                                                               
                                                                                     
                                                                               
def _df_ohlc_1m(days=7):
    rng = np.random.default_rng(11)
    n = days * 1440
    from datetime import datetime, timedelta
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    t0 = datetime(2025, 1, 1)
    return pl.DataFrame({
        "timestamp": [t0 + timedelta(minutes=i) for i in range(n)],
        "open": close + rng.normal(0, 0.1, n),
        "high": close + np.abs(rng.normal(0, 0.5, n)),
        "low": close - np.abs(rng.normal(0, 0.5, n)),
        "close": close,
        "volume": rng.uniform(1, 10, n),
    })


def test_d_khung_atr_sl_tp_dong_bo():
    df = _df_ohlc_1m()
    base_sl, rr = 2.5, 2.0
    _old_dyn, _old_tf = getattr(Q, "DUNG_SL_TP_DONG", False), getattr(Q, "SL_TP_TIME_FRAME", None)
    try:
                                                                             
        Q.DUNG_SL_TP_DONG = True
        Q.SL_TP_TIME_FRAME = None
        opt_new = SLTP.them_sl_tp(df, base_sl=base_sl, rr=rr)                                
        vec = SLTP.tinh_sl_tp(df, time_frame="15m", base_sl=base_sl, rr=rr)                      
        assert opt_new["sl_pct"].equals(vec["sl_pct"]) and opt_new["tp_pct"].equals(vec["tp_pct"]), \
            "optimizer != vectorized(15m) khi tf=None"

                                                
        Q.SL_TP_TIME_FRAME = "30m"
        opt_ovr = SLTP.them_sl_tp(df, base_sl=base_sl, rr=rr)
        vec_ovr = SLTP.tinh_sl_tp(df, time_frame="30m", base_sl=base_sl, rr=rr)
        assert opt_ovr["sl_pct"].equals(vec_ovr["sl_pct"]) and opt_ovr["tp_pct"].equals(vec_ovr["tp_pct"]), \
            "optimizer != vectorized(30m) khi override"

                                                                
        Q.DUNG_SL_TP_DONG = False
        Q.SL_TP_TIME_FRAME = None
        f_new = SLTP.them_sl_tp(df, base_sl=base_sl, rr=rr)
        f_fix = SLTP.tinh_sl_tp_co_dinh(df, base_sl=base_sl, rr=rr)
        assert f_new["sl_pct"].equals(f_fix["sl_pct"]) and f_new["tp_pct"].equals(f_fix["tp_pct"]), \
            "SL/TP cố định bị regression"
    finally:
        Q.DUNG_SL_TP_DONG, Q.SL_TP_TIME_FRAME = _old_dyn, _old_tf


                                                                               
                                                   
                                                                               
def _df_lenh(signals, closes, lows, sl_pct=0.02, tp_pct=0.05, lev=1):
    n = len(closes)
    highs = [c * 1.001 for c in closes]
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="min"),
        "open": closes, "high": highs, "low": lows, "close": closes,
        "signal": signals, "signal_raw": signals,
        "sl_pct": [sl_pct] * n, "tp_pct": [tp_pct] * n, "leverage": [lev] * n,
    })


def test_e_hach_toan_phi_nhat_quan():
    """#4: tổng pnl ghi nhận == thay đổi số dư (phí mở nằm trong pnl)."""
    von_ban_dau, von_moi_lenh, phi_gd, slippage = 10000.0, 100.0, 0.001, 0.0005
                                                              
    n = 12
    signals = [0] * n; signals[5] = 1
    closes = [100.0] * n
    lows = [c * 0.999 for c in closes]; lows[8] = 90.0
    df = _df_lenh(signals, closes, lows, sl_pct=0.02, lev=1)

    trades, von_cuoi = run_fast_backtest(df, von_ban_dau, phi_gd, slippage, von_moi_lenh, 1, cooldown_nen=5)
    assert len(trades) == 1, f"kỳ vọng 1 lệnh, có {len(trades)}"
    tong_pnl = sum(t["pnl"] for t in trades)
                                                                      
    assert abs(tong_pnl - (von_cuoi - von_ban_dau)) < 1e-6, \
        f"pnl ghi nhận ({tong_pnl}) != thay đổi số dư ({von_cuoi - von_ban_dau}) → phí mở bị bỏ sót"


def test_e_thanh_ly_tru_phi_mo():
    """#5: thanh lý ghi pnl = -von_moi_lenh - phí_mở (giống vectorized)."""
    von_ban_dau, von_moi_lenh, phi_gd, slippage = 10000.0, 100.0, 0.001, 0.0005
    lev = 10
    n = 12
    signals = [0] * n; signals[5] = 1
    closes = [100.0] * n
    lows = [c * 0.999 for c in closes]; lows[8] = 88.0                                    
    df = _df_lenh(signals, closes, lows, sl_pct=0.15, lev=lev)

    trades, von_cuoi = run_fast_backtest(df, von_ban_dau, phi_gd, slippage, von_moi_lenh, lev, cooldown_nen=5)
    assert len(trades) == 1, f"kỳ vọng 1 lệnh thanh lý, có {len(trades)}"
    phi_mo = von_moi_lenh * lev * phi_gd
    expected = -von_moi_lenh - phi_mo
    assert abs(trades[0]["pnl"] - expected) < 1e-6, f"pnl thanh lý {trades[0]['pnl']} != {expected}"
    assert abs(sum(t["pnl"] for t in trades) - (von_cuoi - von_ban_dau)) < 1e-6


def test_f_cooldown_duoc_ton_trong():
    """#6: cooldown lớn hơn dữ liệu → chỉ 1 lệnh; cooldown 0 → nhiều lệnh hơn."""
    von_ban_dau, von_moi_lenh, phi_gd, slippage = 10000.0, 100.0, 0.001, 0.0005
    n = 15
    signals = [0] * n; signals[5] = 1; signals[8] = 1
    closes = [100.0] * n
    lows = [c * 0.999 for c in closes]; lows[7] = 90.0; lows[10] = 90.0
    df = _df_lenh(signals, closes, lows, sl_pct=0.02, lev=1)

    trades_cd0, _ = run_fast_backtest(df.copy(), von_ban_dau, phi_gd, slippage, von_moi_lenh, 1, cooldown_nen=0)
    trades_cdbig, _ = run_fast_backtest(df.copy(), von_ban_dau, phi_gd, slippage, von_moi_lenh, 1, cooldown_nen=1000)
    assert len(trades_cd0) > len(trades_cdbig), "cooldown=0 phải cho NHIỀU lệnh hơn cooldown=1000"
    assert len(trades_cdbig) == 1, f"cooldown=1000 phải chặn vào lệnh lần 2 (có {len(trades_cdbig)} lệnh)"


_TESTS = [
    ("B  combine == tham chiếu", test_b_ket_hop_tin_hieu_khop_tham_chieu),
    ("D  khung ATR SL/TP",       test_d_khung_atr_sl_tp_dong_bo),
    ("#4 phí mở trong pnl",      test_e_hach_toan_phi_nhat_quan),
    ("#5 thanh lý trừ phí mở",   test_e_thanh_ly_tru_phi_mo),
    ("#6 cooldown tôn trọng",    test_f_cooldown_duoc_ton_trong),
]

if __name__ == "__main__":
    fail = 0
    for ten, fn in _TESTS:
        try:
            fn()
            print(f"  [PASS] {ten}")
        except Exception as e:
            fail += 1
            print(f"  [FAIL] {ten}: {e}")
    print("\nKET QUA:", "PASS" if fail == 0 else f"FAIL ({fail}/{len(_TESTS)})")
    sys.exit(1 if fail else 0)
