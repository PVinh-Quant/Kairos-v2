"""
ml/trang_thai_thi_truong_ml/tao_feature.py – Feature engineering cho ML
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
18 features lõi tính trên mỗi khung thời gian (5M/15M/1H/4H):
  D, S (EMA distance/slope), ADX, RSI, RSIslope, ROC, ATRn,
  VOLz, SpreadATR, BBwidth, SQZ, CHOP, ER, BBpctB,
  VWAPd, WickUpProp, WickDnProp, BodyProp

2 chế độ tính toán:
  • feature_dataset()       – bar-to-bar cho bot realtime (Polars → dict → pandas)
  • features_vectorized()   – toàn bộ dataset 1 lần cho training/backtest (all Polars)

Dùng hàm lõi calc_core_features() chung để đảm bảo không bao giờ có
sự lệch công thức giữa lúc train và lúc inference (train-serve skew).
"""

import polars as pl
import pandas as pd
import numpy as np





def calc_core_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Chứa 100% công thức tính toán 18 Features chuẩn.
    Không bao giờ bị lệch dữ liệu giữa Train và Live vì dùng chung 1 logic.
    """
    EMA_LEN, ADX_LEN, RSI_LEN, BB_LEN = 50, 14, 14, 20
    VOL_MA_LEN, ATR_LEN, CHOP_LEN, ER_LEN = 20, 14, 14, 10


    df = df.with_columns(
        [
            pl.col("close").diff().alias("diff"),
            (pl.col("high") - pl.col("low")).alias("hl"),
            (pl.col("high") - pl.col("close").shift(1)).abs().alias("hc"),
            (pl.col("low") - pl.col("close").shift(1)).abs().alias("lc"),
        ]
    ).with_columns([pl.max_horizontal(["hl", "hc", "lc"]).alias("tr")])


    df = df.with_columns(
        [
            pl.col("close").ewm_mean(span=EMA_LEN, adjust=False).alias("ema_50"),
            pl.col("close").ewm_mean(span=20, adjust=False).alias("ema_20"),
            pl.col("tr").rolling_mean(ATR_LEN).alias("atr"),
        ]
    )


    df = (
        df.with_columns(
            [
                pl.when(pl.col("diff") > 0)
                .then(pl.col("diff"))
                .otherwise(0)
                .rolling_mean(RSI_LEN)
                .alias("avg_gain"),
                pl.when(pl.col("diff") < 0)
                .then(pl.col("diff").abs())
                .otherwise(0)
                .rolling_mean(RSI_LEN)
                .alias("avg_loss"),
            ]
        )
        .with_columns(
            [
                (
                    100
                    - (100 / (1 + (pl.col("avg_gain") / (pl.col("avg_loss") + 1e-9))))
                ).alias("RSI")
            ]
        )
        .with_columns([(pl.col("RSI") - pl.col("RSI").shift(3)).alias("RSIslope")])
    )


    df = (
        df.with_columns(
            [
                (pl.col("high") - pl.col("high").shift(1)).alias("up_move"),
                (pl.col("low").shift(1) - pl.col("low")).alias("down_move"),
            ]
        )
        .with_columns(
            [
                pl.when(
                    (pl.col("up_move") > pl.col("down_move")) & (pl.col("up_move") > 0)
                )
                .then(pl.col("up_move"))
                .otherwise(0)
                .alias("plus_dm"),
                pl.when(
                    (pl.col("down_move") > pl.col("up_move"))
                    & (pl.col("down_move") > 0)
                )
                .then(pl.col("down_move"))
                .otherwise(0)
                .alias("minus_dm"),
            ]
        )
        .with_columns(
            [
                (
                    pl.col("plus_dm").rolling_mean(ADX_LEN) / (pl.col("atr") + 1e-9)
                ).alias("di_plus"),
                (
                    pl.col("minus_dm").rolling_mean(ADX_LEN) / (pl.col("atr") + 1e-9)
                ).alias("di_minus"),
            ]
        )
        .with_columns(
            [
                (
                    (pl.col("di_plus") - pl.col("di_minus")).abs()
                    / (pl.col("di_plus") + pl.col("di_minus") + 1e-9)
                )
                .rolling_mean(ADX_LEN)
                .alias("ADX")
            ]
        )
    )


    df = df.with_columns(
        [
            pl.col("close").rolling_mean(BB_LEN).alias("bb_mid"),
            pl.col("close").rolling_std(BB_LEN).alias("bb_std"),
        ]
    ).with_columns(
        [
            (pl.col("bb_mid") + 2 * pl.col("bb_std")).alias("bb_high"),
            (pl.col("bb_mid") - 2 * pl.col("bb_std")).alias("bb_low"),
            (pl.col("ema_20") + 1.5 * pl.col("atr")).alias("kc_high"),
            (pl.col("ema_20") - 1.5 * pl.col("atr")).alias("kc_low"),
        ]
    )


    df = df.with_columns(
        [
            pl.col("volume").rolling_mean(VOL_MA_LEN).alias("vol_sma"),
            pl.col("volume").rolling_std(VOL_MA_LEN).alias("vol_std"),
            pl.col("tr").rolling_sum(CHOP_LEN).alias("tr_sum"),
            pl.col("high").rolling_max(CHOP_LEN).alias("high_max"),
            pl.col("low").rolling_min(CHOP_LEN).alias("low_min"),
            (pl.col("close") - pl.col("close").shift(ER_LEN)).abs().alias("er_change"),
            pl.col("diff").abs().rolling_sum(ER_LEN).alias("er_vol"),
            pl.max_horizontal("open", "close").alias("body_top"),
            pl.min_horizontal("open", "close").alias("body_bottom"),
            (pl.col("close") * pl.col("volume")).rolling_sum(100).alias("cv_sum"),
            pl.col("volume").rolling_sum(100).alias("v_sum"),
        ]
    )


    return df.select(
        [
            pl.col("timestamp"),
            ((pl.col("close") - pl.col("ema_50")) / (pl.col("ema_50") + 1e-9)).alias(
                "D"
            ),
            (
                (pl.col("ema_50") - pl.col("ema_50").shift(5))
                / (pl.col("ema_50").shift(5) + 1e-9)
            ).alias("S"),
            pl.col("ADX"),
            pl.col("RSI"),
            pl.col("RSIslope"),
            (
                (pl.col("close") - pl.col("close").shift(10))
                / (pl.col("close").shift(10) + 1e-9)
            ).alias("ROC"),
            (pl.col("atr") / (pl.col("close") + 1e-9)).alias("ATRn"),
            ((pl.col("volume") - pl.col("vol_sma")) / (pl.col("vol_std") + 1e-9)).alias(
                "VOLz"
            ),
            (pl.col("hl") / (pl.col("atr") + 1e-9)).alias("SpreadATR"),
            ((pl.col("bb_high") - pl.col("bb_low")) / (pl.col("bb_mid") + 1e-9)).alias(
                "BBwidth"
            ),
            pl.when(
                (pl.col("bb_high") < pl.col("kc_high"))
                & (pl.col("bb_low") > pl.col("kc_low"))
            )
            .then(1.0)
            .otherwise(0.0)
            .alias("SQZ"),
            (
                100
                * (
                    pl.col("tr_sum") / (pl.col("high_max") - pl.col("low_min") + 1e-9)
                ).log10()
                / np.log10(CHOP_LEN)
            ).alias("CHOP"),
            (pl.col("er_change") / (pl.col("er_vol") + 1e-9)).alias("ER"),
            (
                (pl.col("close") - pl.col("bb_low"))
                / (pl.col("bb_high") - pl.col("bb_low") + 1e-9)
            ).alias("BBpctB"),
            (
                (pl.col("close") - (pl.col("cv_sum") / (pl.col("v_sum") + 1e-9)))
                / (pl.col("atr") + 1e-9)
            ).alias("VWAPd"),
            ((pl.col("high") - pl.col("body_top")) / (pl.col("hl") + 1e-9)).alias(
                "WickUpProp"
            ),
            ((pl.col("body_bottom") - pl.col("low")) / (pl.col("hl") + 1e-9)).alias(
                "WickDnProp"
            ),
            (
                (pl.col("body_top") - pl.col("body_bottom")) / (pl.col("hl") + 1e-9)
            ).alias("BodyProp"),
        ]
    )





def feature_dataset(df_5m, df_15m, df_1h, df_4h, last_state=0):
    """Dùng khi Bot nhận Data từng cây nến và truyền vào."""
    if any(df is None or len(df) < 120 for df in [df_5m, df_15m, df_1h, df_4h]):
        return None

    feature_row = {}


    for i in range(8):
        feature_row[f"ctx_last_state_{i}"] = 1.0 if last_state == i else 0.0


    ordered_suffixes = ["5M", "15M", "1H", "4H"]
    data_dict = {"5M": df_5m, "15M": df_15m, "1H": df_1h, "4H": df_4h}

    for suffix in ordered_suffixes:
        df = data_dict[suffix]
        if not isinstance(df, pl.DataFrame):
            df = pl.DataFrame(df)

        try:

            df_closed = df.head(df.height - 1)


            df_feat = calc_core_features(df_closed)


            row = df_feat.tail(1).to_dicts()[0]


            for k, v in row.items():
                if k != "timestamp":
                    feature_row[f"{k}_{suffix}"] = v

        except Exception as e:
            print(f"❌ Lỗi tính toán tại {suffix}: {e}")
            return None


    feature_df = pd.DataFrame([feature_row])
    feature_df = feature_df.replace([np.inf, -np.inf], 0.0).fillna(0.0)

    return feature_df





def features_vectorized(df_1m: pl.DataFrame) -> pl.DataFrame:
    """Dùng khi xử lý Data Lịch sử quy mô lớn để Train AI hoặc Backtest hàng loạt."""

    if "volume" not in df_1m.columns:
        df_1m = df_1m.with_columns(pl.lit(0.0).cast(pl.Float64).alias("volume"))

    def process_timeframe(df, interval_str, suffix, shift_minutes):
        """Gộp nến theo khung thời gian, tính features và dịch chuyển timestamp."""
        rule = interval_str.lower().replace("min", "m")


        df_sorted = df.sort("timestamp")
        df_res = (
            df_sorted.group_by_dynamic(
                "timestamp", every=rule, closed="left", label="left", start_by="window"
            )
            .agg(
                [
                    pl.col("open").first(),
                    pl.col("high").max(),
                    pl.col("low").min(),
                    pl.col("close").last(),
                    pl.col("volume").sum(),
                ]
            )
            .drop_nulls()
        )


        features = calc_core_features(df_res)


        features = features.with_columns(
            (pl.col("timestamp") + pl.duration(minutes=shift_minutes)).alias(
                "timestamp"
            )
        )


        features = features.select(
            [pl.col("timestamp")]
            + [
                pl.col(c).alias(f"{c}_{suffix}")
                for c in features.columns
                if c != "timestamp"
            ]
        )
        return features


    f5m = process_timeframe(df_1m, "5m", "5M", 5)
    f15m = process_timeframe(df_1m, "15m", "15M", 15)
    f1h = process_timeframe(df_1m, "1h", "1H", 60)
    f4h = process_timeframe(df_1m, "4h", "4H", 240)


    df_base = df_1m.select(["timestamp"])

    if "regime" in df_1m.columns:
        last_regime = df_1m["regime"].shift(1).fill_null(0)
        for i in range(8):
            df_base = df_base.with_columns(
                pl.when(last_regime == i)
                .then(1.0)
                .otherwise(0.0)
                .alias(f"ctx_last_state_{i}")
            )
    else:
        for i in range(8):
            df_base = df_base.with_columns(
                pl.lit(1.0 if i == 0 else 0.0).alias(f"ctx_last_state_{i}")
            )


    df_features = (
        df_base.join(f5m, on="timestamp", how="left")
        .join(f15m, on="timestamp", how="left")
        .join(f1h, on="timestamp", how="left")
        .join(f4h, on="timestamp", how="left")
        .fill_null(strategy="forward")
        .drop_nulls()
    )


    feature_cols = [c for c in df_features.columns if c != "timestamp"]

    df_features = df_features.with_columns(
        [
            pl.when(pl.col(c).is_infinite() | pl.col(c).is_nan())
            .then(0.0)
            .otherwise(pl.col(c))
            .alias(c)
            for c in feature_cols
        ]
    )

    return df_features
