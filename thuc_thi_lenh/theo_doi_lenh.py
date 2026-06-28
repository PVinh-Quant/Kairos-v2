"""
thuc_thi_lenh/theo_doi_lenh.py – Theo dõi trạng thái vị thế đang mở
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Truy vấn sàn để lấy PnL%, entry price, và size thực tế của vị thế.
Dùng để phát hiện vị thế bị đóng ngoài hệ thống (bị thanh lý, đóng tay).
"""

from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from utils.log import logger


def kiem_tra_trang_thai_vi_the(san, symbol):
    """Truy vấn sàn lấy thông tin vị thế đang mở (pnl, side, entry, amount), trả về None nếu không có."""
    exchange = quan_ly_san.lay_san(san)
    if not exchange:
        return None

    try:
        positions = exchange.fetch_positions([symbol])
        for pos in positions:

            size = (
                float(pos["contracts"] or 0)
                if "contracts" in pos
                else float(pos["info"].get("size", 0))
            )
            if size > 0 and pos["symbol"] == symbol:
                return {
                    "pnl_percent": float(pos["percentage"]),
                    "pnl_amount": float(pos["unrealizedPnl"]),
                    "side": pos["side"],
                    "entry_price": float(pos["entryPrice"]),
                    "amount": size,
                }
        return None
    except Exception as e:
        logger.error(f"Lỗi theo dõi vị thế {symbol}: {e}")
        return None
