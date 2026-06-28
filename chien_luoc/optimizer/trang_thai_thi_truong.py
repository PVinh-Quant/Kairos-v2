"""
chien_luoc/logic_vectorized/trang_thai_thi_truong.py – Bộ lọc thị trường vectorized
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Thêm cột `trade_allowed` (bool) vào DataFrame. Backtest chỉ thực thi lệnh khi True.
Các điều kiện lọc:
  1. ML regime: loại regime 0 (Đóng_Băng) và 7 (Quét_Thanh_Khoản) – đồng nhất với bar-to-bar
  2. Giờ giao dịch: loại 5h sáng VN (giãn spread futures)
  3. Ngày: có thể bật lọc cuối tuần nếu cần
  4. Volume tối thiểu: loại nến có volume cực thấp (thị trường chết)
"""

import pandas as pd


TAT_CA_REGIME = set(range(8))



_REGIME_CAM_MAC_DINH = {0, 7}
_REGIME_KHONG_TRADE = set(_REGIME_CAM_MAC_DINH)


def dat_regime_cho_phep(allowed):
    """Đặt tập regime ĐƯỢC phép VÀO lệnh (id trong 0..7); các regime còn lại bị cấm.

    allowed=None → trả về mặc định (cấm 0 và 7). Đọc live trong
    loc_trang_thai_thi_truong nên có hiệu lực ngay cho cả vectorized lẫn bar-to-bar.
    """
    global _REGIME_KHONG_TRADE
    if allowed is None:
        _REGIME_KHONG_TRADE = set(_REGIME_CAM_MAC_DINH)
    else:
        _REGIME_KHONG_TRADE = TAT_CA_REGIME - {int(x) for x in allowed}
    return _REGIME_KHONG_TRADE


def lay_regime_cho_phep():
    """Trả list regime đang được phép VÀO lệnh (theo tập cấm module-global hiện tại).
    Dùng để LƯU vào file chiến lược (đồng bộ ra edge/live như sl_tp_time_frame...)."""
    return sorted(TAT_CA_REGIME - _REGIME_KHONG_TRADE)


def _tap_cam_tu_cho_phep(regime_cho_phep):
    """allowed list → set regime cấm. None → dùng tập cấm module-global hiện tại."""
    if regime_cho_phep is None:
        return _REGIME_KHONG_TRADE
    return TAT_CA_REGIME - {int(x) for x in regime_cho_phep}







_REGIME_CACHE = {}
_REGIME_CACHE_MAX = 32


def _van_tay_ohlcv(df_pl):
    """Khóa cache rẻ & ổn định cho 1 khối OHLCV (height + mốc thời gian + tổng/last close)."""
    try:
        if df_pl.height == 0:
            return None
        ts = df_pl["timestamp"]
        close = df_pl["close"]
        return (
            df_pl.height,
            str(ts[0]), str(ts[-1]),
            round(float(close.sum()), 4), round(float(close[-1]), 6),
        )
    except Exception:
        return None


def xoa_cache_regime():
    """Xóa cache regime ML (gọi khi nạp lại/huấn luyện lại mô hình trong cùng phiên)."""
    _REGIME_CACHE.clear()


def du_doan_trang_thai_thi_truong(df):
    """
    Dự đoán trạng thái bằng ML cho toàn bộ DataFrame (Vectorized) sử dụng Polars.
    Hỗ trợ cả Pandas và Polars DataFrame đầu vào.
    """
    try:
        import polars as pl
        from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml_vector

        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Thiếu các cột cần thiết để chạy ML: {missing}")

        is_pandas = not hasattr(df, "clone")
        if is_pandas:
            df_pl = pl.from_pandas(df[required_cols])
        else:
            df_pl = df.select(required_cols)


        van_tay = _van_tay_ohlcv(df_pl)
        df_regime = _REGIME_CACHE.get(van_tay) if van_tay is not None else None
        if df_regime is None:
            df_result = du_doan_trang_thai_ml_vector(df_pl)
            df_regime = df_result.select(["timestamp", "regime", "confidence"])
            if van_tay is not None:
                if len(_REGIME_CACHE) >= _REGIME_CACHE_MAX:
                    _REGIME_CACHE.pop(next(iter(_REGIME_CACHE)))
                _REGIME_CACHE[van_tay] = df_regime


        if is_pandas:
            import pandas as pd
            df_regime_pd = df_regime.to_pandas()
            df_regime_pd["timestamp"] = pd.to_datetime(df_regime_pd["timestamp"])
            df_temp = pd.DataFrame(
                {"timestamp": pd.to_datetime(df["timestamp"]), "index": df.index}
            )
            df_temp = df_temp.merge(df_regime_pd, on="timestamp", how="left")
            df_out = df.copy()
            df_out["regime"] = df_temp.set_index("index")["regime"].fillna(0).astype(int)
            df_out["confidence"] = df_temp.set_index("index")["confidence"].fillna(0.0)
            return df_out
        else:
            if df.schema["timestamp"] != df_regime.schema["timestamp"]:
                df_regime = df_regime.with_columns(pl.col("timestamp").cast(df.schema["timestamp"]))
            df_out = df.join(df_regime, on="timestamp", how="left")
            df_out = df_out.with_columns([
                pl.col("regime").fill_null(0).cast(pl.Int64),
                pl.col("confidence").fill_null(0.0)
            ])
            return df_out
    except Exception:
        if not hasattr(df, "clone"):
            df_out = df.copy()
            df_out["regime"] = 0
            df_out["confidence"] = 0.0
            return df_out
        else:
            return df.with_columns([
                pl.lit(0).cast(pl.Int64).alias("regime"),
                pl.lit(0.0).alias("confidence")
            ])


def loc_trang_thai_thi_truong(df, loc_cuoi_tuan=False, loc_gio_spread=True, regime_cho_phep=None):
    """
    df phải có cột `timestamp`. Trả về df với cột `trade_allowed` (bool).

    regime_cho_phep: list id regime ĐƯỢC phép vào lệnh (đọc từ chiến lược/JSON).
        None → dùng tập cấm module-global (mặc định 0 và 7, hoặc do dashboard đặt).
    """
    import polars as pl
    import pandas as pd

    is_pandas = not hasattr(df, "clone")
    if is_pandas:
        df_pl = pl.from_pandas(df)
    else:
        df_pl = df.clone()

    if "timestamp" not in df_pl.columns:
        df_pl = df_pl.with_columns(pl.lit(True).alias("trade_allowed"))
        return df_pl.to_pandas() if is_pandas else df_pl

    if "regime" not in df_pl.columns:
        df_pl = du_doan_trang_thai_thi_truong_vectorized(df_pl)

    trade_allowed = pl.lit(True)

    tap_cam = _tap_cam_tu_cho_phep(regime_cho_phep)
    if "regime" in df_pl.columns:
        trade_allowed = trade_allowed & (~pl.col("regime").is_in(tap_cam))

    if loc_gio_spread:
        ts_col = pl.col("timestamp")
        if df_pl.schema["timestamp"] in (pl.String, pl.Utf8):
            ts_col = ts_col.str.to_datetime()
        trade_allowed = trade_allowed & (ts_col.dt.hour() != 22)

    if loc_cuoi_tuan:
        ts_col = pl.col("timestamp")
        if df_pl.schema["timestamp"] in (pl.String, pl.Utf8):
            ts_col = ts_col.str.to_datetime()
        trade_allowed = trade_allowed & (ts_col.dt.weekday() <= 5)

    if "volume" in df_pl.columns:
        vol_mean = pl.col("volume").rolling_mean(window_size=200, min_periods=10)
        trade_allowed = trade_allowed & (pl.col("volume") > (vol_mean * 0.05))

    df_pl = df_pl.with_columns(trade_allowed.alias("trade_allowed"))

    return df_pl.to_pandas() if is_pandas else df_pl


du_doan_trang_thai_thi_truong_vectorized = du_doan_trang_thai_thi_truong


def pre_compute_regime(df_1m):
    """Pre-compute regime ML 1 lần trên toàn bộ df_1m gốc (Polars).

    Gọi hàm này MỘT LẦN DÀNH khi nạp data vào RAM trong optimizer, TRƯỚC khi
    chạy các trial. Cột ``regime`` và ``confidence`` sẽ được gắn sẵn → các hàm
    ``loc_trang_thai_thi_truong`` / ``chuan_hoa_va_loc_tin_hieu`` sẽ SKIP ML
    inference nhờ kiểm tra ``"regime" not in df.columns`` trả False.

    Args:
        df_1m: Polars DataFrame OHLCV gốc (chưa filter, chưa merge).

    Returns:
        Polars DataFrame giống df_1m nhưng có thêm cột ``regime`` (Int32)
        và ``confidence`` (Float64). Nếu ML thất bại → regime=0, confidence=0.
    """
    import polars as pl

    if "regime" in df_1m.columns:
        return df_1m

    try:
        from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml_vector

        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df_1m.columns]
        if missing:
            raise ValueError(f"Thiếu cột: {missing}")

        df_result = du_doan_trang_thai_ml_vector(df_1m.select(required))

        #
        df_regime = df_result.select(["timestamp", "regime", "confidence"])

        #
        cols_goc = [c for c in df_1m.columns if c not in ("regime", "confidence")]
        df_out = df_1m.select(cols_goc).join(df_regime, on="timestamp", how="left")
        df_out = df_out.with_columns([
            pl.col("regime").fill_null(0).cast(pl.Int32),
            pl.col("confidence").fill_null(0.0).cast(pl.Float64),
        ])
        return df_out

    except Exception as e:
        from utils.log import logger
        logger.warning(f"[Regime] Pre-compute thất bại ({e}), gán regime=0 mặc định.")
        return df_1m.with_columns([
            pl.lit(0).cast(pl.Int32).alias("regime"),
            pl.lit(0.0).cast(pl.Float64).alias("confidence"),
        ])
