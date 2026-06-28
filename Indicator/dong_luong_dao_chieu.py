"""ĐẢO CHIỀU / ĐỘNG LƯỢNG (Momentum / Reversal) - Phiên bản Polars
👉 Lực đang yếu đi hay mạnh lên?
"""

import polars as pl
import numpy as np
import re
import math
from numpy.lib.stride_tricks import sliding_window_view


def _rai_xuong_tu_khung_lon(df, polars_time_frame, suffix, tinh_1m):
    """BẢN BASE (miễn phí): chỉ báo khung lớn được tính NGAY trên nến khung lớn rồi
    rải (forward-fill) xuống từng nến nhỏ — KHÔNG cập nhật live trong nến.

    Dùng lại chính logic khung 1m (`tinh_1m`) trên nến khung lớn đã đóng, sau đó
    join_asof backward về lưới thời gian gốc. Cột feature đuôi "_1m" → "_<suffix>".
    """
    base = {"timestamp", "open", "high", "low", "close", "volume"}
    htf = (
        df.group_by_dynamic(
            "timestamp", every=polars_time_frame, closed="left", label="left"
        )
        .agg([
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
            pl.col("volume").sum().alias("volume"),
        ])
        .drop_nulls(subset=["close"])
        .sort("timestamp")
    )
    htf = tinh_1m(htf)
    htf = htf.with_columns(pl.col("timestamp").dt.offset_by(polars_time_frame))
    feat = [c for c in htf.columns if c not in base]
    ren = {c: c[:-2] + suffix for c in feat if c.endswith("_1m")}
    htf = htf.rename(ren)
    feat = [ren.get(c, c) for c in feat]
    return df.join_asof(
        htf.select(["timestamp"] + feat), on="timestamp", strategy="backward"
    )


def calculate_mad_fast(tp_arr, window):
    """Tính Mean Absolute Deviation (MAD) cực nhanh bằng NumPy sliding_window_view."""
    n = len(tp_arr)
    mad_arr = np.full(n, np.nan)
    if n >= window:
        windows = sliding_window_view(tp_arr, window_shape=window)
        means = np.mean(windows, axis=1, keepdims=True)
        mads = np.mean(np.abs(windows - means), axis=1)
        mad_arr[window - 1:] = mads
    return mad_arr


def _cci_last_from_tp(tp_arr, window, constant):
    if len(tp_arr) < window:
        return np.nan
    win = tp_arr[-window:]
    mean_tp = np.mean(win)
    mad = np.mean(np.abs(win - mean_tp))
    if mad == 0:
        mad = 1e-9
    return (tp_arr[-1] - mean_tp) / (constant * mad)


def pt_rsi(df, time_frame, window=14):
    """Phân tích RSI dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF), dùng Wilder's Smoothing."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    col_name = f"rsi_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_rsi(d, "1m", window)
        )

    if time_frame == "1m":
        delta = pl.col("close").diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0.0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0)

        avg_gain = gain.ewm_mean(alpha=1 / window, adjust=False)
        avg_loss = loss.ewm_mean(alpha=1 / window, adjust=False)
        rs = avg_gain / pl.when(avg_loss == 0).then(1e-9).otherwise(avg_loss)
        rsi_val = pl.when(avg_loss == 0).then(100.0).otherwise(100.0 - (100.0 / (1.0 + rs)))

        df = df.with_columns(rsi_val.alias(col_name))
    return df


def pt_stochastic(df, time_frame, k_window=14, d_window=3):
    """
    Phân tích Stochastic Oscillator dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF).
    """
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    k_window = parse_window(k_window, 14)
    d_window = parse_window(d_window, 3)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_k = f"stoch_k_{time_frame}"
    c_d = f"stoch_d_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_stochastic(d, "1m", k_window, d_window)
        )

    if time_frame == "1m":
        low_min = pl.col("low").rolling_min(window_size=k_window)
        high_max = pl.col("high").rolling_max(window_size=k_window)

        denom = pl.when((high_max - low_min) == 0).then(1e-9).otherwise(high_max - low_min)
        k_series = 100 * (pl.col("close") - low_min) / denom
        d_series = k_series.rolling_mean(window_size=d_window)

        df = df.with_columns([
            k_series.alias(c_k),
            d_series.alias(c_d)
        ])

    df = df.with_columns([
        ((pl.col(c_k).fill_nan(None) > pl.col(c_d).fill_nan(None)).fill_null(False)).alias(f"stoch_bull_cross_{time_frame}"),
        ((pl.col(c_k).fill_nan(None) > 80).fill_null(False)).alias(f"stoch_overbought_{time_frame}"),
        ((pl.col(c_k).fill_nan(None) < 20).fill_null(False)).alias(f"stoch_oversold_{time_frame}")
    ]).with_columns([
        (pl.col(f"stoch_bull_cross_{time_frame}") & pl.col(f"stoch_oversold_{time_frame}")).alias(f"stoch_strong_buy_{time_frame}"),
        ((pl.col(c_k).fill_nan(None) < pl.col(c_d).fill_nan(None)).fill_null(False) & pl.col(f"stoch_overbought_{time_frame}")).alias(f"stoch_strong_sell_{time_frame}")
    ])

    return df


def _compute_mfi_polars(high_col, low_col, close_col, volume_col, w):
    """Tính MFI từ OHLCV bằng Polars Expressions."""
    tp = (high_col + low_col + close_col) / 3
    mf = tp * volume_col
    tp_diff = tp.diff()

    pos_mf = pl.when(tp_diff > 0).then(mf).otherwise(0.0)
    neg_mf = pl.when(tp_diff < 0).then(mf).otherwise(0.0)

    pos_sum = pos_mf.rolling_sum(window_size=w)
    neg_sum = neg_mf.rolling_sum(window_size=w)

    neg_sum_safe = pl.when(neg_sum == 0).then(1e-9).otherwise(neg_sum)
    mfi = 100 - 100 / (1 + pos_sum / neg_sum_safe)
    return mfi, tp


def pt_mfi(df, time_frame, window=14):
    """MFI - Hybrid Live Version"""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_mfi = f"mfi_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_mfi(d, "1m", window)
        )

    if time_frame == "1m":
        mfi_series, _ = _compute_mfi_polars(
            pl.col("high"), pl.col("low"), pl.col("close"), pl.col("volume"), window
        )
        df = df.with_columns(mfi_series.alias(c_mfi))
    df = df.with_columns([
        ((pl.col(c_mfi).fill_nan(None) > 80).fill_null(False)).alias(f"mfi_overbought_{time_frame}"),
        ((pl.col(c_mfi).fill_nan(None) < 20).fill_null(False)).alias(f"mfi_oversold_{time_frame}")
    ])

    return df


def _compute_ao_polars(high_col, low_col, fast_w, slow_w):
    """Tính Awesome Oscillator."""
    midprice = (high_col + low_col) / 2
    return midprice.rolling_mean(window_size=fast_w) - midprice.rolling_mean(window_size=slow_w)


def _compute_tsi_polars(close_col, long_w, short_w, signal_w):
    """Tính TSI và đường signal bằng double EMA smoothing."""
    momentum = close_col.diff()
    abs_momentum = momentum.abs()

    tsi_num = (
        momentum.ewm_mean(span=short_w, adjust=False)
        .ewm_mean(span=long_w, adjust=False)
    )
    tsi_den = (
        abs_momentum.ewm_mean(span=short_w, adjust=False)
        .ewm_mean(span=long_w, adjust=False)
    )

    tsi_den_safe = pl.when(tsi_den == 0).then(1e-9).otherwise(tsi_den)
    tsi_vals = 100 * tsi_num / tsi_den_safe
    sig_vals = tsi_vals.ewm_mean(span=signal_w, adjust=False)
    return tsi_vals, sig_vals


def _compute_uo_polars(high_col, low_col, close_col, period1, period2, period3):
    """Tính Ultimate Oscillator từ OHLC bằng Polars Expressions."""
    prev_close = close_col.shift(1)
    bp = close_col - pl.min_horizontal(low_col, prev_close)
    tr = pl.max_horizontal(high_col, prev_close) - pl.min_horizontal(low_col, prev_close)

    bp_sum1 = bp.rolling_sum(window_size=period1)
    tr_sum1 = tr.rolling_sum(window_size=period1)
    bp_sum2 = bp.rolling_sum(window_size=period2)
    tr_sum2 = tr.rolling_sum(window_size=period2)
    bp_sum3 = bp.rolling_sum(window_size=period3)
    tr_sum3 = tr.rolling_sum(window_size=period3)

    tr_sum1_safe = pl.when(tr_sum1 == 0).then(1e-9).otherwise(tr_sum1)
    tr_sum2_safe = pl.when(tr_sum2 == 0).then(1e-9).otherwise(tr_sum2)
    tr_sum3_safe = pl.when(tr_sum3 == 0).then(1e-9).otherwise(tr_sum3)

    avg1 = bp_sum1 / tr_sum1_safe
    avg2 = bp_sum2 / tr_sum2_safe
    avg3 = bp_sum3 / tr_sum3_safe

    uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / (4 + 2 + 1)
    return uo


def pt_ultimate_oscillator(df, time_frame, w1=7, w2=14, w3=28):
    """Ultimate Oscillator - Hybrid Live Version"""
    for param_name, default in [("w1", 7), ("w2", 14), ("w3", 28)]:
        val = locals()[param_name]
        if isinstance(val, str):
            num_str = re.sub(r"\D", "", val)
            val = int(num_str) if num_str else default
        else:
            val = int(val)
        if param_name == "w1":
            w1 = val
        if param_name == "w2":
            w2 = val
        if param_name == "w3":
            w3 = val

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_uo = f"uo_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_ultimate_oscillator(d, "1m", w1, w2, w3)
        )

    if time_frame == "1m":
        df = df.with_columns(
            _compute_uo_polars(pl.col("high"), pl.col("low"), pl.col("close"), w1, w2, w3).alias(c_uo)
        )
    df = df.with_columns([
        ((pl.col(c_uo).fill_nan(None) > 70).fill_null(False)).alias(f"uo_overbought_{time_frame}"),
        ((pl.col(c_uo).fill_nan(None) < 30).fill_null(False)).alias(f"uo_oversold_{time_frame}")
    ])

    return df


def pt_stoch_rsi(df, time_frame, window=14, smooth_k=3, smooth_d=3):
    """Stochastic RSI - Hybrid Live Version"""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)
    if isinstance(smooth_k, str):
        num_str = re.sub(r"\D", "", smooth_k)
        smooth_k = int(num_str) if num_str else 3
    else:
        smooth_k = int(smooth_k)
    if isinstance(smooth_d, str):
        num_str = re.sub(r"\D", "", smooth_d)
        smooth_d = int(num_str) if num_str else 3
    else:
        smooth_d = int(smooth_d)

    polars_time_frame = time_frame.lower()
    c_k = f"stochrsi_k_{time_frame}"
    c_d = f"stochrsi_d_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _stoch_rsi_calc(close_col):
        delta = close_col.diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0.0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0)
        avg_gain = gain.ewm_mean(alpha=1/window, adjust=False)
        avg_loss = loss.ewm_mean(alpha=1/window, adjust=False)
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi_min = rsi.rolling_min(window)
        rsi_max = rsi.rolling_max(window)
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-9) * 100.0
        stoch_rsi_k = stoch_rsi.rolling_mean(smooth_k)
        stoch_rsi_d = stoch_rsi_k.rolling_mean(smooth_d)
        return stoch_rsi_k, stoch_rsi_d, rsi, rsi_min, rsi_max, stoch_rsi, avg_gain, avg_loss


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_stoch_rsi(d, "1m", window, smooth_k, smooth_d)
        )

    if time_frame == "1m":
        stoch_k, stoch_d, _, _, _, _, _, _ = _stoch_rsi_calc(pl.col("close"))
        df_out = df.with_columns([
            stoch_k.alias(c_k),
            stoch_d.alias(c_d)
        ])
    return df_out


def _fisher_loop(hl2, window):
    n = len(hl2)
    val = np.zeros(n)
    fish = np.zeros(n)

    import pandas as pd
    hl2_series = pd.Series(hl2)
    rolling_min = hl2_series.rolling(window).min().values
    rolling_max = hl2_series.rolling(window).max().values

    for i in range(n):
        if i < window:
            val[i] = 0.0
            fish[i] = 0.0
            continue

        diff = rolling_max[i] - rolling_min[i]
        if diff < 1e-9:
            diff = 1e-9

        ratio = (hl2[i] - rolling_min[i]) / diff
        raw_val = 2 * (ratio - 0.5)
        val[i] = 0.33 * raw_val + 0.67 * val[i-1]
        val[i] = min(max(val[i], -0.999), 0.999)

        fish[i] = 0.5 * np.log((1 + val[i]) / (1 - val[i] + 1e-9)) + 0.5 * fish[i-1]

    return fish


def pt_stc(df, time_frame, fast=23, slow=50, cycle=10):
    """Schaff Trend Cycle - Hybrid Live Version"""
    if isinstance(fast, str):
        num_str = re.sub(r"\D", "", fast)
        fast = int(num_str) if num_str else 23
    else:
        fast = int(fast)
    if isinstance(slow, str):
        num_str = re.sub(r"\D", "", slow)
        slow = int(num_str) if num_str else 50
    else:
        slow = int(slow)
    if isinstance(cycle, str):
        num_str = re.sub(r"\D", "", cycle)
        cycle = int(num_str) if num_str else 10
    else:
        cycle = int(cycle)

    polars_time_frame = time_frame.lower()
    c_stc = f"stc_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _stc_calc(close_col):
        macd = close_col.ewm_mean(span=fast, adjust=False) - close_col.ewm_mean(span=slow, adjust=False)
        macd_min = macd.rolling_min(cycle)
        macd_max = macd.rolling_max(cycle)
        stoch1 = (macd - macd_min) / (macd_max - macd_min + 1e-9)
        stoch1_smoothed = stoch1.ewm_mean(span=3, adjust=False)

        stoch1_min = stoch1_smoothed.rolling_min(cycle)
        stoch1_max = stoch1_smoothed.rolling_max(cycle)
        stoch2 = (stoch1_smoothed - stoch1_min) / (stoch1_max - stoch1_min + 1e-9)
        stc = stoch2.ewm_mean(span=3, adjust=False) * 100
        return stc, macd, macd_min, macd_max


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_stc(d, "1m", fast, slow, cycle)
        )

    if time_frame == "1m":
        stc, _, _, _ = _stc_calc(pl.col("close"))
        df_out = df.with_columns(stc.alias(c_stc))
    return df_out
