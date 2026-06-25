"""
chuc_nang/vectorized_backtest.py – Vectorized Backtest Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Xử lý backtest toàn bộ dataset bằng Pandas vectorized (không loop từng nến).
Pipeline:
  1. Tải lịch sử 1m từ Binance
  2. ML regime detection vectorized
  3. Chạy chiến lược vectorized trên toàn dataset
  4. Tính metrics: winrate, PnL, max drawdown, sharpe ratio
  5. Hiển thị kết quả trên dashboard PyQt6
"""

import sys
import os
import time
import json
import matplotlib
import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from utils.log import logger
    from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
    from utils.save_dataflie import luu_du_lieu_vectorized_pl
    from utils.thoi_gian import lay_timestamp_ms

    from lay_du_lieu.lay_ohlcv import tai_du_lieu_lich_su
    from chien_luoc.quan_ly_chien_luoc_vectorized import tong_hop_tin_hieu
    from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml_vector
    from utils.kho_du_lieu import luu_ket_qua_backtest, tao_run_id, thong_ke_tong_quat

except ImportError as e:
    logger.error(f"Lỗi Import: {e}")
    logger.info(
        "Vui lòng chạy script từ thư mục gốc hoặc đảm bảo cấu trúc thư mục đúng."
    )
    sys.exit(1)


def vectorized_backtest(strategies=None, dataset=None):
    """Chạy backtest vectorized cho tất cả symbol, trả về (list lệnh, dict DataFrame theo symbol).

    strategies: dict {tên: JSONStrategy} override (None = chiến lược toàn cục theo config).
    Truyền vào để backtest ĐÚNG 1 chiến lược — vd màn Tối ưu gửi sang Biểu đồ nến.
    dataset: dict bộ dữ liệu override (None = dùng Symbol/ngày trong config).
    """
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    VON_BAN_DAU = float(config_backtest.get("so_du_ban_dau", 10000))
    PHI_GD = float(config_backtest.get("phi_giao_dich", 0.001))
    SLIPPAGE = float(config_backtest.get("do_truot_gia", 0.001))
    START_DATE = config_backtest.get("ngay_bat_dau", "")
    END_DATE = config_backtest.get("ngay_ket_thuc", "")

    DON_BAY = int(config_trading.get("don_bay", 1))
    DS_SYMBOL = config_trading.get("cap_giao_dich", [])
    VON_MOI_LENH = float(config_trading.get("von_moi_lenh_usdt", 100))

    if dataset:
        START_DATE = dataset.get("tu_ngay") or START_DATE
        END_DATE = dataset.get("den_ngay") or END_DATE
        DS_SYMBOL = dataset.get("symbols") or DS_SYMBOL

    tong_lich_su_lenh = []
    run_id = tao_run_id()
    dict_du_lieu_gui = {}

    from utils.log import banner_khoi_dong

    banner_khoi_dong(
        "VECTORIZED BACKTEST",
        [
            ("Thời gian", f"{START_DATE}  →  {END_DATE}"),
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.0f} USDT"),
            ("Vốn/lệnh", f"{VON_MOI_LENH:,.0f} USDT  ×  {DON_BAY}x"),
            ("Phí / Slip", f"{PHI_GD*100:.3f}%  /  {SLIPPAGE*100:.3f}%"),
            ("Symbols", ", ".join(DS_SYMBOL) if DS_SYMBOL else "—"),
            ("Run ID", run_id),
        ],
    )

                                    

    for symbol in DS_SYMBOL:

        start_time = lay_timestamp_ms()


        logger.info(f"Đang xử lý cặp: {symbol}")
        von_hien_tai = VON_BAN_DAU
        df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)

        if df_goc is None or df_goc.is_empty():
            continue

                                                                                               
        df = tong_hop_tin_hieu(df_goc, strategies=strategies)
        
                                         
        vi_the = 0
        gia_vao = 0
        co_tin_hieu = 0
        regime_vao = 0                                                        
        don_bay_vao = DON_BAY
        dem_cooldown = 0
                                                                                               
        COOLDOWN_NEN = int(config_trading.get("cooldown_nen", 5))                                        

                                                                   
        signals = df["signal"].to_numpy()
                                                                                       
        signals_raw = (
            df["signal_raw"].to_numpy() if "signal_raw" in df.columns else signals
        )
        opens = df["open"].to_numpy()
        closes = df["close"].to_numpy()
        highs = df["high"].to_numpy() if "high" in df.columns else closes.copy()
        lows = df["low"].to_numpy() if "low" in df.columns else closes.copy()
        times = df["timestamp"].to_numpy()
        sl_pcts = df["sl_pct"].to_numpy() if "sl_pct" in df.columns else np.array([0.05] * len(df))
        tp_pcts = df["tp_pct"].to_numpy() if "tp_pct" in df.columns else np.array([0.10] * len(df))
        leverages = (
            df["leverage"].to_numpy() if "leverage" in df.columns else np.array([DON_BAY] * len(df))
        )
        regimes = df["regime"].to_numpy() if "regime" in df.columns else np.array([0] * len(df))

        sl_gia = 0.0
        tp_gia = 0.0
        thoi_gian_vao = None
        sl_pct_vao = 0.0
        tp_pct_vao = 0.0

                                                                  
        idx_start = 43200
        if len(df) <= idx_start:
            logger.warning(f"Dữ liệu của {symbol} quá ngắn để warm-up.")
            continue

        signal_indices = np.where(signals != 0)[0]
        num_signals = len(signal_indices)
        sig_ptr = 0

        i = idx_start
        n = len(df)
        while i < n:
            if dem_cooldown > 0:
                dem_cooldown -= 1

                                                                           
            if vi_the == 0 and co_tin_hieu == 0 and dem_cooldown == 0:
                while sig_ptr < num_signals and signal_indices[sig_ptr] < i:
                    sig_ptr += 1
                if sig_ptr >= num_signals:
                    break
                i = signal_indices[sig_ptr]

            tin_hieu_hien_tai = signals[i]
            tin_hieu_raw = signals_raw[i]
            gia_open = opens[i]
            gia_close = closes[i]
            gia_high = highs[i]
            gia_low = lows[i]
            thoi_gian = times[i]
            don_bay_i = int(leverages[i])

                                                                 
            if co_tin_hieu != 0 and vi_the == 0:
                                                 
                if von_hien_tai < VON_MOI_LENH:
                    co_tin_hieu = 0
                    i += 1
                    continue

                vi_the = co_tin_hieu
                don_bay_vao = don_bay_i
                regime_vao = int(regimes[i - 1]) if i > 0 else 0
                phi_truot = gia_open * SLIPPAGE
                gia_vao = gia_open + phi_truot if vi_the == 1 else gia_open - phi_truot

                                     
                sl_pct_i = sl_pcts[i - 1] if i > 0 else 0.05
                tp_pct_i = tp_pcts[i - 1] if i > 0 else 0.10
                if vi_the == 1:
                    sl_gia = gia_vao * (1 - sl_pct_i)
                    tp_gia = gia_vao * (1 + tp_pct_i)
                else:
                    sl_gia = gia_vao * (1 + sl_pct_i)
                    tp_gia = gia_vao * (1 - tp_pct_i)

                phi_mo = (VON_MOI_LENH * don_bay_vao) * PHI_GD
                von_hien_tai -= phi_mo
                co_tin_hieu = 0
                thoi_gian_vao = thoi_gian
                sl_pct_vao = sl_pct_i
                tp_pct_vao = tp_pct_i

                                                                                            
            if vi_the != 0:
                can_thoat = False
                loai = "LONG" if vi_the == 1 else "SHORT"
                gia_dong = gia_close
                ly_do_thoat = ""

                if vi_the == 1:
                    liq_price = gia_vao * (1 - 1 / don_bay_vao)
                                                                                                   
                    if gia_low <= sl_gia:
                        can_thoat = True
                        gia_dong = sl_gia
                        ly_do_thoat = "SL"
                                    
                    elif gia_high >= tp_gia:
                        can_thoat = True
                        gia_dong = tp_gia
                        ly_do_thoat = "TP"
                                                                                        
                    elif gia_low <= liq_price:
                        can_thoat = True
                        gia_dong = liq_price
                        ly_do_thoat = "LIQUIDATION"
                                                                                                     
                    elif tin_hieu_raw == -1:
                        can_thoat = True
                        ly_do_thoat = "SIGNAL"
                else:
                    liq_price = gia_vao * (1 + 1 / don_bay_vao)
                                                                 
                    if gia_high >= sl_gia:
                        can_thoat = True
                        gia_dong = sl_gia
                        ly_do_thoat = "SL"
                                    
                    elif gia_low <= tp_gia:
                        can_thoat = True
                        gia_dong = tp_gia
                        ly_do_thoat = "TP"
                                                                                        
                    elif gia_high >= liq_price:
                        can_thoat = True
                        gia_dong = liq_price
                        ly_do_thoat = "LIQUIDATION"
                                                                                                     
                    elif tin_hieu_raw == 1:
                        can_thoat = True
                        ly_do_thoat = "SIGNAL"

                if can_thoat:
                    if ly_do_thoat != "LIQUIDATION":
                        phi_truot_dong = gia_dong * SLIPPAGE
                        if vi_the == 1:
                            gia_dong = gia_dong - phi_truot_dong
                        else:
                            gia_dong = gia_dong + phi_truot_dong

                    if ly_do_thoat == "LIQUIDATION":
                                                                                        
                        pnl_raw = -VON_MOI_LENH
                        phi_dong = 0.0
                    else:
                        pnl_raw = (
                            (gia_dong - gia_vao) / gia_vao
                            if vi_the == 1
                            else (gia_vao - gia_dong) / gia_vao
                        ) * (VON_MOI_LENH * don_bay_vao)
                        phi_dong = (VON_MOI_LENH * don_bay_vao) * PHI_GD
                    phi_mo_lenh = (VON_MOI_LENH * don_bay_vao) * PHI_GD
                    pnl_net = pnl_raw - phi_dong - phi_mo_lenh
                    von_hien_tai += (pnl_raw - phi_dong)

                    tong_lich_su_lenh.append(
                        {
                            "Symbol": symbol,
                            "Loại": loai,
                            "Regime": regime_vao,
                            "Giá vào": gia_vao,
                            "Giá đóng": gia_dong,
                            "Leverage": don_bay_vao,
                            "PnL": pnl_net,
                            "Time": thoi_gian,
                            "Balance": von_hien_tai,
                            "Strategy": "",                                                  
                            "Entry_Time": thoi_gian_vao,
                            "SL_pct": sl_pct_vao,
                            "TP_pct": tp_pct_vao,
                            "Exit_Reason": ly_do_thoat,
                        }
                    )
                    vi_the = 0
                    dem_cooldown = COOLDOWN_NEN                                          

                                                                                                  
            if vi_the == 0 and co_tin_hieu == 0 and tin_hieu_hien_tai != 0 and dem_cooldown == 0:
                co_tin_hieu = tin_hieu_hien_tai

            i += 1

        dict_du_lieu_gui[symbol] = df.clone()

        end_time = lay_timestamp_ms()
        thoi_gian_xu_ly_ms = end_time - start_time
        print(f"Xử lý trong: {thoi_gian_xu_ly_ms} ms", end="\r")


                                                         
        luu_du_lieu_vectorized_pl(df, symbol, "1m", label="backtest")

                                                                                              
    if tong_lich_su_lenh:
        tong_lich_su_lenh.sort(key=lambda x: x.get("Time", ""))
        curr_bal = VON_BAN_DAU
        for t in tong_lich_su_lenh:
            curr_bal += t.get("PnL", 0.0)
            t["Balance"] = curr_bal
            t["price_change"] = t.get("PnL", 0.0)
        von_hien_tai = curr_bal

                                                                              
    if tong_lich_su_lenh:
        df_lenh = pd.DataFrame(tong_lich_su_lenh)
        try:
            from chien_luoc.quan_ly_chien_luoc_vectorized import ten_cac_chien_luoc_kich_hoat
            ten_chien_luoc = ten_cac_chien_luoc_kich_hoat(strategies)
        except Exception:
            ten_chien_luoc = ""
        luu_ket_qua_backtest(
            tong_lich_su_lenh,
            run_id,
            "backtest_vector",
            config={
                "tu_ngay": START_DATE,
                "den_ngay": END_DATE,
                "symbols": DS_SYMBOL,
                "von_ban_dau": VON_BAN_DAU,
                "phi_gd": PHI_GD,
                "slippage": SLIPPAGE,
                "don_bay": DON_BAY,
                "ten_chien_luoc": ten_chien_luoc,
            },
        )
        logger.info(
            f"Đã lưu {len(tong_lich_su_lenh)} lệnh vào warehouse [run_id={run_id}]"
        )

                                                                             
                                                                                            
                                                                    
        try:
            save_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "du_lieu",
                "thong_tin_lenh",
            )
            os.makedirs(save_dir, exist_ok=True)
            csv_path = os.path.join(
                save_dir, f"backtest_vector_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            )
            df_lenh.to_csv(csv_path, index=False, encoding="utf-8")
            logger.info(f"Đã xuất CSV lịch sử lệnh vector: {csv_path}")
        except Exception as e:
            logger.warning(f"Không xuất được CSV lịch sử lệnh vector: {e}")

                                                                              
    if tong_lich_su_lenh:
        df_result = pd.DataFrame(tong_lich_su_lenh)
        tong_lenh = len(df_result)
        so_thang = (df_result["PnL"] > 0).sum()
        winrate = so_thang / tong_lenh * 100 if tong_lenh else 0
        tong_pnl = df_result["PnL"].sum()
        pnl_pct = (von_hien_tai - VON_BAN_DAU) / VON_BAN_DAU * 100

        from utils.log import banner_ket_qua

        banner_ket_qua(
            "KẾT QUẢ  —  Vectorized Backtest",
            [
                ("Thời gian", f"{START_DATE}  →  {END_DATE}"),
                ("Vốn ban đầu", f"{VON_BAN_DAU:,.0f} USDT"),
                ("Vốn cuối", f"{von_hien_tai:,.2f} USDT  ({pnl_pct:+.2f}%)"),
                (
                    "Tổng lệnh",
                    f"{tong_lenh}  (Thắng {so_thang}  /  Thua {tong_lenh - so_thang})",
                ),
                ("Win Rate", f"{winrate:.1f}%"),
                ("Tổng PnL", f"{tong_pnl:+,.2f} USDT"),
            ],
        )
    else:
        logger.warning("Không có lệnh nào được thực hiện trong khoảng thời gian này.")

    vectorized_backtest.dict_du_lieu_gui = dict_du_lieu_gui
    return tong_lich_su_lenh, dict_du_lieu_gui


if __name__ == "__main__":
    vectorized_backtest()
