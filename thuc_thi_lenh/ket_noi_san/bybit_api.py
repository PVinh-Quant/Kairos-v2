"""
thuc_thi_lenh/ket_noi_san/bybit_api.py – Connector Bybit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wrapper CCXT cho Bybit. Module-level instance bybit_connector
được dùng trực tiếp khi cần gọi API Bybit đặc thù.
Phần lớn lệnh nên đi qua BoMayThucThi để hỗ trợ đa sàn.
"""

import ccxt
from utils.doc_cau_hinh import lay_cau_hinh_api
from utils.log import logger


class BybitAPI:
    """Wrapper kết nối Bybit qua CCXT, xử lý đặc thù leverage của Bybit."""

    def __init__(self):
        """Khởi tạo kết nối Bybit từ cấu hình API, gán None nếu không tìm thấy config."""
        configs = lay_cau_hinh_api()
        if "bybit" in configs:
            self.exchange = ccxt.bybit(configs["bybit"])
            self.exchange.load_markets()
        else:
            self.exchange = None

    def doi_don_bay(self, symbol, leverage):
        """Set đòn bẩy cho symbol trên Bybit, bỏ qua lỗi nếu leverage không thay đổi."""
        try:

            return self.exchange.set_leverage(leverage, symbol)
        except Exception as e:

            if "leverage not modified" not in str(e).lower():
                logger.error(f"Lỗi set leverage Bybit: {e}")
            return None


bybit_connector = BybitAPI()
