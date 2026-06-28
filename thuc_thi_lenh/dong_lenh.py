"""
thuc_thi_lenh/dong_lenh.py – Đóng vị thế an toàn
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dùng reduceOnly=True để đảm bảo lệnh chỉ đóng vị thế, không mở ngược.
OKX/Bybit Hedge Mode cần thêm posSide (long/short) – xử lý riêng tại đây.
"""

from thuc_thi_lenh.mo_lenh import thuc_hien_mo_lenh
from utils.log import logger


def thuc_hien_dong_lenh(san, symbol, side_hien_tai, khoi_luong):
    """Đóng vị thế an toàn cho cả Binance (One-way) và OKX/Bybit (Hedge Mode)."""
    side_dong = "sell" if side_hien_tai == "buy" else "buy"


    params = {"reduceOnly": True}

    if san in ["okx", "bybit"]:
        if side_hien_tai == "buy":
            params["posSide"] = "long"
        else:
            params["posSide"] = "short"

    logger.info(
        f"Đóng lệnh {side_hien_tai.upper()} {symbol} trên {san} (Params: {params})..."
    )

    return thuc_hien_mo_lenh(san, symbol, side_dong, khoi_luong, params=params)
