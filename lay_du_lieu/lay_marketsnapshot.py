"""
lay_du_lieu/lay_marketsnapshot.py – WebSocket market data realtime
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Singleton KairosDataManager quản lý WebSocket đến Binance Futures.
Mỗi symbol subscribe 5 stream đồng thời:
  • aggTrade   – tích lũy CVD (Cumulative Volume Delta)
  • markPrice  – funding rate hiện tại
  • depth5     – order book top 5 → tính imbalance mua/bán
  • forceOrder – liquidation tách biệt long/short
  • bookTicker – spread bid/ask

Giao diện sử dụng đơn giản: mo_theo_doi() / dong_theo_doi()
"""

import websocket
import threading
import json
import time


class KairosDataManager:
    """
    Singleton thread-safe quản lý nhiều WebSocket connection.
    Mỗi connection xử lý tối đa 20 symbol để tránh giới hạn stream của Binance.
    Dữ liệu được cache trong self.cache[symbol] và truy cập không cần lock đọc.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Tạo hoặc trả về instance singleton của KairosDataManager."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KairosDataManager, cls).__new__(cls)
                cls._instance.cache = {}
                cls._instance.symbol_to_conn = {}                                   
                cls._instance.connections = (
                    []
                )                                                            
                cls._instance.is_stopping = False
            return cls._instance

    def _init_symbol_cache(self, symbol):
        """Khởi tạo cấu trúc cache rỗng cho một symbol mới."""
        if symbol not in self.cache:
            self.cache[symbol] = {
                "funding_rate": 0.0,
                "liq_long": 0.0,
                "liq_short": 0.0,
                "delta": 0.0,
                "buy_vol": 0.0,
                "sell_vol": 0.0,
                                         
                "spread_hist": [],
                "bid_hist": [],
                "ask_hist": [],
                "bid_sz_hist": [],
                "ask_sz_hist": [],
                                           
                "depth_bid": [],
                "depth_ask": [],
                "bid_total": 0.0,
                "ask_total": 0.0,
                "imbalance": 0.0,
            }

    def _safe_close(self, ws):
        """Đóng WebSocket an toàn, bỏ qua mọi lỗi."""
        if ws and hasattr(ws, "sock") and ws.sock:
            try:
                ws.close()
            except:
                pass

    def on_message(self, ws, message):
        """Xử lý message đến từ WebSocket và cập nhật cache tương ứng."""
        try:
            raw = json.loads(message)
            stream = raw.get("stream", "")
            data = raw.get("data", {})

                                                                              
            if "@forceOrder" in stream:
                symbol = data.get("o", {}).get("s", "").upper()
            else:
                symbol = data.get("s", "").upper()

            if not symbol or symbol not in self.cache:
                return

            with self._lock:
                target = self.cache[symbol]

                if "@forceOrder" in stream:
                    o = data["o"]
                    qty = float(o["q"])
                                                                                            
                    if o["S"] == "SELL":
                        target["liq_long"] += qty
                    else:
                        target["liq_short"] += qty

                elif "@aggTrade" in stream:
                    qty = float(data["q"])
                    if data["m"]:
                        target["sell_vol"] += qty
                    else:
                        target["buy_vol"] += qty
                    target["delta"] = target["buy_vol"] - target["sell_vol"]

                elif "@markPrice" in stream:
                    target["funding_rate"] = float(data.get("r", 0))

                elif "@depth5" in stream:
                    bids = data.get("b", [])
                    asks = data.get("a", [])
                    bid_total = sum(float(x[1]) for x in bids)
                    ask_total = sum(float(x[1]) for x in asks)

                    target["depth_bid"] = bids
                    target["depth_ask"] = asks
                    target["bid_total"] = bid_total
                    target["ask_total"] = ask_total

                    if bid_total + ask_total > 0:
                        target["imbalance"] = (bid_total - ask_total) / (
                            bid_total + ask_total
                        )
        except:
            pass

    def _manage_connection(self, conn_idx):
        """Vòng lặp duy trì kết nối WebSocket, tự động reconnect khi mất kết nối."""
        while not self.is_stopping:
            with self._lock:
                symbols = list(self.connections[conn_idx]["symbols"])
                if not symbols:
                    self.connections[conn_idx]["ws"] = None
                    break

                                                            
                streams = []
                for s in symbols:
                    s_low = s.lower()
                    streams.extend(
                        [
                            f"{s_low}@aggTrade",
                            f"{s_low}@bookTicker",
                            f"{s_low}@depth5@100ms",
                            f"{s_low}@forceOrder",
                            f"{s_low}@markPrice@1s",
                        ]
                    )

                url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

            ws = websocket.WebSocketApp(url, on_message=self.on_message)
            self.connections[conn_idx]["ws"] = ws
            ws.run_forever()
            time.sleep(2)

    def add_symbol(self, symbol):
        """Thêm symbol vào quản lý, tạo connection mới nếu cần."""
        symbol = symbol.upper()
        if symbol in self.symbol_to_conn:
            return

        with self._lock:
            self._init_symbol_cache(symbol)
            target_idx = -1
            for i, conn in enumerate(self.connections):
                if len(conn["symbols"]) < 20:
                    target_idx = i
                    break

            if target_idx == -1:
                target_idx = len(self.connections)
                self.connections.append(
                    {"ws": None, "symbols": {symbol}, "thread": None}
                )
                t = threading.Thread(
                    target=self._manage_connection, args=(target_idx,), daemon=True
                )
                self.connections[target_idx]["thread"] = t
                t.start()
            else:
                self.connections[target_idx]["symbols"].add(symbol)
                self._safe_close(self.connections[target_idx]["ws"])

            self.symbol_to_conn[symbol] = target_idx

    def remove_symbol(self, symbol):
        """Xóa symbol khỏi quản lý và dọn sạch cache."""
        symbol = symbol.upper()
        if symbol not in self.symbol_to_conn:
            return
        with self._lock:
            conn_idx = self.symbol_to_conn[symbol]
            self.connections[conn_idx]["symbols"].remove(symbol)
            del self.symbol_to_conn[symbol]
            if symbol in self.cache:
                del self.cache[symbol]
            self._safe_close(self.connections[conn_idx]["ws"])


                                            
                   
                                            


def mo_theo_doi(cap_giao_dich):
    """Bắt đầu theo dõi WebSocket cho một cặp giao dịch, trả về cache dict."""
    symbol = cap_giao_dich.replace("/", "").upper()
    manager = KairosDataManager()
    if symbol not in manager.symbol_to_conn:
        manager.add_symbol(symbol)
    return manager.cache.get(symbol, {})


def dong_theo_doi(cap_giao_dich):
    """Dừng theo dõi WebSocket và giải phóng tài nguyên cho một cặp giao dịch."""
    symbol = cap_giao_dich.replace("/", "").upper()
    KairosDataManager().remove_symbol(symbol)


if __name__ == "__main__":
    raw_list = [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "DOGE/USDT",
        "ADA/USDT",
        "MATIC/USDT",
        "DOT/USDT",
        "LINK/USDT",
        "AVAX/USDT",
        "SHIB/USDT",
        "PEPE/USDT",
        "LTC/USDT",
        "NEAR/USDT",
    ]

    try:
        while True:
            for pair in raw_list:
                pair_data = mo_theo_doi(pair)
                                                                  
                if pair_data:
                    print(pair_data)
                time.sleep(1)
    except KeyboardInterrupt:
        for pair in raw_list:
            dong_theo_doi(pair)
