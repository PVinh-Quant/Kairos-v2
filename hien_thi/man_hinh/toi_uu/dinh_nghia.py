"""toi_uu/dinh_nghia.py — Hằng số: danh mục chỉ báo, khung TG, mô-đun, regime, vốn nền."""
import sys, os
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


try:
    from utils.doc_cau_hinh import lay_cau_hinh_ao
    SO_DU_BAN_DAU = float(lay_cau_hinh_ao().get("so_du_ban_dau", 10000) or 10000)
except Exception:
    SO_DU_BAN_DAU = 10000.0
CATEGORIES = {
    "Momentum / Dao động": ["rsi", "stochastic", "mfi", "ultimate", "stoch_rsi", "stc"],
    "Volatility / Dải băng": ["bollinger", "keltner", "donchian", "atr_bands", "chandelier_exit", "choppiness"],
    "Trend / Xu hướng": ["ema", "sma", "adx", "supertrend", "macd", "psar", "aroon", "vortex", "hma", "kama", "alma", "vwma"],
    "Volume / Khối lượng": ["volume", "obv", "vwap", "cmf", "mfi_volume", "pvt", "chaikin_oscillator"],
    "Market Structure / Cấu trúc giá": ["fractals"],
    "Sentiment & Positioning / Vị thế": ["elder_ray"],
}

INDICATOR_DESC = {
    "rsi": "Chỉ số sức mạnh tương đối", "stochastic": "Dao động Stochastic",
    "mfi": "Chỉ số dòng tiền",
    "ultimate": "Ultimate Oscillator", "bollinger": "Bollinger Bands", "keltner": "Keltner Channel",
    "donchian": "Donchian Channel", "atr_bands": "Dải ATR", "ema": "Trung bình mũ",
    "sma": "Trung bình đơn giản", "adx": "Chỉ số định hướng TB", "supertrend": "Supertrend",
    "macd": "MACD", "psar": "Parabolic SAR", "aroon": "Aroon", "vortex": "Vortex",
    "volume": "Khối lượng", "obv": "On-Balance Volume", "vwap": "Giá TB theo khối lượng",
    "cmf": "Chaikin Money Flow", "mfi_volume": "MFI theo khối lượng",
    "fractals": "Fractals",

    "stoch_rsi": "Stochastic RSI",
    "stc": "Schaff Trend Cycle",
    "chandelier_exit": "Chandelier Exit",
    "choppiness": "Choppiness Index", "hma": "Hull Moving Average",
    "kama": "Kaufman Adaptive MA",
    "alma": "Arnaud Legoux MA", "vwma": "Volume Weighted MA",
    "pvt": "Price Volume Trend", "chaikin_oscillator": "Chaikin Oscillator",
    "elder_ray": "Elder Ray (Bull/Bear Power)",
}



try:
    from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY as _REG
    _da_liet_ke = {k for ks in CATEGORIES.values() for k in ks}
    _con_thieu = [k for k in _REG.keys() if k not in _da_liet_ke]
    if _con_thieu:
        CATEGORIES.setdefault("Khác / Chưa phân loại", []).extend(_con_thieu)
    for k in _REG.keys():
        INDICATOR_DESC.setdefault(k, k.replace("_", " ").title())
except Exception:
    pass

ALL_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]




MODULE_DEFS = {
    "regime":  {"name": "Regime ML",    "flag": "DUNG_REGIME_MAC_DINH", "desc": "ML lọc nến theo trạng thái thị trường — chọn các trạng thái được vào lệnh"},
    "sl_tp":   {"name": "SL/TP động",   "flag": "DUNG_SL_TP_DONG",      "desc": "SL/TP động theo ATR — chỉnh khung ATR & khoảng dò base_sl/rr"},
    "don_bay": {"name": "Đòn bẩy động", "flag": "DUNG_DON_BAY_DONG",    "desc": "Đòn bẩy theo điều kiện thị trường — chỉnh đòn bẩy gốc/trần/khung"},
}




REGIME_STATES = [
    (0, "Đóng băng"),
    (1, "Nén chặt"),
    (2, "Đầu xu hướng"),
    (3, "Xu hướng mạnh"),
    (4, "Cao trào"),
    (5, "Hồi quy"),
    (6, "Nhiễu động"),
    (7, "Quét thanh khoản"),
]
REGIME_ALLOWED_DEFAULT = [1, 2, 3, 4, 5, 6]


DEFAULT_MODULE_PARAMS = {
    "regime":  {"allowed": list(REGIME_ALLOWED_DEFAULT)},
    "sl_tp":   {"tf": "Tự động", "sl_min": 1.0, "sl_max": 5.0, "rr_min": 1.2, "rr_max": 4.0},
    "don_bay": {"goc": 5, "max_lev": 50, "tf": "15m"},
}


__all__ = ["CATEGORIES", "INDICATOR_DESC", "ALL_TIMEFRAMES", "MODULE_DEFS",
           "REGIME_STATES", "REGIME_ALLOWED_DEFAULT", "DEFAULT_MODULE_PARAMS", "SO_DU_BAN_DAU"]
