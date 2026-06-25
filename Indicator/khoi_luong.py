"""KHỐI LƯỢNG (Volume / Participation) - Phiên bản Polars + ta library (Bản cấp thấp)
👉 Có tiền thật vào không?
- Volume
- Volume MA
- OBV
- VWAP
- Volume Profile
- CMF
- AD Line
- MFI Volume
- Ease of Movement
- Price Volume Trend (PVT)
- Chaikin Oscillator
📌 Dùng để xác nhận tín hiệu
"""

import polars as pl
import pandas as pd
import numpy as np
import ta
import ta.volume
import ta.trend
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


def pt_volume(df, time_frame, window=20, volume_luy_ke=True):
    """Phân tích Volume dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window_val = int(num_str) if num_str else 20
    else:
        window_val = int(window)

    if window_val < 2:
        window_val = 20

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_vol_mean = f"vol_mean_{time_frame}"
    c_vol_live = f"vol_live_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["volume"]).to_pandas()
        vol_mean = df_pd["volume"].rolling(window_val, min_periods=1).mean()
        df_out = df.with_columns([
            pl.Series(c_vol_mean, vol_mean),
            pl.col("volume").alias(c_vol_live)
        ])
    else:
        if volume_luy_ke:
            htf_vol = (
                df.group_by_dynamic(
                    "timestamp",
                    every=polars_time_frame,
                    closed="left",
                    label="left"
                )
                .agg(pl.col("volume").last().alias("volume"))
                .drop_nulls()
                .sort("timestamp")
            )
        else:
            htf_vol = (
                df.group_by_dynamic(
                    "timestamp",
                    every=polars_time_frame,
                    closed="left",
                    label="left"
                )
                .agg(pl.col("volume").sum().alias("volume"))
                .drop_nulls()
                .sort("timestamp")
            )

        htf_vol = htf_vol.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf_vol.select(["volume"]).to_pandas()
        vol_mean = htf_pd["volume"].rolling(window_val, min_periods=1).mean()

        htf_vol_features = htf_vol.with_columns([
            pl.Series("vol_mean", vol_mean),
            pl.col("volume").alias("vol_live")
        ])

        htf_to_join = htf_vol_features.select(["timestamp", "vol_mean", "vol_live"])
        df_out = df.join_asof(htf_to_join, on="timestamp", strategy="backward").rename({
            "vol_mean": c_vol_mean,
            "vol_live": c_vol_live
        })

                             
    df_out = df_out.with_columns([
        (pl.col(c_vol_live).fill_nan(None) > pl.col(c_vol_mean).fill_nan(None)).fill_null(False).alias(f"vol_tang_{time_frame}"),
        (pl.col(c_vol_live).fill_nan(None) > (pl.col(c_vol_mean).fill_nan(None) * 2)).fill_null(False).alias(f"vol_tang_manh_{time_frame}"),
        (pl.col(c_vol_live).fill_nan(None) < pl.col(c_vol_mean).fill_nan(None)).fill_null(False).alias(f"vol_giam_{time_frame}"),
        (pl.col(c_vol_live).fill_nan(None) < (pl.col(c_vol_mean).fill_nan(None) * 0.5)).fill_null(False).alias(f"vol_giam_manh_{time_frame}")
    ])

    _vm = pl.when(pl.col(c_vol_mean) > 0).then(pl.col(c_vol_mean)).otherwise(None)
    df_out = df_out.with_columns(
        (pl.col(c_vol_live) / _vm).alias(f"vol_ratio_{time_frame}")
    )

    return df_out


def pt_volume_ma(df, time_frame, fast_window=5, slow_window=20, volume_luy_ke=True):
    """Phân tích Volume MA Kép dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    def parse_window(w, default):
        if isinstance(w, str):
            num_str = re.sub(r"\D", "", w)
            return int(num_str) if num_str else default
        return int(w)

    fast_window = parse_window(fast_window, 5)
    slow_window = parse_window(slow_window, 20)

    if fast_window < 2:
        fast_window = 5
    if slow_window < 2:
        slow_window = 20

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_vol_live = f"vol_live_{time_frame}"
    c_vol_fast = f"vol_ma_fast_{time_frame}"
    c_vol_slow = f"vol_ma_slow_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["volume"]).to_pandas()
        fast_ma = df_pd["volume"].rolling(fast_window, min_periods=1).mean()
        slow_ma = df_pd["volume"].rolling(slow_window, min_periods=1).mean()
        df_out = df.with_columns([
            pl.col("volume").alias(c_vol_live),
            pl.Series(c_vol_fast, fast_ma),
            pl.Series(c_vol_slow, slow_ma)
        ])
    else:
        if volume_luy_ke:
            htf_vol_closed = (
                df.group_by_dynamic(
                    "timestamp",
                    every=polars_time_frame,
                    closed="left",
                    label="left"
                )
                .agg(pl.col("volume").last().alias("volume"))
                .drop_nulls()
                .sort("timestamp")
            )
        else:
            htf_vol_closed = (
                df.group_by_dynamic(
                    "timestamp",
                    every=polars_time_frame,
                    closed="left",
                    label="left"
                )
                .agg(pl.col("volume").sum().alias("volume"))
                .drop_nulls()
                .sort("timestamp")
            )

        htf_vol_closed = htf_vol_closed.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf_vol_closed.select(["volume"]).to_pandas()
        fast_ma = htf_pd["volume"].rolling(fast_window, min_periods=1).mean()
        slow_ma = htf_pd["volume"].rolling(slow_window, min_periods=1).mean()

        htf_vol_ma = htf_vol_closed.with_columns([
            pl.col("volume").alias("vol_live"),
            pl.Series("fast", fast_ma),
            pl.Series("slow", slow_ma)
        ])

        htf_to_join = htf_vol_ma.select(["timestamp", "vol_live", "fast", "slow"])
        df_out = df.join_asof(htf_to_join, on="timestamp", strategy="backward").rename({
            "vol_live": c_vol_live,
            "fast": c_vol_fast,
            "slow": c_vol_slow
        })

                             
    df_out = df_out.with_columns([
        (pl.col(c_vol_fast).fill_nan(None) > pl.col(c_vol_slow).fill_nan(None)).fill_null(False).alias(f"vol_trend_up_{time_frame}"),
        (pl.col(c_vol_live).fill_nan(None) > (pl.col(c_vol_slow).fill_nan(None) * 1.5)).fill_null(False).alias(f"vol_surge_{time_frame}"),
        (pl.col(c_vol_live).fill_nan(None) < (pl.col(c_vol_slow).fill_nan(None) * 0.5)).fill_null(False).alias(f"vol_dry_{time_frame}")
    ])

    _vs = pl.when(pl.col(c_vol_slow) > 0).then(pl.col(c_vol_slow)).otherwise(None)
    df_out = df_out.with_columns((pl.col(c_vol_live) / _vs).alias(f"volma_ratio_{time_frame}"))

    return df_out


def pt_obv(df, time_frame, sma_window=20):
    """Phân tích On-Balance Volume (OBV) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(sma_window, str):
        num_str = re.sub(r"\D", "", sma_window)
        sma_window = int(num_str) if num_str else 20
    else:
        sma_window = int(sma_window)

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_obv = f"obv_{time_frame}"
    c_obv_sma = f"obv_sma_{sma_window}_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["close", "volume"]).to_pandas()
        obv = ta.volume.on_balance_volume(close=df_pd["close"], volume=df_pd["volume"])
        obv_sma = obv.rolling(sma_window).mean()
        df_out = df.with_columns([
            pl.Series(c_obv, obv),
            pl.Series(c_obv_sma, obv_sma)
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
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["close", "volume"]).to_pandas()
        obv = ta.volume.on_balance_volume(close=htf_pd["close"], volume=htf_pd["volume"])
        obv_sma = obv.rolling(sma_window).mean()

        htf_features = htf.with_columns([
            pl.Series("obv", obv),
            pl.Series("obv_sma", obv_sma)
        ])

        htf_to_join = htf_features.select(["timestamp", "obv", "obv_sma"])
        df_out = df.join_asof(htf_to_join, on="timestamp", strategy="backward").rename({
            "obv": c_obv,
            "obv_sma": c_obv_sma
        })

    obv_roc = pl.col(c_obv).diff(5)
    obv_roc_std_50 = obv_roc.rolling_std(window_size=50)

                             
    df_out = df_out.with_columns([
        (pl.col(c_obv).fill_nan(None) > pl.col(c_obv_sma).fill_nan(None)).fill_null(False).alias(f"obv_bullish_{time_frame}"),
        (obv_roc.fill_nan(None) > (obv_roc_std_50.fill_nan(None) * 2)).fill_null(False).alias(f"obv_surge_{time_frame}")
    ])

                                                         
    df_out = df_out.with_columns((pl.col(c_obv) - pl.col(c_obv_sma)).alias(f"obv_osc_{time_frame}"))

    return df_out


def pt_vwap(df, time_frame, window=20):
    """Phân tích Rolling VWAP (MVWAP) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
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

    c_vwap = f"vwap_{time_frame}"

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_vwap(d, "1m", window)
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close", "volume"]).to_pandas()
        vwap_ind = ta.volume.VolumeWeightedAveragePrice(
            high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], volume=df_pd["volume"], window=window
        )
        df_out = df.with_columns(pl.Series(c_vwap, vwap_ind.volume_weighted_average_price()))
    distance_pct = (pl.col("close") - pl.col(c_vwap)).abs() / pl.col(c_vwap)

                                                            
    _vwap_safe = pl.when(pl.col(c_vwap) != 0).then(pl.col(c_vwap)).otherwise(None)
    df_out = df_out.with_columns(
        ((pl.col("close") - pl.col(c_vwap)) / _vwap_safe).alias(f"vwap_dist_{time_frame}")
    )

                             
    df_out = df_out.with_columns([
        (pl.col("close").fill_nan(None) > pl.col(c_vwap).fill_nan(None)).fill_null(False).alias(f"vwap_bullish_{time_frame}"),
        (distance_pct.fill_nan(None) > 0.03).fill_null(False).alias(f"vwap_overextended_{time_frame}")
    ])

    return df_out


def pt_volume_profile(df, time_frame="1D", price_step=10):
    """Phân tích Session Volume Profile dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    polars_time_frame = time_frame.lower().replace("d", "d")

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_poc = f"vp_poc_{time_frame}"
    c_vah = f"vp_vah_{time_frame}"
    c_val = f"vp_val_{time_frame}"

                                                     
    df_pd = df.select(["timestamp", "high", "low", "close", "volume"]).to_pandas()
    pandas_freq = polars_time_frame.replace("m", "min").replace("d", "D").replace("w", "W")
    df_pd["session"] = df_pd["timestamp"].dt.floor(pandas_freq)
    tp = (df_pd["high"] + df_pd["low"] + df_pd["close"]) / 3
    df_pd["price_zone"] = (tp / price_step).apply(np.floor) * price_step

                                   
    vol_by_price = df_pd.groupby(["session", "price_zone"])["volume"].sum().reset_index()
    vol_by_price = vol_by_price.sort_values(by=["session", "price_zone"])

                                 
    poc_data = vol_by_price.sort_values(by=["session", "volume", "price_zone"], ascending=[True, False, True]).groupby("session").first().reset_index()[["session", "price_zone"]].rename(columns={"price_zone": "POC"})

                                       
    vol_sorted = vol_by_price.sort_values(by=["session", "volume", "price_zone"], ascending=[True, False, False])
    vol_sorted["cum_vol_pct"] = vol_sorted.groupby("session")["volume"].cumsum() / vol_sorted.groupby("session")["volume"].transform("sum")
    value_area = vol_sorted[vol_sorted["cum_vol_pct"] <= 0.70]

    vah_val_data = value_area.groupby("session")["price_zone"].agg(
        VAH="max",
        VAL="min"
    ).reset_index()

           
    profile_data = pd.merge(poc_data, vah_val_data, on="session", how="left")
    profile_data = profile_data.sort_values("session")

                                                         
    profile_data["POC_closed"] = profile_data["POC"].shift(1)
    profile_data["VAH_closed"] = profile_data["VAH"].shift(1)
    profile_data["VAL_closed"] = profile_data["VAL"].shift(1)

                      
    df_pd = pd.merge(df_pd, profile_data[["session", "POC_closed", "VAH_closed", "VAL_closed"]], on="session", how="left")
    df_pd["POC_closed"] = df_pd["POC_closed"].ffill()
    df_pd["VAH_closed"] = df_pd["VAH_closed"].ffill()
    df_pd["VAL_closed"] = df_pd["VAL_closed"].ffill()

                                                                                            
    session_close = df_pd.groupby("session")["close"].last().reset_index().sort_values("session")
    session_close["close_closed"] = session_close["close"].shift(1)
    df_pd = pd.merge(df_pd, session_close[["session", "close_closed"]], on="session", how="left")
    df_pd["close_closed"] = df_pd["close_closed"].ffill()

                           
    df = df.with_columns([
        pl.Series(c_poc, df_pd["POC_closed"]),
        pl.Series(c_vah, df_pd["VAH_closed"]),
        pl.Series(c_val, df_pd["VAL_closed"]),
        pl.Series("_ref_close", df_pd["close_closed"])
    ])

                                                                          
    distance_to_poc = (pl.col("_ref_close") - pl.col(c_poc)).abs() / pl.col(c_poc)

    df_out = df.with_columns([
        (pl.col("_ref_close").fill_nan(None) > pl.col(c_vah).fill_nan(None)).fill_null(False).alias(f"vp_above_vah_{time_frame}"),
        (pl.col("_ref_close").fill_nan(None) < pl.col(c_val).fill_nan(None)).fill_null(False).alias(f"vp_below_val_{time_frame}"),
        (distance_to_poc.fill_nan(None) < 0.005).fill_null(False).alias(f"vp_near_poc_{time_frame}")
    ])

                                                                  
    _poc_safe = pl.when(pl.col(c_poc) != 0).then(pl.col(c_poc)).otherwise(None)
    df_out = df_out.with_columns(((pl.col("_ref_close") - pl.col(c_poc)) / _poc_safe).alias(f"vp_poc_dist_{time_frame}"))

    return df_out.drop("_ref_close")


def pt_cmf(df, time_frame, window=20):
    """Phân tích Chaikin Money Flow (CMF) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 20
    else:
        window = int(window)
    if window < 2:
        window = 20

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_cmf = f"cmf_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close", "volume"]).to_pandas()
        cmf = ta.volume.ChaikinMoneyFlowIndicator(
            high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], volume=df_pd["volume"], window=window
        ).chaikin_money_flow()
        df_out = df.with_columns(pl.Series(c_cmf, cmf))
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
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low", "close", "volume"]).to_pandas()
        cmf = ta.volume.ChaikinMoneyFlowIndicator(
            high=htf_pd["high"], low=htf_pd["low"], close=htf_pd["close"], volume=htf_pd["volume"], window=window
        ).chaikin_money_flow()

        htf_features = htf.with_columns(pl.Series("cmf", cmf))
        htf_to_join = htf_features.select(["timestamp", "cmf"])
        df_out = df.join_asof(htf_to_join, on="timestamp", strategy="backward").rename({"cmf": c_cmf})

                             
    df_out = df_out.with_columns([
        (pl.col(c_cmf).fill_nan(None) > 0.1).fill_null(False).alias(f"cmf_bull_{time_frame}"),
        (pl.col(c_cmf).fill_nan(None) < -0.1).fill_null(False).alias(f"cmf_bear_{time_frame}"),
        pl.when(pl.col(c_cmf).fill_nan(None) > 0.1).then(pl.lit("MUA_MANH"))
        .when(pl.col(c_cmf).fill_nan(None) < -0.1).then(pl.lit("BAN_MANH"))
        .otherwise(pl.lit("TRUNG_TINH"))
        .alias(f"cmf_status_{time_frame}")
    ])

    return df_out


def pt_ad_line(df, time_frame):
    """Phân tích Accumulation/Distribution Line dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_ad = f"ad_{time_frame}"

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, polars_time_frame, time_frame, lambda d: pt_ad_line(d, "1m")
        )

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close", "volume"]).to_pandas()
        ad = ta.volume.acc_dist_index(high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], volume=df_pd["volume"])
        df_out = df.with_columns(pl.Series(c_ad, ad))
                             
    ad_trend = pl.col(c_ad) - pl.col(c_ad).shift(10)
    price_trend = pl.col("close") - pl.col("close").shift(10)

    df_out = df_out.with_columns([
        (pl.col(c_ad).fill_nan(None) > pl.col(c_ad).shift(1).fill_nan(None)).fill_null(False).alias(f"ad_rising_{time_frame}"),
        pl.when((ad_trend.fill_nan(None) > 0) & (price_trend.fill_nan(None) < 0)).then(pl.lit("DIVERGE_BULL"))
        .when((ad_trend.fill_nan(None) < 0) & (price_trend.fill_nan(None) > 0)).then(pl.lit("DIVERGE_BEAR"))
        .otherwise(pl.lit("CONFIRM"))
        .alias(f"ad_vs_price_{time_frame}")
    ])

                                                      
    df_out = df_out.with_columns(
        (pl.col(c_ad) - pl.col(c_ad).ewm_mean(span=20, adjust=False)).alias(f"ad_osc_{time_frame}")
    )

    return df_out


def pt_mfi_volume(df, time_frame, window=14):
    """Phân tích Money Flow Index (MFI) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)
    if window < 2:
        window = 14

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_mfi = f"mfi_vol_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close", "volume"]).to_pandas()
        mfi = ta.volume.money_flow_index(
            high=df_pd["high"], low=df_pd["low"], close=df_pd["close"], volume=df_pd["volume"], window=window
        )
        df_out = df.with_columns(pl.Series(c_mfi, mfi))
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
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low", "close", "volume"]).to_pandas()
        mfi = ta.volume.money_flow_index(
            high=htf_pd["high"], low=htf_pd["low"], close=htf_pd["close"], volume=htf_pd["volume"], window=window
        )
        htf = htf.with_columns(pl.Series("mfi", mfi))

        htf_to_join = htf.select(["timestamp", "mfi"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")

        df_out = df_joined.with_columns(pl.col("mfi").alias(c_mfi)).drop("mfi")

                             
    df_out = df_out.with_columns([
        (pl.col(c_mfi).fill_nan(None) > 80).fill_null(False).alias(f"mfi_vol_ob_{time_frame}"),
        (pl.col(c_mfi).fill_nan(None) < 20).fill_null(False).alias(f"mfi_vol_os_{time_frame}")
    ])

    return df_out


def pt_ease_of_movement(df, time_frame, window=14):
    """Phân tích Ease of Movement (EOM) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 14
    else:
        window = int(window)
    if window < 2:
        window = 14

    polars_time_frame = time_frame.lower()

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    c_eom = f"eom_{time_frame}"

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "volume"]).to_pandas()
        eom = ta.volume.EaseOfMovementIndicator(
            high=df_pd["high"], low=df_pd["low"], volume=df_pd["volume"], window=window
        ).ease_of_movement()
        df_out = df.with_columns(pl.Series(c_eom, eom))
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
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf = htf.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )

        htf_pd = htf.select(["high", "low", "volume"]).to_pandas()
        eom = ta.volume.EaseOfMovementIndicator(
            high=htf_pd["high"], low=htf_pd["low"], volume=htf_pd["volume"], window=window
        ).ease_of_movement()
        htf = htf.with_columns(pl.Series("eom", eom))

        htf_to_join = htf.select(["timestamp", "eom"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")

        df_out = df_joined.with_columns(pl.col("eom").alias(c_eom)).drop("eom")

                             
    df_out = df_out.with_columns(
        (pl.col(c_eom).fill_nan(None) > 0.0).fill_null(False).alias(f"eom_bull_{time_frame}")
    )

    return df_out


def pt_pvt(df, time_frame):
    """Price Volume Trend (PVT) - Vectorized MTF"""
    polars_time_frame = time_frame.lower()
    c_pvt = f"pvt_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    if time_frame == "1m":
        df_pd = df.select(["close", "volume"]).to_pandas()
        pvt = ta.volume.volume_price_trend(close=df_pd["close"], volume=df_pd["volume"])
        df_out = df.with_columns(pl.Series(c_pvt, pvt))
    else:
        htf = (
            df.group_by_dynamic(
                "timestamp",
                every=polars_time_frame,
                closed="left",
                label="left"
            )
            .agg([
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf_pd = htf.select(["close", "volume"]).to_pandas()
        pvt = ta.volume.volume_price_trend(close=htf_pd["close"], volume=htf_pd["volume"])

        htf_pvt = htf.with_columns(pl.Series("pvt", pvt))

        htf_pvt = htf_pvt.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )
        
        htf_to_join = htf_pvt.select(["timestamp", "pvt"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns(pl.col("pvt").alias(c_pvt)).drop("pvt")

                             
    df_out = df_out.with_columns(
        (pl.col(c_pvt).fill_nan(None) > pl.col(c_pvt).shift(1).fill_nan(None)).fill_null(False).alias(f"pvt_rising_{time_frame}")
    )
    return df_out


def pt_chaikin_oscillator(df, time_frame, fast_period=3, slow_period=10):
    """Chaikin Oscillator - Vectorized MTF"""
    if isinstance(fast_period, str):
        num_str = re.sub(r"\D", "", fast_period)
        fast_period = int(num_str) if num_str else 3
    else:
        fast_period = int(fast_period)
    if isinstance(slow_period, str):
        num_str = re.sub(r"\D", "", slow_period)
        slow_period = int(num_str) if num_str else 10
    else:
        slow_period = int(slow_period)

    polars_time_frame = time_frame.lower()
    c_chaikin = f"chaikin_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _chaikin_calc_pd(high, low, close, volume):
        adl = ta.volume.acc_dist_index(high=high, low=low, close=close, volume=volume)
        chaikin = adl.ewm(span=fast_period, adjust=False).mean() - adl.ewm(span=slow_period, adjust=False).mean()
        return chaikin

    if time_frame == "1m":
        df_pd = df.select(["high", "low", "close", "volume"]).to_pandas()
        chaikin = _chaikin_calc_pd(df_pd["high"], df_pd["low"], df_pd["close"], df_pd["volume"])
        df_out = df.with_columns(pl.Series(c_chaikin, chaikin))
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
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume")
            ])
            .drop_nulls()
            .sort("timestamp")
        )

        htf_pd = htf.select(["high", "low", "close", "volume"]).to_pandas()
        chaikin = _chaikin_calc_pd(htf_pd["high"], htf_pd["low"], htf_pd["close"], htf_pd["volume"])

        htf_chaikin = htf.with_columns(pl.Series("chaikin", chaikin))

        htf_chaikin = htf_chaikin.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )
        
        htf_to_join = htf_chaikin.select(["timestamp", "chaikin"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns(pl.col("chaikin").alias(c_chaikin)).drop("chaikin")

                             
    df_out = df_out.with_columns(
        (pl.col(c_chaikin).fill_nan(None) > 0.0).fill_null(False).alias(f"chaikin_bull_{time_frame}")
    )
    return df_out
