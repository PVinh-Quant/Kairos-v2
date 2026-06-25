"""
chien_luoc/logic_vectorized/stoploss_takeprofit.py – Quản lý SL/TP động (Vectorized)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tính SL/TP theo ATR cho toàn bộ DataFrame (Pandas-based), phục vụ backtest/tối ưu.
"""

import numpy as np


def tinh_sl_tp(df, time_frame="15m", base_sl=2.5, rr=2.0):
    """
    Tính SL/TP động theo ATR và thêm vào DataFrame.
    Trả về df với cột `sl_pct` và `tp_pct`.
    """
    import polars as pl
    import numpy as np

    is_pandas = not hasattr(df, "clone")
    if is_pandas:
        df_pl = pl.from_pandas(df)
    else:
        df_pl = df.clone()

    from Indicator.bien_dong import pt_atr
    df_pl = pt_atr(df_pl, time_frame)

    col_atr = f"atr_{time_frame}"
    col_mean = f"atr_mean_{time_frame}"

    if col_atr not in df_pl.columns:
        df_pl = df_pl.with_columns([
            pl.lit(base_sl / 100.0).alias("sl_pct"),
            pl.lit(base_sl * rr / 100.0).alias("tp_pct")
        ])
        return df_pl.to_pandas() if is_pandas else df_pl

    atr = pl.col(col_atr).forward_fill().fill_null(0.0)
    atr_mean = pl.col(col_mean).forward_fill().fill_null(pl.col(col_atr).forward_fill().fill_null(0.0))

    vol_ratio = (atr / (atr_mean + 1e-9)).clip(0.5, 3.0)
    
    def get_expr(val):
        if isinstance(val, str):
            return pl.col(val)
        elif isinstance(val, pl.Expr):
            return val
        elif hasattr(val, "values") or isinstance(val, (list, np.ndarray)):
            return pl.Series(val)
        else:
            return pl.lit(val)

    base_sl_expr = get_expr(base_sl)
    rr_expr = get_expr(rr)

    he_so_sl = (base_sl_expr * vol_ratio).clip(1.0, 5.0)
    he_so_tp = he_so_sl * rr_expr

    close = pl.when(pl.col("close") == 0).then(None).otherwise(pl.col("close")).fill_nan(None).forward_fill()

    sl_pct = (atr * he_so_sl / close).clip(0.005, 0.15)              
    tp_pct = (atr * he_so_tp / close).clip(0.01, 0.30)              

    df_pl = df_pl.with_columns([
        sl_pct.alias("sl_pct"),
        tp_pct.alias("tp_pct")
    ])

    return df_pl.to_pandas() if is_pandas else df_pl


def tinh_sl_tp_co_dinh(df, base_sl=2.5, rr=2.0):
    """
    SL/TP CỐ ĐỊNH theo % phẳng (không theo ATR) — dùng khi tắt chế độ SL/TP động.
    Trả về df với cột `sl_pct` (= base_sl%) và `tp_pct` (= base_sl*rr%).
    """
    import polars as pl
    import numpy as np

    is_pandas = not hasattr(df, "clone")
    if is_pandas:
        df_pl = pl.from_pandas(df)
    else:
        df_pl = df.clone()

    def get_expr(val):
        if isinstance(val, str):
            return pl.col(val)
        elif isinstance(val, pl.Expr):
            return val
        elif hasattr(val, "values") or isinstance(val, (list, np.ndarray)):
            return pl.Series(val)
        else:
            return pl.lit(val)

    base_sl_expr = get_expr(base_sl)
    rr_expr = get_expr(rr)

    df_pl = df_pl.with_columns([
        (base_sl_expr / 100.0).alias("sl_pct"),
        ((base_sl_expr * rr_expr) / 100.0).alias("tp_pct")
    ])

    return df_pl.to_pandas() if is_pandas else df_pl


def them_sl_tp(df, time_frame="15m", base_sl=2.5, rr=2.0):
    """
    Wrapper function to align with the expected import in toi_uu_hoa/bo_dieu_phoi.py.
    """
    try:
        import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        dung_sl_tp_dong = getattr(Q, "DUNG_SL_TP_DONG", False)
        tf_override = getattr(Q, "SL_TP_TIME_FRAME", None)
    except ImportError:
        dung_sl_tp_dong = False
        tf_override = None

    if tf_override:
        time_frame = tf_override

    if dung_sl_tp_dong:
        return tinh_sl_tp(df, time_frame=time_frame, base_sl=base_sl, rr=rr)
    else:
        return tinh_sl_tp_co_dinh(df, base_sl=base_sl, rr=rr)


def tinh_sl_tp_live(df_15m, gia_vao, side, base_sl=2.5, rr=2.0, time_frame="15m"):
    """
    Tính giá dừng lỗ và chốt lời động theo ATR cho nến cuối cùng.
    `time_frame` đồng bộ với chip "SL/TP động" (mặc định 15m).
    Trả về (sl, tp) hoặc (None, None).
    """
    from Indicator.bien_dong import pt_atr
    import polars as pl
    if not hasattr(df_15m, "clone"):
        df_pl = pl.from_pandas(df_15m)
    else:
        df_pl = df_15m.clone()

    df_pl = pt_atr(df_pl, time_frame)
    if df_pl is None or df_pl.is_empty():
        return None, None

    atr = df_pl[f"atr_{time_frame}"][-1]
    atr_mean = df_pl[f"atr_mean_{time_frame}"][-1]

    if atr is None or atr <= 0:
        return None, None

    if atr_mean is None or atr_mean <= 0:
        vol_ratio = 1.0
    else:
        vol_ratio = atr / atr_mean

    vol_ratio = max(0.5, min(vol_ratio, 3.0))
    he_so_sl = base_sl * vol_ratio
    he_so_sl = max(1.0, min(he_so_sl, 5.0))
    he_so_tp = he_so_sl * rr

    sl_pct = (atr * he_so_sl) / gia_vao
    tp_pct = (atr * he_so_tp) / gia_vao

    sl_pct = max(0.005, min(sl_pct, 0.15))
    tp_pct = max(0.01, min(tp_pct, 0.30))

    if side == "buy":
        sl = gia_vao * (1 - sl_pct)
        tp = gia_vao * (1 + tp_pct)
    else:        
        sl = gia_vao * (1 + sl_pct)
        tp = gia_vao * (1 - tp_pct)

    return sl, tp


def tinh_sl_tp_theo_atr(gia_vao, tin_hieu, df_15m):
    """
    Wrapper function để đồng bộ import trong các file backtest cũ.
    """
    return tinh_sl_tp_live(df_15m=df_15m, gia_vao=gia_vao, side=tin_hieu, base_sl=2.5, rr=2.0)


