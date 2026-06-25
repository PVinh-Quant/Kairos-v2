import os
import glob
import numpy as np
import pandas as pd
import polars as pl
from chien_luoc.json_strategy import JSONStrategy
from chien_luoc.optimizer.stoploss_takeprofit import tinh_sl_tp as tinh_sl_tp_vectorized, tinh_sl_tp_co_dinh
from chien_luoc.optimizer.don_bay import tinh_don_bay as tinh_don_bay_vectorized
from chien_luoc.optimizer.trang_thai_thi_truong import (
    loc_trang_thai_thi_truong,
    du_doan_trang_thai_thi_truong_vectorized,
)
from chien_luoc.optimizer.loc_tin_hieu import chuan_hoa_va_loc_tin_hieu
from Indicator.chu_ky import pt_phien_giao_dich
from utils.log import logger
from utils.doc_cau_hinh import lay_cau_hinh_giao_dich

_config_trade = lay_cau_hinh_giao_dich() or {}

REGIME_TO_STRATEGY = {
    1: "squeeze",
    2: "breakout",
    3: "trend",
    4: "reversion",
    5: "reversion",
    6: "scalping",
}


def _doc_regime_cho_phep(strat):
    """Đọc list regime ĐƯỢC phép vào lệnh từ config chiến lược (logic/config/risk).
    None nếu chiến lược không khai báo → pipeline dùng tập cấm mặc định (0 và 7)."""
    for src in (getattr(strat, "logic", None), getattr(strat, "config", None), getattr(strat, "risk", None)):
        if isinstance(src, dict) and src.get("regime_cho_phep") is not None:
            try:
                return [int(x) for x in src["regime_cho_phep"]]
            except (TypeError, ValueError):
                return None
    return None

                                                                                      
                                                                                     
                                                             
                                                                                       
DUNG_REGIME_MAC_DINH = False

                                                                                     
                                                                                           
                                                                                            
                                                                                    
DUNG_SL_TP_DONG = False
DUNG_DON_BAY_DONG = False
DON_BAY_CO_DINH = int(_config_trade.get("don_bay", 5))
BASE_SL_DEFAULT = 2.5
RR_DEFAULT = 2.0

                                                                                  
                                                                                       
SL_TP_TIME_FRAME = None                                                                           
SL_RANGE = (1.0, 5.0)                                            
RR_RANGE = (1.2, 4.0)                                                 
DON_BAY_GOC = DON_BAY_CO_DINH                                    
MAX_LEVERAGE = 50                                 
DON_BAY_TF = "15m"                                        

                                                      
JSON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "du_lieu", "danh_sach_chien_luoc")
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
                logger.info(f"[vectorized] Bỏ qua chiến lược {strat.name} (bị tắt bên trong cấu hình JSON hoặc status={status_field})")
                continue

                                                                                                      
            if list_kich_hoat_lower:
                name_matches = (strat_name in list_kich_hoat_lower) or (filename in list_kich_hoat_lower)
                if not name_matches:
                    continue
            else:
                if is_rejected:
                    logger.info(f"[vectorized] Bỏ qua chiến lược {strat.name} (chứa vd_REJECT trong tên file)")
                    continue

            STRATEGIES[strat_name] = strat
            logger.info(f"[vectorized] Đã nạp thành công chiến lược: {strat.name}")
        except Exception as e:
            logger.error(f"Lỗi load JSON strategy {f}: {e}")
else:
    logger.warning(f"Thư mục chứa chiến lược JSON không tồn tại: {JSON_DIR}")


def ten_cac_chien_luoc_kich_hoat(strategies=None):
    """Nhãn tên các chiến lược đang kích hoạt, vd 'RSI@5m + MACD@15m'.

    Dùng để lưu vào backtest_run.ten_chien_luoc (UI Trang chủ hiển thị). None ⇒ tập
    STRATEGIES toàn cục (theo config); truyền dict override để lấy đúng tên đang chạy.
    """
    strats = STRATEGIES if strategies is None else strategies
    if not isinstance(strats, dict):
        return ""
    ten = [str(getattr(s, "name", "")).strip() for s in strats.values()]
    ten = [t for t in ten if t]
    return " + ".join(dict.fromkeys(ten))                              


def chay_tat_ca_chien_luoc(df_1m, strategies=None):
    """Chạy chiến lược JSON, trả dict {tên: DataFrame có cột signal}.

    strategies: dict {tên: JSONStrategy} override. None ⇒ dùng STRATEGIES toàn cục
    (nạp lúc import). Truyền vào để chạy ĐÚNG 1 chiến lược (vd màn Tối ưu gửi sang)
    mà không phụ thuộc cache import / lọc tên file.
    """
    strats = STRATEGIES if strategies is None else strategies
    res = {}
    for name, strat in strats.items():
        df_ind = strat.tinh_chi_bao(df_1m)
        df_sig = strat.tinh_tin_hieu_vectorized(df_ind)
        res[name] = df_sig
    return res


def xay_strategies_tu_config(config, ten="active"):
    """Dựng dict {ten: JSONStrategy} từ 1 config best_params (spec s0..,logic,risk).

    JSONStrategy chỉ nhận đường dẫn file ⇒ ghi config ra file tạm rồi nạp (tái dùng
    nguyên bộ parser tương-thích-ngược của JSONStrategy), xoá file sau khi đã nạp.
    Dùng để biến kết quả optimizer (result["best_params"]) thành chiến lược chạy được
    qua chính tong_hop_tin_hieu — KHÔNG tạo path tín hiệu mới.
    """
    import tempfile
    import json as _json

    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(config, f, ensure_ascii=False)
        strat = JSONStrategy(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    strat._name = ten
    return {ten: strat}


def tong_hop_tin_hieu(df_1m, df_regime=None, dung_regime=None, strategies=None):
    """
    Tổng hợp tín hiệu từ tất cả chiến lược bằng Polars.
    Hỗ trợ cả Pandas và Polars DataFrame đầu vào/đầu ra.

    strategies: dict {tên: JSONStrategy} override (None = STRATEGIES toàn cục). Cho phép
    chạy ĐÚNG 1 chiến lược (vd màn Tối ưu gửi sang Biểu đồ nến) qua cùng pipeline này.
    """
    import polars as pl
    import pandas as pd

                                                                              
    strats = STRATEGIES if strategies is None else strategies

    is_pandas = not hasattr(df_1m, "clone")
    if is_pandas:
        df_1m_pl = pl.from_pandas(df_1m)
    else:
        df_1m_pl = df_1m.clone()

                                                                                       
    ket_qua = chay_tat_ca_chien_luoc(df_1m_pl, strategies=strats)

                                        
    df_base = df_1m_pl.select(["timestamp", "open", "high", "low", "close", "volume"])
    if df_base.schema["timestamp"] in (pl.String, pl.Utf8):
        df_base = df_base.with_columns(pl.col("timestamp").str.to_datetime())
    
    df_base = df_base.with_columns(pl.lit(0).cast(pl.Int64).alias("signal"))

                                                                                        
                                                                                             
    dung_regime_ml = False
    regime_cho_phep = None
    if strats:
        selected_strat = list(strats.values())[0]
        use_ml_strat = (
            bool(selected_strat.config.get("dung_ml", False)) or
            bool(selected_strat.logic.get("dung_ml", False)) or
            bool(selected_strat.config.get("use_ml", False)) or
            bool(selected_strat.logic.get("use_ml", False))
        )
        dung_regime_ml = use_ml_strat
                                                                                             
        regime_cho_phep = _doc_regime_cho_phep(selected_strat)

    if not dung_regime_ml:
        df_base = df_base.with_columns(pl.lit(-1).cast(pl.Int64).alias("regime"))
    for name, df_s in ket_qua.items():
        if df_s.schema["timestamp"] in (pl.String, pl.Utf8):
            df_s = df_s.with_columns(pl.col("timestamp").str.to_datetime())
        elif df_s.schema["timestamp"] != df_base.schema["timestamp"]:
            df_s = df_s.with_columns(pl.col("timestamp").cast(df_base.schema["timestamp"]))
        
        df_base = df_base.join(df_s.select(["timestamp", pl.col("signal").alias("s_val")]), on="timestamp", how="left")
        df_base = df_base.with_columns(
            pl.when(pl.col("signal") == 0).then(pl.col("s_val").fill_null(0)).otherwise(pl.col("signal")).alias("signal")
        ).drop("s_val")

                                                                                      
    if strats:
        selected_strat = list(strats.values())[0]
        base_sl = float(selected_strat.risk.get("base_sl", BASE_SL_DEFAULT))
        rr = float(selected_strat.risk.get("rr", RR_DEFAULT))
        fixed_leverage = int(
            selected_strat.risk.get("fixed_leverage") or
            selected_strat.config.get("fixed_leverage") or
            selected_strat.risk.get("don_bay_goc") or
            selected_strat.config.get("don_bay_goc") or
            DON_BAY_CO_DINH
        )
                                                                                          
        sl_tp_tf = (selected_strat.risk.get("sl_tp_time_frame")
                    or selected_strat.config.get("sl_tp_time_frame") or "15m")
        max_lev = int(selected_strat.risk.get("max_leverage")
                      or selected_strat.config.get("max_leverage") or 50)
        don_bay_tf = (selected_strat.risk.get("don_bay_tf")
                      or selected_strat.config.get("don_bay_tf") or "15m")
    else:
        base_sl = BASE_SL_DEFAULT
        rr = RR_DEFAULT
        fixed_leverage = DON_BAY_CO_DINH
        sl_tp_tf = "15m"
        max_lev = 50
        don_bay_tf = "15m"

    tong_tin_hieu = int(df_base["signal"].abs().sum())
    logger.info(f"Tổng tín hiệu sau union: {tong_tin_hieu} nến")

    df_base = df_base.with_columns(
        pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
    )

                                 
    use_sl_tp_dong_strat = False
    use_don_bay_dong_strat = False
    if strats:
        selected_strat = list(strats.values())[0]
        use_sl_tp_dong_strat = (
            bool(selected_strat.config.get("dung_sl_tp_dong", False)) or
            bool(selected_strat.risk.get("dung_sl_tp_dong", False)) or
            bool(selected_strat.config.get("use_sl_tp_dong", False)) or
            bool(selected_strat.risk.get("use_sl_tp_dong", False))
        )
        use_don_bay_dong_strat = (
            bool(selected_strat.config.get("dung_don_bay_dong", False)) or
            bool(selected_strat.risk.get("dung_don_bay_dong", False)) or
            bool(selected_strat.config.get("use_don_bay_dong", False)) or
            bool(selected_strat.risk.get("use_don_bay_dong", False))
        )

                                                                                       
    use_sl_tp_dong_final = use_sl_tp_dong_strat
    if use_sl_tp_dong_final:
        df_base = tinh_sl_tp_vectorized(df_base, time_frame=sl_tp_tf, base_sl=base_sl, rr=rr)
    else:
        df_base = tinh_sl_tp_co_dinh(df_base, base_sl=base_sl, rr=rr)

                     
    use_don_bay_dong_final = use_don_bay_dong_strat
    if use_don_bay_dong_final:
        df_base = tinh_don_bay_vectorized(df_base, don_bay_goc=fixed_leverage, max_leverage=max_lev, time_frame=don_bay_tf)
    else:
        df_base = df_base.with_columns(pl.lit(fixed_leverage).cast(pl.Int64).alias("leverage"))

                                                   
    df_base = pt_phien_giao_dich(df_base, "1m")

                                                                                           
                                                                                                  
    df_base = chuan_hoa_va_loc_tin_hieu(df_base, dung_regime_ml=dung_regime_ml, regime_cho_phep=regime_cho_phep)

    return df_base.to_pandas() if is_pandas else df_base

