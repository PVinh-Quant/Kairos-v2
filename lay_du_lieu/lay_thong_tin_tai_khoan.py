"""
lay_du_lieu/lay_thong_tin_tai_khoan.py – Truy vấn tài khoản sàn
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cung cấp 2 hàm truy vấn trực tiếp sàn giao dịch:
  • lay_so_du_kha_dung() – số dư USDT có thể dùng để mở lệnh
  • lay_vi_the_hien_tai() – thông tin vị thế đang mở (side, size, entry, PnL)
"""

from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from utils.log import logger


def lay_so_du_kha_dung(ten_san, asset="USDT"):
    """Lấy số dư khả dụng (Free Balance) của một tài sản trên sàn."""
    exchange = quan_ly_san.lay_san(ten_san)
    if not exchange:
        return 0.0

    try:
        balance = exchange.fetch_balance()

        if "free" in balance and asset in balance["free"]:
            return float(balance["free"][asset])
        elif asset in balance:
            return float(balance[asset]["free"])
        else:
            return 0.0
    except Exception as e:
        logger.error(f"Lỗi lấy số dư {ten_san}: {e}")
        return 0.0


def lay_vi_the_hien_tai(ten_san, symbol):
    """Lấy thông tin vị thế đang mở của 1 cặp coin (side, amount, entry_price, unrealized_pnl)."""
    exchange = quan_ly_san.lay_san(ten_san)
    if not exchange:
        return None

    try:
        positions = exchange.fetch_positions([symbol])
        for pos in positions:
            if pos["symbol"] == symbol and float(pos["contracts"]) > 0:
                return {
                    "symbol": symbol,
                    "side": pos["side"],
                    "amount": float(pos["contracts"]),
                    "entry_price": float(pos["entryPrice"]),
                    "unrealized_pnl": float(pos["unrealizedPnl"]),
                }
        return None
    except Exception as e:
        logger.error(f"Lỗi lấy vị thế {symbol}: {e}")
        return None
