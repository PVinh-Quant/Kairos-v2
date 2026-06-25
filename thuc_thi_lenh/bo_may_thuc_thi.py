"""
thuc_thi_lenh/bo_may_thuc_thi.py – Quản lý kết nối các sàn giao dịch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Singleton BoMayThucThi khởi tạo và giữ kết nối CCXT đến tất cả sàn
được cấu hình trong config/tai_khoan_api.json (Binance, OKX, Bybit).

Module-level instance `quan_ly_san` được import ở mọi nơi cần thực thi lệnh
thay vì tạo kết nối mới mỗi lần – tránh overhead và rate limit.
"""

import ccxt
from utils.doc_cau_hinh import lay_cau_hinh_api
from utils.log import logger


class BoMayThucThi:
    """Quản lý pool kết nối CCXT. Khởi tạo 1 lần, dùng lại xuyên suốt phiên giao dịch."""

    def __init__(self):
        """Đọc cấu hình API và khởi tạo kết nối tới tất cả sàn được cấu hình."""
        self.configs = lay_cau_hinh_api()
        self.exchanges = {}
        self.khoi_tao_ket_noi()

    def khoi_tao_ket_noi(self):
        """Khởi tạo kết nối CCXT cho từng sàn trong config, bỏ qua nếu đã kết nối."""
        for san, config in self.configs.items():
            if san in self.exchanges:
                logger.info(f"Sàn {san} đã được kết nối trước đó. Bỏ qua.")
                continue
            try:
                if san == "binance":
                    self.exchanges[san] = ccxt.binance(config)
                elif san == "okx":
                    self.exchanges[san] = ccxt.okx(config)
                elif san == "bybit":
                    self.exchanges[san] = ccxt.bybit(config)
                self.exchanges[san].load_markets()
            except Exception as e:
                logger.error(f"Lỗi kết nối sàn {san}: {e}")

    def lay_san(self, ten_san):
        """Lấy object exchange CCXT theo tên sàn, trả về None nếu không tìm thấy."""
        return self.exchanges.get(ten_san)

    def mo_lenh_market(self, ten_san, symbol, side, amount, leverage, set_lev=True):
        """Đặt lệnh market, tự set leverage trước nếu set_lev=True."""
        exchange = self.lay_san(ten_san)
        if not exchange:
            return None
        try:
            if set_lev:
                try:
                    exchange.set_leverage(leverage, symbol)
                except:
                    pass
                                     
            order = exchange.create_order(symbol, "market", side, amount)
            logger.info(
                f"KHỚP LỆNH {side.upper()} {symbol} trên {ten_san}. ID: {order['id']}"
            )
            return order
        except Exception as e:
            logger.error(f"Lỗi mở lệnh: {e}")
            return None

    def dong_vi_the(self, ten_san, symbol, side_hien_tai, amount):
        """Đóng vị thế bằng cách đặt lệnh ngược chiều với reduceOnly."""
        side_dong = "sell" if side_hien_tai == "buy" else "buy"
        return self.mo_lenh_market(ten_san, symbol, side_dong, amount, 0, set_lev=False)


quan_ly_san = BoMayThucThi()
