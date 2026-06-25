"""toi_uu/tien_ich.py — Đọc/ghi Data Pool, liệt kê symbol, helper số liệu/kết luận."""
import sys, os, json
from hien_thi.duong_dan import PROJECT_ROOT
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from toi_uu_hoa.kiem_dinh import danh_gia_guardrails, MIN_TRADES_OOS              
_DUONG_DAN_BO_DU_LIEU = os.path.join(PROJECT_ROOT, "du_lieu", "bo_du_lieu.json")
_THU_MUC_CACHE_OHLCV = os.path.join(PROJECT_ROOT, "du_lieu", "cache_ohlcv")
def doc_bo_du_lieu():
    """Đọc danh sách bộ dữ liệu đã lưu (mỗi phần tử: id/ten/symbols/tu_ngay/den_ngay)."""
    try:
        with open(_DUONG_DAN_BO_DU_LIEU, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) if isinstance(data, dict) else data
        return [d for d in items if isinstance(d, dict)]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def luu_bo_du_lieu(items):
    """Ghi danh sách bộ dữ liệu xuống du_lieu/bo_du_lieu.json."""
    try:
        os.makedirs(os.path.dirname(_DUONG_DAN_BO_DU_LIEU), exist_ok=True)
        with open(_DUONG_DAN_BO_DU_LIEU, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "items": items}, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def liet_ke_symbol_co_san():
    """Symbol có sẵn để chọn: quét folder cache_ohlcv ('BTC_USDT' → 'BTC/USDT');
    nếu trống thì fallback về cap_giao_dich trong config."""
    symbols = []
    try:
        for ten in sorted(os.listdir(_THU_MUC_CACHE_OHLCV)):
            if os.path.isdir(os.path.join(_THU_MUC_CACHE_OHLCV, ten)):
                symbols.append(ten.replace("_", "/"))
    except OSError:
        pass
    if not symbols:
        try:
            from utils.doc_cau_hinh import lay_cau_hinh_giao_dich
            symbols = list((lay_cau_hinh_giao_dich() or {}).get("cap_giao_dich", []))
        except Exception:                
            symbols = []
    return symbols


def _ticker_goc(syms):
    """['BNB/USDT','BTC/USDT'] → 'BNB · BTC' (bỏ /USDT trùng lặp cho gọn)."""
    return " · ".join(s.split("/")[0] for s in syms) if syms else "—"


def _so_ngay_khoang(tu, den):
    """Số ngày giữa hai mốc 'yyyy-mm-dd' (None nếu lỗi định dạng / âm)."""
    try:
        from datetime import datetime
        n = (datetime.strptime(str(den), "%Y-%m-%d") - datetime.strptime(str(tu), "%Y-%m-%d")).days
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None

def _safe_float(value, default=0.0):
    try:
        f = float(value)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _oos_thieu_lenh(res):
    """OOS không đủ lệnh để đánh giá: 0 lệnh, hoặc Sharpe = giá trị phạt (≤ -9.99)."""
    oos = (res or {}).get("oos_metrics", {}) or {}
    return _safe_float(oos.get("total_trades")) <= 1 or _safe_float(oos.get("sharpe_ratio")) <= -9.99


def ket_luan_chien_luoc(res):
    """DEPLOY / REJECT / NO_TRADE — uỷ quyền cho guardrails ở toi_uu_hoa.kiem_dinh."""
    return danh_gia_guardrails(res)["verdict"]


__all__ = ["doc_bo_du_lieu", "luu_bo_du_lieu", "liet_ke_symbol_co_san", "_ticker_goc",
           "_so_ngay_khoang", "_safe_float", "_oos_thieu_lenh", "ket_luan_chien_luoc",
           "_DUONG_DAN_BO_DU_LIEU", "_THU_MUC_CACHE_OHLCV"]
