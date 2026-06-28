"""
chien_luoc/user_strategies/vi_du_rsi_ema_trend.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PLUGIN VÍ DỤ — "RSI đảo chiều THEO xu hướng EMA đa khung".

Logic (không làm được bằng combo AND template đơn thuần):
  • Tính RSI ở khung vào lệnh (mặc định 5m) + EMA ở khung lọc xu hướng (mặc định 1h).
  • Chỉ MUA khi RSI cắt LÊN khỏi vùng quá bán VÀ giá đang trên EMA khung lớn (mua đáy
    trong xu hướng tăng) → tránh bắt dao rơi.
  • Chỉ BÁN khi RSI cắt XUỐNG khỏi vùng quá mua VÀ giá đang dưới EMA khung lớn.
  • Giữ vị thế (forward-fill) tới khi có tín hiệu đảo chiều ngược lại.

Đây là file mẫu minh họa cách viết plugin: chỉ cần hiện thực `sinh_tin_hieu`
và khai báo `khong_gian_tham_so`. Xóa file này không ảnh hưởng hệ thống.
"""

from chien_luoc.base_strategy import ChienLuocPluginCoSo
from Indicator.dong_luong_dao_chieu import pt_rsi
from Indicator.xu_huong import pt_ema_trend


class RSIDaoChieuTheoTrendEMA(ChienLuocPluginCoSo):
    ten = "RSI đảo chiều theo trend EMA"
    mo_ta = "Mua đáy RSI trong xu hướng tăng EMA, bán đỉnh RSI trong xu hướng giảm (đa khung)."
    nhom = "Chiến lược plugin"


    khung_vao = "5m"
    khung_loc = "1h"

    def khong_gian_tham_so(self):
        return [
            {"ten": "rsi_window",  "kieu": "int", "thap": 5,  "cao": 30},
            {"ten": "oversold",    "kieu": "int", "thap": 15, "cao": 40},
            {"ten": "overbought",  "kieu": "int", "thap": 60, "cao": 85},
            {"ten": "ema_window",  "kieu": "int", "thap": 20, "cao": 120},
        ]

    def sinh_tin_hieu(self, df, tf_map=None, params=None):
        import polars as pl

        p = {**self.get_default_params(), **(params or {})}
        rsi_w = int(p["rsi_window"])
        ema_w = int(p["ema_window"])
        oversold = p["oversold"]
        overbought = p["overbought"]

        is_pandas = not hasattr(df, "clone")
        d = pl.from_pandas(df) if is_pandas else df.clone()


        d = pt_rsi(d, self.khung_vao, window=rsi_w)
        d = pt_ema_trend(d, self.khung_loc, window=ema_w)

        rsi_col = f"rsi_{self.khung_vao}"
        ema_col = f"ema_{ema_w}_{self.khung_loc}"
        if rsi_col not in d.columns or ema_col not in d.columns:
            d = d.with_columns(pl.lit(0).cast(pl.Int64).alias("signal"))
            return d.to_pandas() if is_pandas else d

        rsi = pl.col(rsi_col)
        rsi_prev = pl.col(rsi_col).shift(1)
        trend_up = pl.col("close") > pl.col(ema_col)
        trend_dn = pl.col("close") < pl.col(ema_col)

        entry_long = (rsi_prev < oversold) & (rsi >= oversold) & trend_up
        entry_short = (rsi_prev > overbought) & (rsi <= overbought) & trend_dn

        d = d.with_columns(
            pl.when(entry_long).then(1).when(entry_short).then(-1).otherwise(0).alias("signal")
        )

        d = d.with_columns(
            pl.when(pl.col("signal") == 0).then(None).otherwise(pl.col("signal"))
            .forward_fill().fill_null(0).cast(pl.Int64).alias("signal")
        )
        return d.to_pandas() if is_pandas else d
