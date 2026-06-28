"""BIẾN ĐỘNG (Volatility) - Phiên bản Polars + ta library (Bản cấp thấp)
👉 Giá chạy mạnh hay yếu?
- ATR
- Bollinger Bands
- Keltner Channel
- Donchian Channel
📌 Dùng cho SL / TP / leverage
"""

import polars as pl
import pandas as pd
import numpy as np
import ta
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


def pt_atr(df, time_frame, window=14, mean_window=100):
    """Phân tích ATR: Mức độ biến động thị trường (Bản cấp thấp)."""
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    window = parse_window(window, 14)
    mean_window = parse_window(mean_window, 100)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    col_atr = f"atr_{time_frame}"
    col_atr_mean = f"atr_mean_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_atr(d, "1m", window, mean_window)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        atr_series = ta.volatility.average_true_range(
            high=df_pd["high"],
            low=df_pd["low"],
            close=df_pd["close"],
            window=window
        )
        df = df.with_columns(pl.Series(col_atr, atr_series))
        df = df.with_columns(
            pl.col(col_atr).rolling_mean(window_size=mean_window).alias(col_atr_mean)
        )

    df = df.with_columns([
        pl.when(pl.col(col_atr) > pl.col(col_atr_mean))
        .then(pl.lit("BIEN_DONG_CAO"))
        .otherwise(pl.lit("BIEN_DONG_THAP"))
        .alias(f"atr_status_{time_frame}"),

        pl.when(pl.col(col_atr) > pl.col(col_atr_mean))
        .then(pl.lit("CAO"))
        .otherwise(pl.lit("THAP"))
        .alias(f"atr_muc_do_{time_frame}")
    ])

    _close_safe = pl.when(pl.col("close") > 0).then(pl.col("close")).otherwise(None)
    df = df.with_columns(
        (pl.col(col_atr) / _close_safe).alias(f"atr_pct_{time_frame}")
    )

    return df


def pt_bollinger_squeeze(df, time_frame, window=20, window_dev=2):
    """Phân tích Bollinger Bands & Squeeze dạng Vectorized (Bản cấp thấp)."""
    def parse_number(val, default):
        if isinstance(val, str):
            num_str = re.sub(r"[^\d.]", "", val)
            return float(num_str) if "." in num_str else int(num_str) if num_str else default
        return val

    window = int(parse_number(window, 20))
    window_dev = float(parse_number(window_dev, 2))
    bw_mean_window = 50

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_upper = f"bb_upper_{time_frame}"
    c_lower = f"bb_lower_{time_frame}"
    c_mid = f"bb_mid_{time_frame}"
    c_bw = f"bb_width_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_bollinger_squeeze(d, "1m", window, window_dev)
        )

    if time_frame == "1m":
        df_pd = df.select(["close"]).to_pandas()
        bb = ta.volatility.BollingerBands(close=df_pd["close"], window=window, window_dev=window_dev)
        df = df.with_columns([
            pl.Series(c_mid, bb.bollinger_mavg()),
            pl.Series(c_upper, bb.bollinger_hband()),
            pl.Series(c_lower, bb.bollinger_lband()),
            pl.Series(c_bw, bb.bollinger_wband()),
        ])
        df = df.with_columns([
            pl.col(c_bw).rolling_mean(window_size=bw_mean_window).alias("bandwidth_mean")
        ])

    df = df.with_columns([
        pl.when(pl.col(c_bw) < (pl.col("bandwidth_mean") * 0.8))
        .then(pl.lit("BOP"))
        .otherwise(pl.lit("MO_RONG"))
        .alias(f"bb_status_{time_frame}"),

        pl.when(pl.col(c_bw) < (pl.col("bandwidth_mean") * 0.6))
        .then(pl.lit("CHAT"))
        .otherwise(
            pl.when(pl.col(c_bw) < (pl.col("bandwidth_mean") * 0.8))
            .then(pl.lit("THUONG"))
            .otherwise(pl.lit("KHONG"))
        )
        .alias(f"bb_muc_do_{time_frame}")
    ]).drop("bandwidth_mean")


    _bb_range = pl.col(c_upper) - pl.col(c_lower)
    _bb_range = pl.when(_bb_range != 0).then(_bb_range).otherwise(None)
    df = df.with_columns(
        ((pl.col("close") - pl.col(c_lower)) / _bb_range).alias(f"bb_percent_b_{time_frame}")
    )

    return df


def pt_keltner_channel(df, time_frame, window=20, atr_window=10, multiplier=2.0):
    """Phân tích Keltner Channel dạng Vectorized (Bản cấp thấp)."""
    def parse_number(val, default):
        if isinstance(val, str):
            num_str = re.sub(r"[^\d.]", "", val)
            return float(num_str) if "." in num_str else int(num_str) if num_str else default
        return val

    window = int(parse_number(window, 20))
    atr_window = int(parse_number(atr_window, 10))
    multiplier = float(parse_number(multiplier, 2.0))

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_upper = f"kc_upper_{time_frame}"
    c_lower = f"kc_lower_{time_frame}"
    c_mid = f"kc_mid_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_keltner_channel(d, "1m", window, atr_window, multiplier)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        kc = ta.volatility.KeltnerChannel(
            high=df_pd["high"],
            low=df_pd["low"],
            close=df_pd["close"],
            window=window,
            window_atr=atr_window,
            multiplier=multiplier,
            original_version=False
        )
        df = df.with_columns([
            pl.Series(c_mid, kc.keltner_channel_mband()),
            pl.Series(c_upper, kc.keltner_channel_hband()),
            pl.Series(c_lower, kc.keltner_channel_lband()),
        ])

    df = df.with_columns([
        (pl.col("close") > pl.col(c_upper)).alias(f"kc_break_upper_{time_frame}"),
        (pl.col("close") < pl.col(c_lower)).alias(f"kc_break_lower_{time_frame}"),
        (pl.col("close") > pl.col(c_mid)).alias(f"kc_above_mid_{time_frame}")
    ])


    _kc_rng = pl.col(c_upper) - pl.col(c_lower)
    _kc_rng = pl.when(_kc_rng != 0).then(_kc_rng).otherwise(None)
    df = df.with_columns(((pl.col("close") - pl.col(c_lower)) / _kc_rng).alias(f"kc_percent_{time_frame}"))

    return df


def pt_donchian_channel(df, time_frame, window=20):
    """Phân tích Donchian Channel dạng Vectorized (Bản cấp thấp)."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_upper = f"dc_upper_{time_frame}"
    c_lower = f"dc_lower_{time_frame}"
    c_mid = f"dc_mid_{time_frame}"
    c_width = f"dc_width_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        dc = ta.volatility.DonchianChannel(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], window=window)
        df = df.with_columns([
            pl.Series(c_upper, dc.donchian_channel_hband()),
            pl.Series(c_lower, dc.donchian_channel_lband()),
        ]).with_columns([
            ((pl.col(c_upper) + pl.col(c_lower)) / 2).alias(c_mid)
        ]).with_columns([
            ((pl.col(c_upper) - pl.col(c_lower)) / pl.col(c_mid)).alias(c_width)
        ])
    else:

        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
            ])
            .drop_nulls()
            .sort("timestamp")
        )


        htf_pd = htf.select(["high", "low", "close"]).to_pandas()
        dc = ta.volatility.DonchianChannel(high=htf_pd["high"], low=htf_pd["low"], close=htf_pd["close"], window=window)
        htf = htf.with_columns([
            pl.Series("upper_closed", dc.donchian_channel_hband()),
            pl.Series("lower_closed", dc.donchian_channel_lband()),
        ]).with_columns([
            ((pl.col("upper_closed") + pl.col("lower_closed")) / 2).alias("mid_closed")
        ]).with_columns([
            ((pl.col("upper_closed") - pl.col("lower_closed")) / pl.col("mid_closed")).alias("width_closed")
        ])


        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(time_frame)
        )


        htf_to_join = htf.select([
            "timestamp",
            pl.col("upper_closed").alias(c_upper),
            pl.col("lower_closed").alias(c_lower),
            pl.col("mid_closed").alias(c_mid),
            pl.col("width_closed").alias(c_width)
        ])
        df = df.join_asof(htf_to_join, on="timestamp", strategy="backward")


    df = df.with_columns([
        pl.when(pl.col("close") > pl.col(c_mid))
        .then(pl.lit("UP"))
        .otherwise(pl.lit("DOWN"))
        .alias(f"dc_trend_{time_frame}"),

        (pl.col("close") > pl.col(c_mid)).alias(f"dc_bullish_zone_{time_frame}")
    ])

    return df


def pt_historical_volatility(df, time_frame, window=20):
    """Phân tích Historical Volatility dạng Vectorized (Bản cấp thấp)."""
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    def parse_timeframe_to_minutes(tf):
        num_str = re.sub(r"\D", "", tf)
        num = int(num_str) if num_str else 1
        if "h" in tf.lower():
            return num * 60
        elif "d" in tf.lower():
            return num * 1440
        elif "w" in tf.lower():
            return num * 10080
        return num

    window = parse_window(window, 20)
    tf_minutes = parse_timeframe_to_minutes(time_frame)
    annual_factor = math.sqrt(525600 / tf_minutes)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_hv = f"hv_{time_frame}"
    c_hv_high = f"hv_high_{time_frame}"
    c_hv_status = f"hv_status_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["close"]).to_pandas()
        log_ret = np.log(df_pd["close"] / df_pd["close"].shift(1))
        hv = log_ret.rolling(window).std() * annual_factor
        df = df.with_columns(pl.Series(c_hv, hv))
    else:

        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("close").last().alias("close"),
            ])
            .drop_nulls()
            .sort("timestamp")
        )


        htf_pd = htf.select(["close"]).to_pandas()
        log_ret = np.log(htf_pd["close"] / htf_pd["close"].shift(1))
        hv_closed = log_ret.rolling(window).std() * annual_factor
        htf = htf.with_columns(pl.Series("hv_closed", hv_closed))


        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(time_frame)
        )


        htf_to_join = htf.select([
            "timestamp",
            pl.col("hv_closed").alias(c_hv)
        ])
        df = df.join_asof(htf_to_join, on="timestamp", strategy="backward")


    df = df.with_columns([
        pl.col(c_hv).rolling_mean(window_size=50).alias("hv_mean")
    ]).with_columns([
        (pl.col(c_hv) > pl.col("hv_mean")).alias(c_hv_high)
    ]).with_columns([
        pl.when(pl.col(c_hv_high))
        .then(pl.lit("CAO"))
        .otherwise(pl.lit("THAP"))
        .alias(c_hv_status)
    ]).drop("hv_mean")

    return df


def pt_chaikin_volatility(df, time_frame, window=10):
    """Phân tích Chaikin Volatility dạng Vectorized (Bản cấp thấp)."""
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    window = parse_window(window, 10)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_cv = f"cv_{time_frame}"
    c_cv_expanding = f"cv_expanding_{time_frame}"
    c_cv_status = f"cv_status_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low"]).to_pandas()
        hl = df_pd["high"] - df_pd["low"]
        hl_ema = hl.ewm(span=window, adjust=False).mean()
        cv = (hl_ema - hl_ema.shift(window)) / hl_ema.shift(window) * 100
        df = df.with_columns(pl.Series(c_cv, cv))
    else:

        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
            ])
            .drop_nulls()
            .sort("timestamp")
        )


        htf_pd = htf.select(["high", "low"]).to_pandas()
        hl = htf_pd["high"] - htf_pd["low"]
        hl_ema = hl.ewm(span=window, adjust=False).mean()
        cv_closed = (hl_ema - hl_ema.shift(window)) / hl_ema.shift(window) * 100
        htf = htf.with_columns(pl.Series("cv_closed", cv_closed))


        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(time_frame)
        )


        htf_to_join = htf.select([
            "timestamp",
            pl.col("cv_closed").alias(c_cv)
        ])
        df = df.join_asof(htf_to_join, on="timestamp", strategy="backward")


    df = df.with_columns([
        (pl.col(c_cv) > 0).alias(c_cv_expanding)
    ]).with_columns([
        pl.when(pl.col(c_cv_expanding))
        .then(pl.lit("TANG"))
        .otherwise(pl.lit("GIAM"))
        .alias(c_cv_status)
    ])

    return df


def pt_atr_bands(df, time_frame, multiplier=2.5, window=20):
    """Phân tích ATR Bands dạng Vectorized (Bản cấp thấp)."""
    def parse_number(val, default):
        if isinstance(val, str):
            num_str = re.sub(r"[^\d.]", "", val)
            return float(num_str) if "." in num_str else int(num_str) if num_str else default
        return val

    window = int(parse_number(window, 20))
    multiplier = float(parse_number(multiplier, 2.5))

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_upper = f"atrb_upper_{time_frame}"
    c_lower = f"atrb_lower_{time_frame}"
    c_mid = f"atrb_mid_{time_frame}"
    c_above = f"atrb_above_{time_frame}"
    c_below = f"atrb_below_{time_frame}"


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_atr_bands(d, "1m", multiplier, window)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        atr = ta.volatility.average_true_range(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], window=window)
        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=window).alias(c_mid),
            pl.Series("atr", atr)
        ]).with_columns([
            (pl.col(c_mid) + multiplier * pl.col("atr")).alias(c_upper),
            (pl.col(c_mid) - multiplier * pl.col("atr")).alias(c_lower),
        ]).drop("atr")

    df = df.with_columns([
        (pl.col("close") > pl.col(c_upper)).alias(c_above),
        (pl.col("close") < pl.col(c_lower)).alias(c_below)
    ])


    _ab_rng = pl.col(c_upper) - pl.col(c_lower)
    _ab_rng = pl.when(_ab_rng != 0).then(_ab_rng).otherwise(None)
    df = df.with_columns(((pl.col("close") - pl.col(c_lower)) / _ab_rng).alias(f"atrb_percent_{time_frame}"))

    return df


def pt_chandelier_exit(df, time_frame, window=22, multiplier=3.0):
    """Phân tích Chandelier Exit dạng Vectorized (Bản cấp thấp)."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 22
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_long = f"chan_long_{time_frame}"
    c_short = f"chan_short_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _chan_calc_pd(high, low, close):
        atr = ta.volatility.average_true_range(high=high, low=low, close=close, window=window)
        chan_long = high.rolling(window).max() - atr * multiplier
        chan_short = low.rolling(window).min() + atr * multiplier
        return chan_long, chan_short


    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_chandelier_exit(d, "1m", window, multiplier)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        chan_l, chan_s = _chan_calc_pd(df_pd["high"], df_pd["low"], df_pd["close"])
        df_out = df.with_columns([
            pl.Series(c_long, chan_l),
            pl.Series(c_short, chan_s)
        ])

    _cl = pl.col(c_long)
    _close_safe = pl.when(pl.col("close") != 0).then(pl.col("close")).otherwise(None)
    df_out = df_out.with_columns(((pl.col("close") - _cl) / _close_safe).alias(f"chan_dist_{time_frame}"))

    return df_out


def pt_choppiness_index(df, time_frame, window=14):
    """Phân tích Choppiness Index dạng Vectorized (Bản cấp thấp)."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_chop = f"choppiness_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _chop_calc_pd(high, low, close):
        prev_close = close.shift(1)
        tr = np.maximum(
            high - low,
            np.maximum(
                (high - prev_close).abs(),
                (low - prev_close).abs()
            )
        )
        tr_sum = tr.rolling(window).sum()
        max_high = high.rolling(window).max()
        min_low = low.rolling(window).min()
        chop = 100 * (np.log10(tr_sum / (max_high - min_low + 1e-9))) / math.log10(window)
        return chop

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close"]).to_pandas()
        chop = _chop_calc_pd(df_pd["high"], df_pd["low"], df_pd["close"])
        df_out = df.with_columns(pl.Series(c_chop, chop))
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


        htf_pd = htf.select(["high", "low", "close"]).to_pandas()
        chop = _chop_calc_pd(htf_pd["high"], htf_pd["low"], htf_pd["close"])
        htf_chop = htf.with_columns(pl.Series("chop", chop))


        htf_chop = htf_chop.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )


        htf_to_join = htf_chop.select(["timestamp", "chop"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns(pl.col("chop").alias(c_chop)).drop("chop")

    return df_out
