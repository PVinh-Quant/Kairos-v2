"""XU HƯỚNG (Trend) - Phiên bản Polars + ta library (Bản cấp thấp)
👉 Giá đang đi hướng nào?
- EMA, SMA
- MACD
- ADX
- Ichimoku
- SuperTrend
- PSAR
- Aroon
- Vortex
- HMA, KAMA, TRIX, ALMA, VWMA
📌 Dùng để chọn phe BUY / SELL
"""

import polars as pl
import pandas as pd
import numpy as np
import ta
import ta.trend
import ta.momentum
import ta.volatility
import re
import math


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


def calculate_supertrend_fast(high, low, close, window=10, multiplier=3.0):
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)
    atr = ta.volatility.average_true_range(high=high_s, low=low_s, close=close_s, window=window).to_numpy()

    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(close)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    supertrend = np.full(n, np.nan)
    direction = np.full(n, 1, dtype=int)

    first_valid_arr = np.flatnonzero(~np.isnan(atr))
    if len(first_valid_arr) == 0:
        return supertrend, np.zeros(n, dtype=bool)

    first_valid = int(first_valid_arr[0])
    final_upper[first_valid] = basic_upper[first_valid]
    final_lower[first_valid] = basic_lower[first_valid]
    supertrend[first_valid] = final_upper[first_valid]

    for i in range(first_valid + 1, n):
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        if supertrend[i - 1] == final_upper[i - 1]:
            direction[i] = -1 if close[i] > final_upper[i] else 1
        else:
            direction[i] = 1 if close[i] < final_lower[i] else -1

        supertrend[i] = final_lower[i] if direction[i] < 0 else final_upper[i]

    return supertrend, direction < 0


def pt_ema_trend(df, time_frame, window=20):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    col_ema_name = f"ema_{window}_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_ema_trend(d, "1m", window)
        )


    df_pd = df.select(["close"]).to_pandas()
    ema_val = ta.trend.ema_indicator(close=df_pd["close"], window=window)
    df_out = df.with_columns(pl.Series(col_ema_name, ema_val))

    df_out = df_out.with_columns(
        pl.when(pl.col("close").fill_nan(None) > pl.col(col_ema_name).fill_nan(None))
        .then(pl.lit("UP"))
        .otherwise(pl.lit("DOWN"))
        .alias(f"is_trend_{time_frame}")
    )

    distance_pct = (pl.col("close") - pl.col(col_ema_name)).abs() / pl.col(col_ema_name)
    df_out = df_out.with_columns(
        (distance_pct.fill_nan(None) > 0.005).fill_null(False).alias(f"trend_strong_{time_frame}")
    )

    _ema_safe = pl.when(pl.col(col_ema_name) != 0).then(pl.col(col_ema_name)).otherwise(None)
    df_out = df_out.with_columns(
        ((pl.col("close") - pl.col(col_ema_name)) / _ema_safe).alias(f"ema_dist_{time_frame}")
    )

    return df_out


def pt_sma(df, time_frame, window=20):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    col_sma = f"sma_{window}_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_sma(d, "1m", window)
        )

    if window <= 1:
        df_out = df.with_columns(pl.col("close").alias(col_sma))
    else:
        df_pd = df.select(["close"]).to_pandas()
        sma_val = ta.trend.sma_indicator(close=df_pd["close"], window=window)
        df_out = df.with_columns(pl.Series(col_sma, sma_val))

    df_out = df_out.with_columns(
        (pl.col("close").fill_nan(None) > pl.col(col_sma).fill_nan(None)).fill_null(False).alias(f"is_above_sma_{window}_{time_frame}")
    )

    distance_pct = (pl.col("close") - pl.col(col_sma)).abs() / pl.col(col_sma)
    df_out = df_out.with_columns(
        (distance_pct.fill_nan(None) > 0.02).fill_null(False).alias(f"sma_overextended_{window}_{time_frame}")
    )

    _sma_safe = pl.when(pl.col(col_sma) != 0).then(pl.col(col_sma)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - pl.col(col_sma)) / _sma_safe).alias(f"sma_dist_{time_frame}"))

    return df_out


def pt_adx(df, time_frame, window=28):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 28
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    col_adx = f"adx_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        adx_val = ta.trend.ADXIndicator(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], window=window).adx()
        df_out = df.with_columns(pl.Series(col_adx, adx_val))
    else:
        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=polars_time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low", "close"]).to_pandas()
        adx_val = ta.trend.ADXIndicator(high=htf_pd["high"], low=htf_pd["low"], close=htf_pd["close"], window=window).adx()
        htf = htf.with_columns(pl.Series("adx", adx_val))
        htf_to_join = htf.select(["timestamp", "adx"])
        df_out = df.join_asof(htf_to_join, on="timestamp", strategy="backward").rename({"adx": col_adx})

    df_out = df_out.with_columns([
        (pl.col(col_adx).fill_nan(None) > 25.0).fill_null(False).alias(f"has_trend_{time_frame}"),
        (pl.col(col_adx).fill_nan(None) > 40.0).fill_null(False).alias(f"is_strong_trend_{time_frame}")
    ])

    return df_out


def pt_ichimoku(df, time_frame, n1=9, n2=26, n3=52):
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    n1 = parse_window(n1, 9)
    n2 = parse_window(n2, 26)
    n3 = parse_window(n3, 52)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_tenkan = f"ichi_tenkan_{time_frame}"
    c_kijun = f"ichi_kijun_{time_frame}"
    c_senkou_a = f"ichi_senkou_a_{time_frame}"
    c_senkou_b = f"ichi_senkou_b_{time_frame}"
    c_senkou_a_lead = f"ichi_senkou_a_lead_{time_frame}"
    c_senkou_b_lead = f"ichi_senkou_b_lead_{time_frame}"
    c_chikou_ref = f"ichi_chikou_ref_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_ichimoku(d, "1m", n1, n2, n3)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        ichi_vis = ta.trend.IchimokuIndicator(high=df_pd["high"], low=df_pd["low"], window1=n1, window2=n2, window3=n3, visual=True)
        ichi_lead = ta.trend.IchimokuIndicator(high=df_pd["high"], low=df_pd["low"], window1=n1, window2=n2, window3=n3, visual=False)

        df_out = df.with_columns([
            pl.Series(c_tenkan, ichi_vis.ichimoku_conversion_line()),
            pl.Series(c_kijun, ichi_vis.ichimoku_base_line()),
            pl.Series(c_senkou_a, ichi_vis.ichimoku_a()),
            pl.Series(c_senkou_b, ichi_vis.ichimoku_b()),
            pl.Series(c_senkou_a_lead, ichi_lead.ichimoku_a()),
            pl.Series(c_senkou_b_lead, ichi_lead.ichimoku_b()),
            pl.col("close").shift(n2).alias(c_chikou_ref)
        ])
    kumo_top = pl.max_horizontal(pl.col(c_senkou_a), pl.col(c_senkou_b))
    kumo_bottom = pl.min_horizontal(pl.col(c_senkou_a), pl.col(c_senkou_b))

    df_out = df_out.with_columns([
        (pl.col("close").fill_nan(None) > kumo_top.fill_nan(None)).fill_null(False).alias(f"ichi_above_cloud_{time_frame}"),
        (pl.col("close").fill_nan(None) < kumo_bottom.fill_nan(None)).fill_null(False).alias(f"ichi_below_cloud_{time_frame}"),
        (pl.col(c_tenkan).fill_nan(None) > pl.col(c_kijun).fill_nan(None)).fill_null(False).alias(f"ichi_tk_bullish_{time_frame}"),
        (pl.col("close").fill_nan(None) > pl.col(c_chikou_ref).fill_nan(None)).fill_null(False).alias(f"ichi_chikou_bullish_{time_frame}"),
        (pl.col(c_senkou_a).fill_nan(None) > pl.col(c_senkou_b).fill_nan(None)).fill_null(False).alias(f"ichi_cloud_green_{time_frame}")
    ])

    _kumo_mid = (kumo_top + kumo_bottom) / 2
    _km_safe = pl.when(pl.col("close") != 0).then(pl.col("close")).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - _kumo_mid) / _km_safe).alias(f"cloud_dist_{time_frame}"))

    return df_out


def pt_supertrend(df, time_frame, window=10, multiplier=3.0):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 10
    else:
        window = int(window)

    multiplier = float(multiplier)
    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_st = f"supertrend_{time_frame}"
    c_trend = f"is_st_uptrend_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_supertrend(d, "1m", window, multiplier)
        )

    if time_frame == "1m":
        st_val, st_up = calculate_supertrend_fast(
            df["high"].to_numpy(),
            df["low"].to_numpy(),
            df["close"].to_numpy(),
            window,
            multiplier
        )
        df_out = df.with_columns([
            pl.Series(st_val).alias(c_st),
            pl.Series(st_up).alias(c_trend)
        ])
    _st_safe = pl.when(pl.col(c_st) != 0).then(pl.col(c_st)).otherwise(None)
    df_out = df_out.with_columns(
        ((pl.col("close") - pl.col(c_st)) / _st_safe).alias(f"st_dist_{time_frame}")
    )

    return df_out


def pt_macd(df, time_frame, fast=12, slow=26, signal=9):
    if isinstance(fast, str):
        num_str = re.sub(r"\D", "", fast)
        fast = int(num_str) if num_str else 12
    else:
        fast = int(fast)
    if isinstance(slow, str):
        num_str = re.sub(r"\D", "", slow)
        slow = int(num_str) if num_str else 26
    else:
        slow = int(slow)
    if isinstance(signal, str):
        num_str = re.sub(r"\D", "", signal)
        signal = int(num_str) if num_str else 9
    else:
        signal = int(signal)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_macd = f"macd_{time_frame}"
    c_signal = f"macd_signal_{time_frame}"
    c_hist = f"macd_hist_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_macd(d, "1m", fast, slow, signal)
        )

    if time_frame == "1m":
        df_pd = df.select(["close"]).to_pandas()
        macd_ind = ta.trend.MACD(close=df_pd["close"], window_fast=fast, window_slow=slow, window_sign=signal)
        df_out = df.with_columns([
            pl.Series(c_macd, macd_ind.macd()),
            pl.Series(c_signal, macd_ind.macd_signal()),
            pl.Series(c_hist, macd_ind.macd_diff())
        ])
    prev_macd = pl.col(c_macd).shift(1)
    prev_signal = pl.col(c_signal).shift(1)

    df_out = df_out.with_columns([
        (pl.col(c_macd).fill_nan(None) > pl.col(c_signal).fill_nan(None)).fill_null(False).alias(f"macd_bullish_{time_frame}"),
        ((pl.col(c_macd).fill_nan(None) > pl.col(c_signal).fill_nan(None)).fill_null(False) \
            & (prev_macd.fill_nan(None) <= prev_signal.fill_nan(None)).fill_null(False)) \
            .alias(f"macd_cross_up_{time_frame}"),
        ((pl.col(c_macd).fill_nan(None) < pl.col(c_signal).fill_nan(None)).fill_null(False) \
            & (prev_macd.fill_nan(None) >= prev_signal.fill_nan(None)).fill_null(False)) \
            .alias(f"macd_cross_down_{time_frame}")
    ])

    _close_safe = pl.when(pl.col("close") != 0).then(pl.col("close")).otherwise(None)
    df_out = df_out.with_columns(
        (pl.col(c_hist) / _close_safe).alias(f"macd_hist_pct_{time_frame}")
    )

    return df_out


def pt_psar(df, time_frame, af_start=0.02, af_step=0.02, af_max=0.2):
    af_start = float(af_start)
    af_step = float(af_step)
    af_max = float(af_max)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_psar = f"psar_{time_frame}"
    c_bull = f"psar_bull_{time_frame}"
    c_flip_up = f"psar_flip_up_{time_frame}"
    c_flip_down = f"psar_flip_down_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_psar(d, "1m", af_start, af_step, af_max)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        psar_ind = ta.trend.PSARIndicator(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], step=af_step, max_step=af_max)
        df_out = df.with_columns([
            pl.Series(c_psar, psar_ind.psar()),
            pl.Series(c_bull, psar_ind.psar_up().notna())
        ])
    prev_bull = pl.col(c_bull).shift(1)

    df_out = df_out.with_columns([
        ((pl.col(c_bull)) & (~prev_bull).fill_null(False)).alias(c_flip_up),
        ((~pl.col(c_bull)) & prev_bull.fill_null(False)).alias(c_flip_down)
    ])

    _ps = pl.col(c_psar)
    _ps_safe = pl.when(_ps != 0).then(_ps).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - _ps) / _ps_safe).alias(f"psar_dist_{time_frame}"))

    return df_out


def pt_aroon(df, time_frame, window=25):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 25
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_up = f"aroon_up_{time_frame}"
    c_down = f"aroon_down_{time_frame}"
    c_osc = f"aroon_osc_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low"]).to_pandas()
        aroon = ta.trend.AroonIndicator(high=df_pd["high"], low=df_pd["low"], window=window)
        df_out = df.with_columns([
            pl.Series(c_up, aroon.aroon_up()),
            pl.Series(c_down, aroon.aroon_down())
        ])
    else:
        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=polars_time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low"]).to_pandas()
        aroon = ta.trend.AroonIndicator(high=htf_pd["high"], low=htf_pd["low"], window=window)

        htf = htf.with_columns([
            pl.Series("up", aroon.aroon_up()),
            pl.Series("down", aroon.aroon_down())
        ])

        htf_to_join = htf.select(["timestamp", "up", "down"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns([
            pl.col("up").alias(c_up),
            pl.col("down").alias(c_down)
        ]).drop(["up", "down"])

    df_out = df_out.with_columns([
        (pl.col(c_up) - pl.col(c_down)).alias(c_osc)
    ])

    df_out = df_out.with_columns([
        ((pl.col(c_up).fill_nan(None) > 70.0).fill_null(False) & (pl.col(c_down).fill_nan(None) < 30.0).fill_null(False))
            .alias(f"aroon_bull_{time_frame}"),
        ((pl.col(c_down).fill_nan(None) > 70.0).fill_null(False) & (pl.col(c_up).fill_nan(None) < 30.0).fill_null(False))
            .alias(f"aroon_bear_{time_frame}")
    ])

    return df_out


def pt_vortex(df, time_frame, window=14):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_vip = f"vi_plus_{time_frame}"
    c_vim = f"vi_minus_{time_frame}"
    c_bull = f"vi_bull_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        vortex = ta.trend.VortexIndicator(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], window=window)
        df_out = df.with_columns([
            pl.Series(c_vip, vortex.vortex_indicator_pos()),
            pl.Series(c_vim, vortex.vortex_indicator_neg())
        ])
    else:
        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=polars_time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low", "close"]).to_pandas()
        vortex = ta.trend.VortexIndicator(high=htf_pd["high"], low=htf_pd["low"], close=htf_pd["close"], window=window)

        htf = htf.with_columns([
            pl.Series("vip", vortex.vortex_indicator_pos()),
            pl.Series("vim", vortex.vortex_indicator_neg())
        ])

        htf_to_join = htf.select(["timestamp", "vip", "vim"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns([
            pl.col("vip").alias(c_vip),
            pl.col("vim").alias(c_vim)
        ]).drop(["vip", "vim"])

    df_out = df_out.with_columns(
        (pl.col(c_vip).fill_nan(None) > pl.col(c_vim).fill_nan(None)).fill_null(False).alias(c_bull)
    )

    return df_out


def pt_hma(df, time_frame, window=9):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 9
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_hma = f"hma_{window}_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _hma_calc_pd(close, win):
        half_win = int(win / 2)
        sqrt_win = int(math.sqrt(win))
        wma_half = ta.trend.wma_indicator(close, half_win)
        wma_full = ta.trend.wma_indicator(close, win)
        raw_hma = 2 * wma_half - wma_full
        hma = ta.trend.wma_indicator(raw_hma, sqrt_win)
        return hma


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_hma(d, "1m", window)
        )

    if time_frame == "1m":
        df_pd = df.select(["close"]).to_pandas()
        hma = _hma_calc_pd(df_pd["close"], window)
        df_out = df.with_columns(pl.Series(c_hma, hma))
    df_out = df_out.with_columns(
        (pl.col("close").fill_nan(None) > pl.col(c_hma).fill_nan(None)).fill_null(False).alias(f"hma_bull_{time_frame}")
    )
    _ma_safe = pl.when(pl.col(c_hma) != 0).then(pl.col(c_hma)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - pl.col(c_hma)) / _ma_safe).alias(f"hma_dist_{time_frame}"))
    return df_out


def pt_kama(df, time_frame, window=10, fast=2, slow=30):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 10
    else:
        window = int(window)
    if isinstance(fast, str):
        num_str = re.sub(r"\D", "", fast)
        fast = int(num_str) if num_str else 2
    else:
        fast = int(fast)
    if isinstance(slow, str):
        num_str = re.sub(r"\D", "", slow)
        slow = int(num_str) if num_str else 30
    else:
        slow = int(slow)

    polars_time_frame = time_frame.lower()
    c_kama = f"kama_{window}_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_kama(d, "1m", window, fast, slow)
        )

    df_pd = df.select(["close"]).to_pandas()
    kama_val = ta.momentum.kama(close=df_pd["close"], window=window, pow1=fast, pow2=slow)
    df_out = df.with_columns(pl.Series(c_kama, kama_val))

    df_out = df_out.with_columns(
        (pl.col("close").fill_nan(None) > pl.col(c_kama).fill_nan(None)).fill_null(False).alias(f"kama_bull_{time_frame}")
    )
    _ma_safe = pl.when(pl.col(c_kama) != 0).then(pl.col(c_kama)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - pl.col(c_kama)) / _ma_safe).alias(f"kama_dist_{time_frame}"))
    return df_out


def pt_alma(df, time_frame, window=9, offset=0.85, sigma=6.0):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 9
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_alma = f"alma_{window}_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _alma_calc_pd(close_arr):
        n = len(close_arr)
        m = offset * (window - 1)
        s = window / sigma
        weights = np.exp(-((np.arange(window) - m) ** 2) / (2 * s * s))
        sum_weights = weights.sum()

        alma = np.full(n, np.nan, dtype=float)
        if n < window:
            return alma

        for i in range(window - 1, n):
            window_vals = close_arr[i - window + 1:i + 1]
            alma[i] = np.dot(window_vals, weights) / sum_weights

        return alma


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_alma(d, "1m", window, offset, sigma)
        )

    alma_arr = _alma_calc_pd(df["close"].to_numpy())
    df_out = df.with_columns(pl.Series(c_alma, alma_arr))

    df_out = df_out.with_columns(
        (pl.col("close").fill_nan(None) > pl.col(c_alma).fill_nan(None)).fill_null(False).alias(f"alma_bull_{time_frame}")
    )
    _ma_safe = pl.when(pl.col(c_alma) != 0).then(pl.col(c_alma)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - pl.col(c_alma)) / _ma_safe).alias(f"alma_dist_{time_frame}"))
    return df_out


def pt_vwma(df, time_frame, window=20):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_vwma = f"vwma_{window}_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _vwma_calc_pd(close, vol):
        pv = close * vol
        pv_sum = pv.rolling(window).sum()
        vol_sum = vol.rolling(window).sum()
        return pv_sum / (vol_sum + 1e-9)


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_vwma(d, "1m", window)
        )

    if window <= 1:
        df_out = df.with_columns(pl.col("close").alias(c_vwma))
    else:
        df_pd = df.select(["close", "volume"]).to_pandas()
        vwma = _vwma_calc_pd(df_pd["close"], df_pd["volume"])
        df_out = df.with_columns(pl.Series(c_vwma, vwma))

    df_out = df_out.with_columns(
        (pl.col("close").fill_nan(None) > pl.col(c_vwma).fill_nan(None)).fill_null(False).alias(f"vwma_bull_{time_frame}")
    )
    _ma_safe = pl.when(pl.col(c_vwma) != 0).then(pl.col(c_vwma)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - pl.col(c_vwma)) / _ma_safe).alias(f"vwma_dist_{time_frame}"))
    return df_out
