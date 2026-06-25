"""
chien_luoc/quan_ly_chien_luoc_bar_to_bar.py – Điều phối chiến lược bar-to-bar
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVALUATOR BAR-TO-BAR NATIVE — đồng bộ LOGIC với vectorized_backtest nhưng
INPUT khác: bar-to-bar dùng 8 khung ĐÃ GỘP SẴN (df_1m..df_1d).
"""

import os
import glob
import polars as pl
from utils.log import logger
from chien_luoc.json_strategy import JSONStrategy
from utils.doc_cau_hinh import lay_cau_hinh_giao_dich

_config_trade = lay_cau_hinh_giao_dich() or {}

                                               
DUNG_SL_TP_DONG = False
DUNG_DON_BAY_DONG = False
DON_BAY_CO_DINH = int(_config_trade.get("don_bay", 5))
BASE_SL_DEFAULT = 2.5
RR_DEFAULT = 2.0

                                                       
JSON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "du_lieu", "danh_sach_chien_luoc",
)
STRATEGIES = {}
if os.path.exists(JSON_DIR):
    list_kich_hoat = _config_trade.get("chien_luoc_kich_hoat") or []
    if not isinstance(list_kich_hoat, list):
        list_kich_hoat = [list_kich_hoat]
    list_kich_hoat_lower = [str(x).strip().lower() for x in list_kich_hoat if x]

    for f in glob.glob(os.path.join(JSON_DIR, "*.json")):
        try:
            filename = os.path.splitext(os.path.basename(f))[0].lower()
            strat = JSONStrategy(f)
            strat_name = strat.name.lower()

                                                                                                     
            is_rejected = "vd_reject" in filename

                                                                                             
            strat_config = strat.config or {}
            is_active_field = strat_config.get("active", True)
            status_field = str(strat_config.get("status", "")).lower()
            is_disabled_internal = (is_active_field is False) or (status_field in ("inactive", "reject"))

            if is_disabled_internal:
                logger.info(f"[bar-to-bar] Bỏ qua chiến lược {strat.name} (bị tắt bên trong cấu hình JSON hoặc status={status_field})")
                continue

                                                                                                      
            if list_kich_hoat_lower:
                name_matches = (strat_name in list_kich_hoat_lower) or (filename in list_kich_hoat_lower)
                if not name_matches:
                    continue
            else:
                if is_rejected:
                    logger.info(f"[bar-to-bar] Bỏ qua chiến lược {strat.name} (chứa vd_REJECT trong tên file)")
                    continue

            STRATEGIES[strat_name] = strat
            logger.info(f"[bar-to-bar] Đã nạp thành công chiến lược: {strat.name}")
        except Exception as e:
            logger.error(f"Lỗi load JSON strategy {f} ở bar-to-bar: {e}")
else:
    logger.warning(f"Thư mục chứa chiến lược JSON không tồn tại: {JSON_DIR}")


def dat_chien_luoc_ghi_de(config, ten="active"):
    """GHI ĐÈ engine: `STRATEGIES` chỉ còn DUY NHẤT 1 chiến lược dựng từ `config`.

    Dùng khi người dùng chạy LẺ 1 chiến lược chọn từ thư viện "Đã lưu" (Realtime/Demo/
    Backtest) — bỏ qua mọi bộ lọc REJECT/active/kích_hoạt vì người dùng đã CHỦ ĐỘNG chọn.
    `config` = dict best_params (các spec s0/s1.. + logic + risk). Trả JSONStrategy / None.

    Lưu ý vòng đời: các runner (chay_realtime/chay_demo/chay_backtest) tra cứu biến
    toàn cục `STRATEGIES` tại thời điểm gọi, nên việc gán lại ở đây có hiệu lực ngay
    cho luồng nền khởi động SAU lời gọi này (cùng tiến trình).
    """
    global STRATEGIES
    if not config:
        return None
    import json as _json
    import tempfile
    try:
        safe = "".join(c for c in str(ten) if c.isalnum() or c in "._-") or "active"
        fd, path = tempfile.mkstemp(suffix=".json", prefix=f"cl_{safe}_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(config, f, ensure_ascii=False)
        strat = JSONStrategy(path)
        try:
            os.remove(path)                                                            
        except OSError:
            pass
        STRATEGIES = {strat.name.lower(): strat}
        logger.info(f"[bar-to-bar] GHI ĐÈ chiến lược (chạy lẻ từ thư viện): {strat.name}")
        return strat
    except Exception as e:
        logger.error(f"[bar-to-bar] Lỗi ghi đè chiến lược '{ten}': {e}")
        return None


def _to_pl(frame):
    """Chuẩn hóa về Polars DataFrame (None giữ nguyên)."""
    if frame is None:
        return None
    return frame if hasattr(frame, "clone") else pl.from_pandas(frame)


def _danh_gia_strat_now(strat, frames_by_tf):
    """Đánh giá 1 JSONStrategy tại NẾN HIỆN TẠI trên các khung đã gộp. Trả -1/0/1."""
    if getattr(strat, "_is_plugin", False):
        return 0                                                     

    df_1m = frames_by_tf.get("1m")
    df_3m = frames_by_tf.get("3m")
    df_5m = frames_by_tf.get("5m")
    df_15m = frames_by_tf.get("15m")
    df_30m = frames_by_tf.get("30m")
    df_1h = frames_by_tf.get("1h")
    df_4h = frames_by_tf.get("4h")
    df_1d = frames_by_tf.get("1d")

    try:
        tin_hieu, _, _ = strat.phan_tich_live(
            symbol="",
            df_1m=df_1m,
            df_3m=df_3m,
            df_5m=df_5m,
            df_15m=df_15m,
            df_30m=df_30m,
            df_1h=df_1h,
            df_4h=df_4h,
            df_1d=df_1d,
        )
        if tin_hieu == "buy":
            return 1
        if tin_hieu == "sell":
            return -1
    except Exception as e:
        logger.error(f"[bar-to-bar] lỗi đánh giá chiến lược {strat.name}: {e}")
    return 0


def _trade_allowed_now(df_1m, use_ml=False, regime_cho_phep=None):
    """Lọc trạng thái thị trường trên df_1m (regime=-1 = union) → bool nến cuối.
    regime_cho_phep: list trạng thái được phép (đọc từ JSON chiến lược)."""
    try:
        from chien_luoc.optimizer.trang_thai_thi_truong import loc_trang_thai_thi_truong
        df = _to_pl(df_1m)
        if df is None or df.is_empty():
            return True
        if not use_ml and "regime" not in df.columns:
            df = df.with_columns(pl.lit(-1).cast(pl.Int64).alias("regime"))
        df = loc_trang_thai_thi_truong(df, regime_cho_phep=regime_cho_phep)
        if "trade_allowed" in df.columns and df.height > 0:
            return bool(df["trade_allowed"][-1])
    except Exception as e:                
        logger.error(f"[bar-to-bar] lỗi trade_allowed: {e}")
    return True


def danh_gia_tin_hieu_bar(symbol, frames_by_tf):
    """Đánh giá tín hiệu từ các chiến lược cấu hình JSON tại nến hiện tại."""
    if not STRATEGIES:
        return {
            "signal": 0,
            "signal_raw": 0,
            "sl_pct": BASE_SL_DEFAULT / 100.0,
            "tp_pct": (BASE_SL_DEFAULT * RR_DEFAULT) / 100.0,
            "leverage": DON_BAY_CO_DINH,
            "regime": -1,
            "trade_allowed": True,
            "strategy_name": "none",
            "use_ml": False,
        }

    signal_raw = 0
    selected_strat = None
    strategy_name = "union"

                                                             
    for strat in STRATEGIES.values():
        s = _danh_gia_strat_now(strat, frames_by_tf)
        if s != 0:
            signal_raw = s
            selected_strat = strat
            strategy_name = strat.name
            break

    if selected_strat is None:
        selected_strat = list(STRATEGIES.values())[0]

                                                                     
    use_sl_tp_dong = (
        bool(selected_strat.config.get("dung_sl_tp_dong", False)) or
        bool(selected_strat.risk.get("dung_sl_tp_dong", False)) or
        bool(selected_strat.config.get("use_sl_tp_dong", False)) or
        bool(selected_strat.risk.get("use_sl_tp_dong", False))
    )
    use_don_bay_dong = (
        bool(selected_strat.config.get("dung_don_bay_dong", False)) or
        bool(selected_strat.risk.get("dung_don_bay_dong", False)) or
        bool(selected_strat.config.get("use_don_bay_dong", False)) or
        bool(selected_strat.risk.get("use_don_bay_dong", False))
    )
    use_ml = (
        bool(selected_strat.config.get("dung_ml", False)) or
        bool(selected_strat.logic.get("dung_ml", False)) or
        bool(selected_strat.config.get("use_ml", False)) or
        bool(selected_strat.logic.get("use_ml", False))
    )
                                                                                        
    regime_cho_phep = None
    for _src in (selected_strat.logic, selected_strat.config, selected_strat.risk):
        if isinstance(_src, dict) and _src.get("regime_cho_phep") is not None:
            try:
                regime_cho_phep = [int(x) for x in _src["regime_cho_phep"]]
            except (TypeError, ValueError):
                regime_cho_phep = None
            break

    df_15m = frames_by_tf.get("15m")
    df_1m = frames_by_tf.get("1m")

                        
    base_sl = float(selected_strat.risk.get("base_sl", BASE_SL_DEFAULT))
    rr = float(selected_strat.risk.get("rr", RR_DEFAULT))
                                                                          
    sl_tp_tf = (selected_strat.risk.get("sl_tp_time_frame")
                or selected_strat.config.get("sl_tp_time_frame") or "15m")

    df15 = _to_pl(df_15m)
    if use_sl_tp_dong and df15 is not None and not df15.is_empty():
        try:
            from chien_luoc.optimizer.stoploss_takeprofit import tinh_sl_tp_live
            sl_frame = _to_pl(frames_by_tf.get(sl_tp_tf))
            if sl_frame is None or sl_frame.is_empty():
                sl_frame = df15
                                                                                              
            close = float(sl_frame["close"][-1])
            sl_p, tp_p = tinh_sl_tp_live(sl_frame, close, "buy", base_sl=base_sl, rr=rr, time_frame=sl_tp_tf)
            if sl_p and tp_p and close > 0:
                sl_pct = abs(close - sl_p) / close
                tp_pct = abs(tp_p - close) / close
            else:
                sl_pct = base_sl / 100.0
                tp_pct = (base_sl * rr) / 100.0
        except Exception as e:
            logger.error(f"[bar-to-bar] lỗi tính SL/TP động: {e}")
            sl_pct = base_sl / 100.0
            tp_pct = (base_sl * rr) / 100.0
    else:
        sl_pct = base_sl / 100.0
        tp_pct = (base_sl * rr) / 100.0

                          
    fixed_leverage = int(
        selected_strat.risk.get("fixed_leverage") or 
        selected_strat.config.get("fixed_leverage") or 
        selected_strat.risk.get("don_bay_goc") or 
        selected_strat.config.get("don_bay_goc") or 
        DON_BAY_CO_DINH
    )

                                                                                      
    max_lev = int(selected_strat.risk.get("max_leverage")
                  or selected_strat.config.get("max_leverage") or 50)
    don_bay_tf = (selected_strat.risk.get("don_bay_tf")
                  or selected_strat.config.get("don_bay_tf") or "15m")

    if use_don_bay_dong:
        try:
            from chien_luoc.optimizer.don_bay import tinh_don_bay_live
            leverage = int(tinh_don_bay_live(
                symbol, fixed_leverage,
                frames_by_tf.get("1m"), frames_by_tf.get("3m"), frames_by_tf.get("5m"),
                frames_by_tf.get("15m"), frames_by_tf.get("30m"), frames_by_tf.get("1h"),
                frames_by_tf.get("4h"), frames_by_tf.get("1d"),
                max_leverage=max_lev, time_frame=don_bay_tf,
            ))
        except Exception as e:
            logger.error(f"[bar-to-bar] lỗi tính đòn bẩy động: {e}")
            leverage = fixed_leverage
    else:
        leverage = fixed_leverage

    trade_allowed = _trade_allowed_now(df_1m, use_ml, regime_cho_phep=regime_cho_phep)
    signal = signal_raw if trade_allowed else 0

    return {
        "signal": signal,
        "signal_raw": signal_raw,
        "sl_pct": sl_pct,
        "tp_pct": tp_pct,
        "leverage": leverage,
        "regime": -1,
        "trade_allowed": trade_allowed,
        "strategy_name": strategy_name,
        "use_ml": use_ml,
    }


def _frames(df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d):
    return {
        "1m": df_1m, "3m": df_3m, "5m": df_5m, "15m": df_15m,
        "30m": df_30m, "1h": df_1h, "4h": df_4h, "1d": df_1d,
    }


def chien_luoc_vao_lenh(
    symbol, Datetime, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d,
    MarketSnapshot=None,
):
    """Entry point mỗi lần quét bar-to-bar. Trả (tin_hieu, diem, chien_luoc, ly_do, packet)."""
    if df_1m is None or (hasattr(df_1m, "is_empty") and df_1m.is_empty()):
        return None, 0, None, "Không có dữ liệu 1m", None

    frames = _frames(df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d)
    kq = danh_gia_tin_hieu_bar(symbol, frames)
    sig = kq["signal"]
    if sig == 0:
        return None, 0, None, "Không có tín hiệu đồng thuận", None

    tin_hieu = "buy" if sig == 1 else "sell"
    diem = 25 if sig == 1 else -25
    packet = {
        "strategy_name": kq["strategy_name"],
        "signal": sig,
        "sl_pct": kq["sl_pct"],
        "tp_pct": kq["tp_pct"],
        "leverage": kq["leverage"],
        "regime": kq["regime"],
        "use_ml": kq["use_ml"],
    }
    if kq["use_ml"]:
        packet["state_name"] = kq["strategy_name"]

    ly_do = f"Đồng thuận chiến lược ({kq['strategy_name']}) → {tin_hieu.upper()}"
    return tin_hieu, diem, kq["strategy_name"], ly_do, packet


def chien_luoc_thoat_lenh(
    symbol, vi_the_hien_tai, chien_luoc, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d,
    MarketSnapshot=None,
):
    """Đóng lệnh khi tín hiệu hợp nhất ĐẢO CHIỀU ngược vị thế đang giữ."""
    if df_1m is None or (hasattr(df_1m, "is_empty") and df_1m.is_empty()):
        return False, "Không có dữ liệu 1m"

    frames = _frames(df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d)
    kq = danh_gia_tin_hieu_bar(symbol, frames)
    sig = kq["signal_raw"]
    vt = (vi_the_hien_tai or "").lower()

    if vt == "buy" and sig == -1:
        return True, "Đảo chiều → SHORT"
    if vt == "sell" and sig == 1:
        return True, "Đảo chiều → LONG"
    return False, "Giữ lệnh"


                                                                           

def tinh_sl_tp_theo_atr(gia_vao, tin_hieu, df_15m):
    """Wrapper tính SL/TP động theo cấu hình chiến lược hiện tại hoặc mặc định."""
    from chien_luoc.optimizer.stoploss_takeprofit import tinh_sl_tp_live
    return tinh_sl_tp_live(df_15m, gia_vao, tin_hieu, base_sl=BASE_SL_DEFAULT, rr=RR_DEFAULT)


def phan_tich_don_bay(symbol, don_bay, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d):
    """Wrapper tính đòn bẩy động theo cấu hình chiến lược hiện tại hoặc mặc định."""
    from chien_luoc.optimizer.don_bay import tinh_don_bay_live
    return tinh_don_bay_live(symbol, don_bay, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d)


def danh_gia_ml(packet, pnl_pct, drawdown_pct):
    """Đánh giá hiệu quả ML dựa trên cấu hình chiến lược (kiểm tra trường use_ml)."""
    if packet and packet.get("use_ml", False):
        try:
            from ml.trang_thai_thi_truong_ml.ml_predict import danh_gia_ml as _danh_gia_ml
            _danh_gia_ml(packet, pnl_pct, drawdown_pct)
        except Exception as e:
            logger.error(f"[bar-to-bar] lỗi khi đánh giá ML: {e}")
