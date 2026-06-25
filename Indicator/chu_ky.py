"""THỜI GIAN & CHU KỲ (Time / Cycle) - Phiên bản Polars
👉 Khi nào thị trường hay phản ứng?
"""

import polars as pl
import re

_ASIAN_START, _ASIAN_END = 0, 8
_LONDON_START, _LONDON_END = 7, 16
_NY_START, _NY_END = 13, 22
_OVERLAP_START, _OVERLAP_END = 13, 16
_FUNDING_HOURS = {0, 8, 16}


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


def pt_kiem_tra_ngay(df):
    """
    Kiểm tra ngày trong tuần (vectorized).
    """
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

                                                   
    df = df.with_columns(
        pl.lit(True).alias("check_days")
    )
    return df


def pt_kiem_tra_gio(df):
    """
    Kiểm tra giờ giao dịch (vectorized).
    """
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    gio = pl.col("timestamp").dt.hour()
    df = df.with_columns(
        (gio != 22).alias("check_hours")
    )
    return df


def pt_phien_giao_dich(df, time_frame):
    """
    Phân loại mỗi nến theo phiên giao dịch chính.
    """
    tf = time_frame.lower().replace(" ", "")
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    hour = pl.col("timestamp").dt.hour()

    in_asian = (hour >= _ASIAN_START) & (hour < _ASIAN_END)
    in_london = (hour >= _LONDON_START) & (hour < _LONDON_END)
    in_ny = (hour >= _NY_START) & (hour < _NY_END)
    in_overlap = (hour >= _OVERLAP_START) & (hour < _OVERLAP_END)

    phien_expr = (
        pl.when(in_overlap)
        .then(pl.lit("OVERLAP"))
        .otherwise(
            pl.when(in_ny & ~in_overlap)
            .then(pl.lit("NY"))
            .otherwise(
                pl.when(in_london & ~in_ny)
                .then(pl.lit("LONDON"))
                .otherwise(
                    pl.when(in_asian & ~in_london)
                    .then(pl.lit("ASIAN"))
                    .otherwise(pl.lit("OFF_PEAK"))
                )
            )
        )
    )

    is_funding = hour.is_in(list(_FUNDING_HOURS))
    is_pre_funding = hour.is_in(list({h - 1 for h in _FUNDING_HOURS if h > 0} | {23}))

    weight_expr = (
        pl.when(phien_expr == "OVERLAP").then(3)
        .when((phien_expr == "NY") | (phien_expr == "LONDON")).then(2)
        .when(phien_expr == "ASIAN").then(1)
        .otherwise(0)
    )

    df = df.with_columns([
        phien_expr.alias(f"phien_{tf}"),
        in_overlap.alias(f"is_overlap_{tf}"),
        (in_london | in_ny).alias(f"is_high_vol_session_{tf}"),
        (is_funding | is_pre_funding).alias(f"is_funding_hour_{tf}"),
        weight_expr.alias(f"session_weight_{tf}")
    ])

    return df


def pt_session_range(df, time_frame):
    """
    Tính High/Low tích lũy của phiên giao dịch hiện tại (8h block).
    """
    tf = time_frame.lower().replace(" ", "")
    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

                                                              
    if time_frame != "1m":
        return _rai_xuong_tu_khung_lon(
            df, tf, tf, lambda d: pt_session_range(d, "1m")
        )

    session_block = pl.col("timestamp").dt.hour() // 8
                                     
    df = df.with_columns(
        (pl.col("timestamp").dt.date().cast(pl.String) + "_" + session_block.cast(pl.String)).alias("_session_key")
    )

    df = df.with_columns([
        pl.col("high").cum_max().over("_session_key").alias(f"session_high_{tf}"),
        pl.col("low").cum_min().over("_session_key").alias(f"session_low_{tf}"),
    ])

    df = df.with_columns(
        ((pl.col(f"session_high_{tf}") - pl.col(f"session_low_{tf}"))
         / (pl.col(f"session_low_{tf}") + 1e-9)
         * 100).alias(f"session_range_pct_{tf}")
    )

    df = df.drop("_session_key")
    return df
