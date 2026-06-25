"""
lay_du_lieu/lay_macro.py – Dữ liệu vĩ mô & tâm lý thị trường
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lấy 2 chỉ số macro dùng để lọc điều kiện thị trường:
  • Fear & Greed Index (alternative.me) – đo tâm lý đám đông 0-100
  • Open Interest (Binance Futures API)  – đo dòng tiền thực vào futures
"""

import requests
import pandas as pd


def lay_du_lieu_cam_xuc():
    """Lấy chỉ số Fear & Greed Index (0=extreme fear, 100=extreme greed). Trả về 50 nếu lỗi."""
    try:
        r = requests.get("https://api.alternative.me/fng/")
        data = r.json()
        return int(data["data"][0]["value"])
    except:
        return 50                                 


session = requests.Session()


def lay_du_lieu_io(symbol="BTC/USDT", period="5m", limit=30):
    """Lấy lịch sử Open Interest từ Binance Futures – dùng để xác nhận dòng tiền vào/ra."""
    symbol = symbol.replace("/", "")
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": period, "limit": limit}

    try:
                                                  
        response = session.get(url, params=params, timeout=5)

                                                                                     
        response.raise_for_status()

        data = response.json()
        df = pd.DataFrame(data)

                                                 
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["sumOpenInterest"] = df["sumOpenInterest"].astype(float)
            return df[["timestamp", "sumOpenInterest"]]

        return df

    except Exception as e:
        print(f"Lỗi khi trích xuất {symbol}: {e}")
        return pd.DataFrame()



