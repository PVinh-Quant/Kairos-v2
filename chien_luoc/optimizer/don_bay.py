"""
chien_luoc/logic_vectorized/chien_luoc_don_bay.py – Đòn bẩy động (Vectorized)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tính leverage động theo ATR 15M, ADX, Volume, Breakout và Bollinger Squeeze cho
toàn bộ DataFrame (Pandas-based), phục vụ backtest/tối ưu.
"""

import numpy as np


def tinh_don_bay(df, don_bay_goc=5, max_leverage=50, time_frame="15m"):
    """
    Tính leverage động theo ATR, ADX, Volume, Breakout, và Bollinger Squeeze (khung `time_frame`).
    Trả về df với cột `leverage`.
    """
    import polars as pl
    import numpy as np

    is_pandas = not hasattr(df, "clone")
    if is_pandas:
        df_pl = pl.from_pandas(df)
    else:
        df_pl = df.clone()

    from Indicator.bien_dong import pt_atr, pt_bollinger_squeeze
    from Indicator.xu_huong import pt_adx
    from Indicator.khoi_luong import pt_volume
    from Indicator.cau_truc_gia import pt_breakout

    tf = time_frame
    df_pl = pt_atr(df_pl, tf)
    df_pl = pt_adx(df_pl, tf)
    df_pl = pt_volume(df_pl, tf, volume_luy_ke=False)
    df_pl = pt_breakout(df_pl, tf)
    df_pl = pt_bollinger_squeeze(df_pl, tf)

    col_atr = f"atr_{tf}"
    col_mean = f"atr_mean_{tf}"

    if col_atr not in df_pl.columns:
        df_pl = df_pl.with_columns(pl.lit(don_bay_goc).cast(pl.Int64).alias("leverage"))
        return df_pl.to_pandas() if is_pandas else df_pl

    atr = pl.col(col_atr).forward_fill().fill_null(0.0)
    atr_mean = pl.col(col_mean).forward_fill().fill_null(pl.col(col_atr).forward_fill().fill_null(0.0))

    leverage_default = pl.when(atr > atr_mean * 1.05) \
        .then(float(don_bay_goc - 1)) \
        .when(atr < atr_mean * 0.95) \
        .then(float(don_bay_goc + 1)) \
        .otherwise(float(don_bay_goc))

    cond_1 = (pl.col(f"atr_status_{tf}") == "BIEN_DONG_CAO") & (pl.col(f"vol_tang_manh_{tf}") == True)
    lev_1 = float(don_bay_goc - 3)

    cond_2 = (pl.col(f"has_trend_{tf}") == False) & (pl.col(f"bb_status_{tf}") == "BOP")
    lev_2 = float(min(don_bay_goc, 10))

    cond_3 = (
        (pl.col(f"breakout_{tf}") != "None")
        & (pl.col(f"has_trend_{tf}") == True)
        & (pl.col(f"vol_tang_{tf}") == True)
    )
    lev_3 = float(don_bay_goc)

    leverage_expr = pl.when(cond_1).then(lev_1) \
        .when(cond_2).then(lev_2) \
        .when(cond_3).then(lev_3) \
        .otherwise(leverage_default)

    leverage_final = leverage_expr.round(0).clip(1.0, float(max_leverage)).cast(pl.Int64)

    df_pl = df_pl.with_columns(leverage_final.alias("leverage"))

    return df_pl.to_pandas() if is_pandas else df_pl


def them_don_bay_dong(df, don_bay_goc=5, max_leverage=50):
    """
    Wrapper function to align with the expected import in toi_uu_hoa/bo_dieu_phoi.py.
    """
    tf = "15m"
    Q = None
    try:
        import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        dung_don_bay_dong = getattr(Q, "DUNG_DON_BAY_DONG", False)
    except ImportError:
        dung_don_bay_dong = False

    if dung_don_bay_dong:
                                                                                     
        if Q is not None:
            don_bay_goc = int(getattr(Q, "DON_BAY_GOC", don_bay_goc) or don_bay_goc)
            max_leverage = int(getattr(Q, "MAX_LEVERAGE", max_leverage) or max_leverage)
            tf = getattr(Q, "DON_BAY_TF", tf) or tf
        return tinh_don_bay(df, don_bay_goc=don_bay_goc, max_leverage=max_leverage, time_frame=tf)
    else:
        import polars as pl
        is_pandas = not hasattr(df, "clone")
        if is_pandas:
            df_pl = pl.from_pandas(df)
        else:
            df_pl = df.clone()
        df_pl = df_pl.with_columns(pl.lit(int(don_bay_goc)).cast(pl.Int64).alias("leverage"))
        return df_pl.to_pandas() if is_pandas else df_pl


def tinh_don_bay_live(symbol, don_bay, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d,
                      max_leverage=50, time_frame="15m"):
    """
    Điều chỉnh đòn bẩy động theo điều kiện thị trường tại thời điểm hiện tại.
    `time_frame`/`max_leverage` đồng bộ với chip "Đòn bẩy động" (mặc định 15m / trần 50).
    """
    frames = {"1m": df_1m, "3m": df_3m, "5m": df_5m, "15m": df_15m,
              "30m": df_30m, "1h": df_1h, "4h": df_4h, "1d": df_1d}
    frame = frames.get(time_frame)
    if frame is None:
        frame = df_15m
    if frame is None or frame.is_empty():
        return don_bay
    try:
        df_calc = tinh_don_bay(frame, don_bay_goc=don_bay, max_leverage=max_leverage, time_frame=time_frame)
        if df_calc is None or len(df_calc) == 0:
            return don_bay
        
        if hasattr(df_calc, "clone"):
                    
            return int(df_calc["leverage"][-1])
        else:
                    
            return int(df_calc["leverage"].iloc[-1])
    except Exception as e:
        from utils.log import logger
        logger.error(f"Lỗi tính đòn bẩy live: {e}")
        return don_bay


def phan_tich_don_bay(symbol, don_bay, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d):
    """
    Wrapper function to align with the expected import in chuc_nang/.
    """
    return tinh_don_bay_live(
        symbol=symbol,
        don_bay=don_bay,
        df_1m=df_1m,
        df_3m=df_3m,
        df_5m=df_5m,
        df_15m=df_15m,
        df_30m=df_30m,
        df_1h=df_1h,
        df_4h=df_4h,
        df_1d=df_1d,
    )


