"""CẤU TRÚC GIÁ (Market Structure / Price Action) - Phiên bản Polars
👉 Thị trường đang ở pha nào?
- Higher High / Higher Low
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Support / Resistance
- Supply / Demand
"""

import polars as pl
import numpy as np
import re


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


def pt_breakout(df, time_frame, window=20):
    """
    Phân tích Breakout (Phá vỡ Đỉnh/Đáy) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF).
    """
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_high = f"breakout_High_{time_frame}"
    c_low = f"breakout_Low_{time_frame}"
    c_status = f"breakout_{time_frame}"

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_breakout(d, "1m", window)
        )

    if time_frame == "1m":
        high_max = pl.col("high").rolling_max(window_size=window)
        low_min = pl.col("low").rolling_min(window_size=window)
        
        df = df.with_columns([
            high_max.alias(c_high),
            low_min.alias(c_low)
        ])
    df = df.with_columns(
        pl.when(pl.col("close") > pl.col(c_high))
        .then(pl.lit("BREAK_OUT"))
        .otherwise(
            pl.when(pl.col("close") < pl.col(c_low))
            .then(pl.lit("BREAK_DOWN"))
            .otherwise(pl.lit("None"))
        )
        .alias(c_status)
    )

    _bk_rng = pl.col(c_high) - pl.col(c_low)
    _bk_rng = pl.when(_bk_rng != 0).then(_bk_rng).otherwise(None)
    df = df.with_columns(((pl.col("close") - pl.col(c_low)) / _bk_rng).alias(f"breakout_percent_{time_frame}"))

    return df


def pt_fractals(df, time_frame, window=2):
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 2
    else:
        window = int(window)

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_up_frac = f"frac_res_{time_frame}"
    c_down_frac = f"frac_sup_{time_frame}"

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_fractals(d, "1m", window)
        )

    if time_frame == "1m":
        high_target = pl.col("high").shift(window)
        low_target = pl.col("low").shift(window)

        up_cond = pl.lit(True)
        down_cond = pl.lit(True)
        for k in range(1, window + 1):
            up_cond = up_cond & (pl.col("high").shift(window + k) < high_target)
            down_cond = down_cond & (pl.col("low").shift(window + k) > low_target)
        for k in range(0, window):
            up_cond = up_cond & (pl.col("high").shift(k) < high_target)
            down_cond = down_cond & (pl.col("low").shift(k) > low_target)

        df = df.with_columns([
            pl.when(up_cond).then(high_target).otherwise(None).forward_fill().alias(c_up_frac),
            pl.when(down_cond).then(low_target).otherwise(None).forward_fill().alias(c_down_frac)
        ])
    df = df.with_columns([
        ((pl.col("close") > pl.col(c_up_frac)).fill_null(False)).alias(f"frac_breakout_up_{time_frame}"),
        ((pl.col("close") < pl.col(c_down_frac)).fill_null(False)).alias(f"frac_breakout_down_{time_frame}"),
        ((pl.col("close") - pl.col(c_down_frac)) / pl.col("close") * 100).alias(f"frac_dist_to_sup_{time_frame}")
    ])

    return df


def pt_pivot_points(df, time_frame, left_bars=5, right_bars=5):
    """
    Phân tích Pivot Points High/Low (Swing Points) dạng Vectorized Đa Khung Thời Gian (MTF).
    """
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    left_bars = parse_window(left_bars, 5)
    right_bars = parse_window(right_bars, 5)
    window = left_bars + right_bars + 1

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_pivot_high = f"pivot_high_{time_frame}"
    c_pivot_low = f"pivot_low_{time_frame}"

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, time_frame.lower(), time_frame, lambda d: pt_pivot_points(d, "1m", left_bars, right_bars)
        )

    if time_frame == "1m":
        target_high = pl.col("high").shift(right_bars)
        target_low = pl.col("low").shift(right_bars)

        rolling_max = pl.col("high").rolling_max(window_size=window)
        rolling_min = pl.col("low").rolling_min(window_size=window)

        is_pivot_high = target_high == rolling_max
        is_pivot_low = target_low == rolling_min

        df = df.with_columns([
            pl.when(is_pivot_high).then(target_high).otherwise(None).forward_fill().alias(c_pivot_high),
            pl.when(is_pivot_low).then(target_low).otherwise(None).forward_fill().alias(c_pivot_low)
        ])
    df = df.with_columns([
        ((pl.col("high") > pl.col(c_pivot_high)).fill_null(False)).alias(f"pivot_sweep_high_{time_frame}"),
        ((pl.col("low") < pl.col(c_pivot_low)).fill_null(False)).alias(f"pivot_sweep_low_{time_frame}"),
        ((pl.col("close") > pl.col(c_pivot_high)).fill_null(False)).alias(f"pivot_break_up_{time_frame}"),
        ((pl.col("close") < pl.col(c_pivot_low)).fill_null(False)).alias(f"pivot_break_down_{time_frame}")
    ])

    _pv_rng = pl.col(c_pivot_high) - pl.col(c_pivot_low)
    _pv_rng = pl.when(_pv_rng != 0).then(_pv_rng).otherwise(None)
    df = df.with_columns(((pl.col("close") - pl.col(c_pivot_low)) / _pv_rng).alias(f"pivot_percent_{time_frame}"))

    return df


def pt_fvg(df, time_frame):
    """
    Phân tích Fair Value Gap (FVG / Imbalance) dạng Vectorized Đa Khung Thời Gian (MTF).
    """
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_fvg_top = f"fvg_top_{time_frame}"
    c_fvg_bot = f"fvg_bottom_{time_frame}"
    c_fvg_type = f"fvg_type_{time_frame}"

    if time_frame == "1m":
        bull_fvg = pl.col("low") > pl.col("high").shift(2)
        bear_fvg = pl.col("high") < pl.col("low").shift(2)

        fvg_top_expr = (
            pl.when(bull_fvg)
            .then(pl.col("low"))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.col("low").shift(2))
                .otherwise(None)
            )
            .forward_fill()
        )
        fvg_bot_expr = (
            pl.when(bull_fvg)
            .then(pl.col("high").shift(2))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.col("high"))
                .otherwise(None)
            )
            .forward_fill()
        )
        fvg_type_expr = (
            pl.when(bull_fvg)
            .then(pl.lit(1.0))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.lit(-1.0))
                .otherwise(None)
            )
            .forward_fill()
        )

        df = df.with_columns([
            fvg_top_expr.alias(c_fvg_top),
            fvg_bot_expr.alias(c_fvg_bot),
            fvg_type_expr.alias(c_fvg_type)
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
            ])
            .drop_nulls()
            .sort("timestamp")
        )

                                      
        bull_fvg = pl.col("low") > pl.col("high").shift(2)
        bear_fvg = pl.col("high") < pl.col("low").shift(2)

        htf_fvg_top = (
            pl.when(bull_fvg)
            .then(pl.col("low"))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.col("low").shift(2))
                .otherwise(None)
            )
            .forward_fill()
        )
        htf_fvg_bot = (
            pl.when(bull_fvg)
            .then(pl.col("high").shift(2))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.col("high"))
                .otherwise(None)
            )
            .forward_fill()
        )
        htf_fvg_type = (
            pl.when(bull_fvg)
            .then(pl.lit(1.0))
            .otherwise(
                pl.when(bear_fvg)
                .then(pl.lit(-1.0))
                .otherwise(None)
            )
            .forward_fill()
        )

        htf = htf.with_columns([
            htf_fvg_top.alias("f_top"),
            htf_fvg_bot.alias("f_bot"),
            htf_fvg_type.alias("f_type")
        ])

                                                         
        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(time_frame)
        )

                            
        htf_to_join = htf.select([
            "timestamp",
            pl.col("f_top").alias("f_top_ffill"),
            pl.col("f_bot").alias("f_bot_ffill"),
            pl.col("f_type").alias("f_type_ffill")
        ])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        
        df = df_joined.with_columns([
            pl.col("f_top_ffill").forward_fill().alias(c_fvg_top),
            pl.col("f_bot_ffill").forward_fill().alias(c_fvg_bot),
            pl.col("f_type_ffill").forward_fill().alias(c_fvg_type)
        ]).drop(["f_top_ffill", "f_bot_ffill", "f_type_ffill"])

    df = df.with_columns([
        (((pl.col("close") <= pl.col(c_fvg_top)) & (pl.col("close") >= pl.col(c_fvg_bot))).fill_null(False)).alias(f"fvg_in_zone_{time_frame}")
    ]).with_columns([
        (
            pl.when(pl.col(c_fvg_type) == 1.0)
            .then(pl.col("close") < pl.col(c_fvg_bot))
            .otherwise(
                pl.when(pl.col(c_fvg_type) == -1.0)
                .then(pl.col("close") > pl.col(c_fvg_top))
                .otherwise(False)
            )
            .fill_null(False)
        )
        .alias(f"fvg_mitigated_{time_frame}")
    ])

    return df


def _heikin_ashi_arrays(open_arr, high_arr, low_arr, close_arr):
    n = len(close_arr)
    ha_close = (open_arr + high_arr + low_arr + close_arr) / 4.0
    ha_open = np.full(n, np.nan, dtype=float)
    if n == 0:
        return ha_open, ha_close

    ha_open[0] = (open_arr[0] + close_arr[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    return ha_open, ha_close


def pt_heikin_ashi(df, time_frame):
    """
    Phân tích Heikin Ashi dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF).
    """
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_ha_open = f"ha_open_{time_frame}"
    c_ha_close = f"ha_close_{time_frame}"
    c_ha_bull = f"ha_bull_{time_frame}"
    c_ha_strong_bull = f"ha_strong_bull_{time_frame}"
    c_ha_strong_bear = f"ha_strong_bear_{time_frame}"
    c_ha_doji = f"ha_doji_{time_frame}"

    if time_frame == "1m":
        ha_open_arr, ha_close_arr = _heikin_ashi_arrays(
            df["open"].to_numpy(),
            df["high"].to_numpy(),
            df["low"].to_numpy(),
            df["close"].to_numpy()
        )
        
        df = df.with_columns([
            pl.Series(ha_open_arr).alias(c_ha_open),
            pl.Series(ha_close_arr).alias(c_ha_close)
        ])
        
        ha_high = pl.max_horizontal("high", c_ha_open, c_ha_close)
        ha_low = pl.min_horizontal("low", c_ha_open, c_ha_close)
    else:
                                     
        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
            ])
            .drop_nulls()
            .sort("timestamp")
        )

                                                       
        ha_open_closed, ha_close_closed = _heikin_ashi_arrays(
            htf["open"].to_numpy(),
            htf["high"].to_numpy(),
            htf["low"].to_numpy(),
            htf["close"].to_numpy()
        )

        htf = htf.with_columns([
            pl.Series("ha_open_closed", ha_open_closed),
            pl.Series("ha_close_closed", ha_close_closed),
            htf["high"].alias("ha_high_closed"),
            htf["low"].alias("ha_low_closed")
        ])

                                                         
        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(time_frame)
        )

                            
        htf_to_join = htf.select([
            "timestamp",
            pl.col("ha_open_closed").alias("ha_open_ffill"),
            pl.col("ha_close_closed").alias("ha_close_ffill"),
            pl.col("ha_high_closed").alias("ha_high_ffill"),
            pl.col("ha_low_closed").alias("ha_low_ffill")
        ])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        
        df = df_joined.with_columns([
            pl.col("ha_open_ffill").alias(c_ha_open),
            pl.col("ha_close_ffill").alias(c_ha_close)
        ])
        
        ha_high = pl.col("ha_high_ffill")
        ha_low = pl.col("ha_low_ffill")

    df = df.with_columns([
        (pl.col(c_ha_close) > pl.col(c_ha_open)).alias(c_ha_bull)
    ])

    df = df.with_columns([
        (pl.col(c_ha_bull) & (ha_low == pl.col(c_ha_open))).alias(c_ha_strong_bull),
        ((~pl.col(c_ha_bull)) & (ha_high == pl.col(c_ha_open))).alias(c_ha_strong_bear)
    ])

    hl_range = pl.when((ha_high - ha_low) == 0).then(None).otherwise(ha_high - ha_low)
    body = (pl.col(c_ha_close) - pl.col(c_ha_open)).abs()
    df = df.with_columns([
        ((body / hl_range) < 0.001).fill_null(False).alias(c_ha_doji)
    ])

    if time_frame != "1m":
        df = df.drop(["ha_high_ffill", "ha_low_ffill", "ha_open_ffill", "ha_close_ffill"])

    _ha_open = pl.col(f"ha_open_{time_frame}")
    _hao_safe = pl.when(_ha_open != 0).then(_ha_open).otherwise(None)
    df = df.with_columns(((pl.col(f"ha_close_{time_frame}") - _ha_open) / _hao_safe).alias(f"ha_body_{time_frame}"))

    return df
