"""
chien_luoc/optimizer/loc_tin_hieu.py — NGUỒN SỰ THẬT CHUNG cho lọc tín hiệu thị trường
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dùng CHUNG cho cả vectorized backtest (`tong_hop_tin_hieu`) lẫn optimizer (`bo_dieu_phoi`),
để cả hai pipeline có CÙNG hành vi lọc — tránh lệch kết quả backtest vs tối ưu hoá.

Một hàm `chuan_hoa_va_loc_tin_hieu(df)` thực hiện đúng 3 việc, theo thứ tự:
  1. Lưu `signal_raw` = tín hiệu THÔ (trước lọc) → engine khớp lệnh dùng cho điều kiện
     THOÁT theo tín hiệu đảo chiều (giống live: vẫn thoát dù nến đang bị cấm VÀO lệnh).
  2. Thêm cột `trade_allowed` qua `loc_trang_thai_thi_truong`
     (giờ spread / volume thấp / cuối tuần / ML regime cấm).
  3. ZERO `signal` (và `entry_signal` nếu có) ở nến `trade_allowed=False` — chỉ chặn VÀO
     lệnh; KHÔNG đụng `signal_raw`.

`dung_regime_ml=False` (mặc định, chế độ union): ép `regime=-1` để KHÔNG chạy mô hình ML,
chỉ lọc theo giờ/volume — đúng như vectorized union mode. Bật True để dùng ML regime.

Hỗ trợ cả Polars và Pandas (vào sao trả ra vậy).

➕ MỞ RỘNG: muốn thêm bộ lọc mới (vd lọc theo spread thật, theo tin tức…), CHỈ sửa ở đây
   → cả backtest lẫn optimizer tự đồng bộ.
"""

import polars as pl

from chien_luoc.optimizer.trang_thai_thi_truong import loc_trang_thai_thi_truong


def chuan_hoa_va_loc_tin_hieu(
    df,
    *,
    dung_regime_ml: bool = False,
    loc_gio_spread: bool = True,
    loc_cuoi_tuan: bool = False,
    regime_cho_phep=None,
):
    """Chuẩn hoá + lọc tín hiệu thị trường. Yêu cầu df đã có cột `signal`.

    Args:
        df: DataFrame (Polars/Pandas) đã có cột `signal` (và tuỳ chọn `entry_signal`).
        dung_regime_ml: True → cho phép `loc_trang_thai_thi_truong` dự đoán ML regime.
                        False (mặc định) → ép regime=-1 (union), chỉ lọc giờ/volume.
        loc_gio_spread: lọc khung giờ spread cao (mặc định True).
        loc_cuoi_tuan: lọc cuối tuần (mặc định False).
        regime_cho_phep: list id regime ĐƯỢC phép vào lệnh (đọc từ chiến lược/JSON);
                         None → dùng tập cấm mặc định/module-global.

    Returns:
        DataFrame cùng kiểu đầu vào, có thêm `signal_raw`, `trade_allowed`, và `signal`
        (`entry_signal`) đã được zero ở nến bị cấm.
    """
    is_pandas = not hasattr(df, "clone")
    df_pl = pl.from_pandas(df) if is_pandas else df.clone()

    if "signal" not in df_pl.columns:
        return df_pl.to_pandas() if is_pandas else df_pl

                                                                   
    if "signal_raw" not in df_pl.columns:
        df_pl = df_pl.with_columns(pl.col("signal").alias("signal_raw"))

                                                                        
    if not dung_regime_ml and "regime" not in df_pl.columns:
        df_pl = df_pl.with_columns(pl.lit(-1).cast(pl.Int64).alias("regime"))

                               
    df_pl = loc_trang_thai_thi_truong(
        df_pl, loc_cuoi_tuan=loc_cuoi_tuan, loc_gio_spread=loc_gio_spread,
        regime_cho_phep=regime_cho_phep,
    )

                                                                                        
    if "trade_allowed" in df_pl.columns:
        cols = [
            pl.when(pl.col("trade_allowed")).then(pl.col("signal")).otherwise(0).alias("signal")
        ]
        if "entry_signal" in df_pl.columns:
            cols.append(
                pl.when(pl.col("trade_allowed")).then(pl.col("entry_signal")).otherwise(0).alias("entry_signal")
            )
        df_pl = df_pl.with_columns(cols)

    return df_pl.to_pandas() if is_pandas else df_pl
