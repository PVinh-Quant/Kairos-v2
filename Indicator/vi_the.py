"""TÂM LÝ & VỊ THẾ (Sentiment / Positioning) – Phiên bản Polars
👉 Đám đông đang nghiêng về đâu?
- CVD (Cumulative Volume Delta) – xấp xỉ từ OHLCV
- Buyer Pressure – tỷ lệ nến bullish rolling
- Volume Surge   – smart money confirmation
📌 Backtest không có WebSocket hay Funding Rate lịch sử → dùng proxy từ giá.
"""

import polars as pl
import numpy as np
import re


def pt_elder_ray(df, time_frame, window=13):
    """Phân tích Elder Ray Index (Bull/Bear Power) dạng Vectorized Hỗ trợ Đa Khung Thời Gian (MTF) bằng Polars."""
    if isinstance(window, str):
        num_str = re.sub(r"\D", "", window)
        window = int(num_str) if num_str else 13
    else:
        window = int(window)

    polars_time_frame = time_frame.lower()
    c_bull = f"bull_power_{time_frame}"
    c_bear = f"bear_power_{time_frame}"

    if "timestamp" in df.columns:
        if df.schema["timestamp"] in (pl.String, pl.Utf8):
            df = df.with_columns(pl.col("timestamp").str.to_datetime())
        df = df.sort("timestamp")

    def _elder_calc(high_col, low_col, close_col):
        ema = close_col.ewm_mean(span=window, adjust=False)
        bull = high_col - ema
        bear = low_col - ema
        return bull, bear

    if time_frame == "1m":
        bull, bear = _elder_calc(pl.col("high"), pl.col("low"), pl.col("close"))
        df_out = df.with_columns([
            bull.alias(c_bull),
            bear.alias(c_bear)
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

        bull, bear = _elder_calc(pl.col("high"), pl.col("low"), pl.col("close"))
        htf_elder = htf.with_columns([
            bull.alias("bull"),
            bear.alias("bear")
        ])

        htf_elder = htf_elder.with_columns(
            pl.col("timestamp").dt.offset_by(polars_time_frame)
        )
        
        htf_to_join = htf_elder.select(["timestamp", "bull", "bear"])
        df_joined = df.join_asof(htf_to_join, on="timestamp", strategy="backward")
        df_out = df_joined.with_columns([
            pl.col("bull").alias(c_bull),
            pl.col("bear").alias(c_bear)
        ]).drop(["bull", "bear"])

    return df_out
