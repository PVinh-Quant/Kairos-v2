"""
chuc_nang/backtest_daluong.py – Backtest Bar-to-Bar Đa Luồng
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mỗi symbol chạy trong một tiến trình riêng (ProcessPoolExecutor).
Kết quả được gộp và tính equity curve tổng hợp sau khi tất cả tiến trình hoàn tất.
"""

import os
import sys
import time
import json
import polars as pl
import multiprocessing
from multiprocessing import Manager
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from utils.log import logger, set_log_time, reset_log_time
    from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
    from lay_du_lieu.lay_ohlcv import (
        gop_nen,
        tai_du_lieu_lich_su,
        chuan_bi_du_lieu_da_khung,
    )
    from chien_luoc.quan_ly_chien_luoc_bar_to_bar import (
        chien_luoc_vao_lenh,
        chien_luoc_thoat_lenh,
        tinh_sl_tp_theo_atr,
        phan_tich_don_bay,
        danh_gia_ml,
    )
    from utils.kho_du_lieu import luu_ket_qua_backtest, tao_run_id
except ImportError as e:
    logger.error(f"Lỗi Import: {e}")
    logger.info(
        "Vui lòng chạy script từ thư mục gốc hoặc đảm bảo cấu trúc thư mục đúng."
    )
    sys.exit(1)


def backtest_1_symbol(symbol, config_backtest, config_trading, result_queue):
    """Chạy backtest bar-to-bar cho một symbol trong tiến trình riêng, đẩy kết quả qua result_queue."""
    try:
        DON_BAY = int(
            config_trading.get(
                "don_bay",
            )
        )
        VON_BAN_DAU = float(config_backtest.get("so_du_ban_dau", 10000))
        PHI_GD = float(config_backtest.get("phi_giao_dich", 0.001))
        SLIPPAGE = float(config_backtest.get("do_truot_gia", 0.0005))
        START_DATE = config_backtest.get("ngay_bat_dau", "")
        END_DATE = config_backtest.get("ngay_ket_thuc", "")

        VON_MOI_LENH = float(config_trading.get("von_moi_lenh_usdt", 100))

        von_hien_tai = VON_BAN_DAU
        lich_su_lenh = []
        bien_dong_tai_san = [{"time": START_DATE, "balance": VON_BAN_DAU}]

        df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)

        if df_goc.is_empty():
            logger.warning(f"Không có dữ liệu cho {symbol}, bỏ qua.")
            return []

        vi_the = None
        dem_cooldown = 0
        COOLDOWN_NEN = int(config_trading.get("cooldown_nen", 5))

        idx_start = 43200

        if df_goc.height < idx_start:
            logger.warning("Dữ liệu quá ngắn.")
            return []

        timestamps = df_goc.get_column("timestamp").slice(idx_start).to_list()

        last_price_close = 0
        last_time_str = ""

                             
        dinh_tai_khoan = von_hien_tai

                                  
        for current_time in timestamps:

            set_log_time(current_time)

            print(f"⏳ {symbol} :{current_time}", end="\r")

            if dem_cooldown > 0:
                dem_cooldown -= 1

            dfs = chuan_bi_du_lieu_da_khung(df_goc, current_time)

            if not dfs:
                continue

            df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d = dfs

            nen_hien_tai = df_1m.tail(1).to_dicts()[0]
            gia_close = nen_hien_tai["close"]
            gia_high = nen_hien_tai["high"]
            gia_low = nen_hien_tai["low"]

            last_price_close = gia_close
            str_time = current_time.strftime("%Y-%m-%d %H:%M")
            last_time_str = str_time

            if vi_the:
                                                   
                side, entry, don_bay, amount = (
                    vi_the["side"],
                    vi_the["entry"],
                    vi_the["leverage"],
                    vi_the["amount"],
                )
                sl_price, tp_price, time_open, phi_mo_lenh = (
                    vi_the["sl_price"],
                    vi_the["tp_price"],
                    vi_the["time_open"],
                    vi_the["phi_mo"],
                )
                chien_luoc = vi_the["chien_luoc"]

                can_thoat = False
                ly_do_thoat = ""
                gia_khop_thoat = gia_close

                                                   
                if side == "buy":
                    liq_price = entry * (1 - 1 / don_bay)
                                                                                            
                    if sl_price > 0 and gia_low <= sl_price:
                        can_thoat = True
                        ly_do_thoat = "SL"
                        gia_khop_thoat = sl_price
                    elif tp_price > 0 and gia_high >= tp_price:
                        can_thoat = True
                        ly_do_thoat = "TP"
                        gia_khop_thoat = tp_price
                    elif gia_low <= liq_price:
                        can_thoat = True
                        ly_do_thoat = "LIQUIDATION"
                        gia_khop_thoat = liq_price
                else:
                    liq_price = entry * (1 + 1 / don_bay)
                                                                                            
                    if sl_price > 0 and gia_high >= sl_price:
                        can_thoat = True
                        ly_do_thoat = "SL"
                        gia_khop_thoat = sl_price
                    elif tp_price > 0 and gia_low <= tp_price:
                        can_thoat = True
                        ly_do_thoat = "TP"
                        gia_khop_thoat = tp_price
                    elif gia_high >= liq_price:
                        can_thoat = True
                        ly_do_thoat = "LIQUIDATION"
                        gia_khop_thoat = liq_price

                                                                    
                if not can_thoat:
                    check_thoat, reason = chien_luoc_thoat_lenh(
                        symbol,
                        side,
                        chien_luoc,
                        df_1m,
                        df_3m,
                        df_5m,
                        df_15m,
                        df_30m,
                        df_1h,
                        df_4h,
                        df_1d,
                    )
                    if check_thoat:
                        can_thoat = True
                        ly_do_thoat = reason
                        gia_khop_thoat = gia_close

                if can_thoat:
                    if ly_do_thoat == "LIQUIDATION":
                                                                                        
                        real_pnl_pct = -1 / don_bay
                        loi_nhuan_usdt = -vi_the["value"]
                        phi_dong = 0.0
                    else:
                        phi_truot_dong = gia_khop_thoat * SLIPPAGE
                        if side == "buy":
                            gia_khop_thoat = gia_khop_thoat - phi_truot_dong
                            real_pnl_pct = (gia_khop_thoat - entry) / entry
                        else:
                            gia_khop_thoat = gia_khop_thoat + phi_truot_dong
                            real_pnl_pct = (entry - gia_khop_thoat) / entry
                        loi_nhuan_usdt = (vi_the["value"] * don_bay) * real_pnl_pct
                        phi_dong = (vi_the["value"] * don_bay) * PHI_GD
                    net_profit = loi_nhuan_usdt - phi_dong
                    von_hien_tai += net_profit

                    real_pnl_usd = loi_nhuan_usdt - phi_dong - phi_mo_lenh

                    logger.info(
                        f"[ OUT ] {symbol:<9} {side.upper():<4} | "
                        f"Price: {gia_khop_thoat:>9.2f} | "
                        f"PnL: {real_pnl_usd:>+5.2f}$ ({(real_pnl_usd / vi_the['value']) * 100:>+8.2f}%) | "
                        f"S: {chien_luoc}"
                    )

                    lich_su_lenh.append(
                        {
                            "symbol": symbol,
                            "side": side,
                            "time_open": time_open,
                            "time_close": str_time,
                            "entry": entry,
                            "exit": gia_khop_thoat,
                            "leverage": don_bay,
                            "pnl_usd": real_pnl_usd,
                            "pnl_pct": real_pnl_usd / vi_the["value"],
                            "score": vi_the["diem"],
                            "strategy": chien_luoc,
                            "reason": ly_do_thoat,
                            "balance": von_hien_tai,
                            "packet": vi_the.get("packet"),
                        }
                    )

                    bien_dong_tai_san.append(
                        {"time": str_time, "balance": von_hien_tai}
                    )

                    result_queue.put({"symbol": symbol, "trades": lich_su_lenh})

                                          
                    if von_hien_tai > dinh_tai_khoan:
                        dinh_tai_khoan = von_hien_tai
                    account_drawdown = (
                        (von_hien_tai - dinh_tai_khoan) / dinh_tai_khoan * 100
                    )
                    danh_gia_ml(
                        vi_the["packet"],
                        (real_pnl_usd / vi_the["value"]) * 100,
                        account_drawdown,
                    )

                                  
                    vi_the = None
                    dem_cooldown = COOLDOWN_NEN

            if not vi_the and dem_cooldown == 0:
                if von_hien_tai >= VON_MOI_LENH:
                    tin_hieu, diem, chien_luoc, ly_do, packet = chien_luoc_vao_lenh(
                        symbol,
                        current_time,
                        df_1m,
                        df_3m,
                        df_5m,
                        df_15m,
                        df_30m,
                        df_1h,
                        df_4h,
                        df_1d,
                    )
                else:
                    tin_hieu = None

                if tin_hieu:
                    don_bay = int(packet.get("leverage") or DON_BAY)

                    gia_vao = (
                        gia_close * (1 + SLIPPAGE)
                        if tin_hieu == "buy"
                        else gia_close * (1 - SLIPPAGE)
                    )

                    sl_pct = float(packet.get("sl_pct") or 0.025)
                    tp_pct = float(packet.get("tp_pct") or 0.05)
                    if tin_hieu == "buy":
                        sl_price = gia_vao * (1 - sl_pct)
                        tp_price = gia_vao * (1 + tp_pct)
                    else:
                        sl_price = gia_vao * (1 + sl_pct)
                        tp_price = gia_vao * (1 - tp_pct)

                    gia_tri_lenh = VON_MOI_LENH * don_bay
                    so_luong_coin = gia_tri_lenh / gia_vao
                    phi_mo = gia_tri_lenh * PHI_GD

                    von_hien_tai -= phi_mo

                    vi_the = {
                        "side": tin_hieu,
                        "entry": gia_vao,
                        "amount": so_luong_coin,
                        "value": VON_MOI_LENH,
                        "sl_price": sl_price,
                        "tp_price": tp_price,
                        "time_open": str_time,
                        "leverage": don_bay,
                        "phi_mo": phi_mo,
                        "chien_luoc": chien_luoc,
                        "diem": diem,
                        "ly_do": ly_do,
                        "packet": packet,
                    }

                    logger.info(
                        f"[ IN  ] {symbol:<9} {tin_hieu.upper():<4} | "
                        f"Entry: {gia_vao:>9.2f} | "
                        f"Fee: {phi_mo:>6.2f}$ (Sc:{diem:>5}) | "
                        f"S: {chien_luoc}"
                    )

                                        
        if vi_the:
            side, entry, don_bay = vi_the["side"], vi_the["entry"], vi_the["leverage"]
            raw_pnl_pct = (
                (last_price_close - entry) / entry
                if side == "buy"
                else (entry - last_price_close) / entry
            )
            net_profit = (vi_the["value"] * don_bay * raw_pnl_pct) - (
                vi_the["value"] * don_bay * PHI_GD
            )
            von_hien_tai += net_profit

            lich_su_lenh.append(
                {
                    "symbol": symbol,
                    "time_open": vi_the["time_open"],
                    "time_close": last_time_str,
                    "side": side,
                    "entry": entry,
                    "exit": last_price_close,
                    "leverage": don_bay,
                    "pnl_usd": net_profit - vi_the.get("phi_mo", 0),
                    "pnl_pct": raw_pnl_pct,
                    "strategy": vi_the.get("chien_luoc", ""),
                    "reason": "FORCE CLOSE (END)",
                    "balance": von_hien_tai,
                    "packet": vi_the.get("packet"),
                }
            )
            result_queue.put({"symbol": symbol, "trades": lich_su_lenh})

        reset_log_time()
        return lich_su_lenh

    except Exception as e:
        logger.error(f"Lỗi {symbol}: {e}")
        return []


def chay_backtest(return_data=False, callback=None):
    """Chạy backtest đa luồng cho tất cả symbol, trả về dict kết quả hoặc list lệnh."""
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    DS_SYMBOL = config_trading.get("cap_giao_dich", [])
    total_symbols = len(DS_SYMBOL)
    VON_BAN_DAU = float(config_backtest.get("so_du_ban_dau", 10000))
    run_id = tao_run_id()

    config_luong = config_backtest.get("so_luong_luong")
    num_workers = int(config_luong) if config_luong else max(1, os.cpu_count() - 1)

    trades_by_symbol = {}
    all_trades_merged = []
    equity_curve = []
    curr_bal = VON_BAN_DAU

    update_interval = 0.5
    last_ui_update = 0

    from utils.log import banner_khoi_dong

    banner_khoi_dong(
        "BACKTEST  —  Đa Luồng",
        [
            (
                "Thời gian",
                f"{config_backtest.get('ngay_bat_dau', '')}  →  {config_backtest.get('ngay_ket_thuc', '')}",
            ),
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.2f} USDT"),
            (
                "Phí GD",
                f"{float(config_backtest.get('phi_giao_dich', 0.001))*100:.3f}%",
            ),
            (
                "Slippage",
                f"{float(config_backtest.get('do_truot_gia', 0.0005))*100:.3f}%",
            ),
            ("Symbols", ", ".join(DS_SYMBOL) if DS_SYMBOL else "—"),
        ],
    )

    with Manager() as manager:
        result_queue = manager.Queue()

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
                                                   
            futures = {
                executor.submit(
                    backtest_1_symbol,
                    symbol,
                    config_backtest,
                    config_trading,
                    result_queue,
                ): symbol
                for symbol in DS_SYMBOL
            }

            finished_symbols = set()

                                                                                       
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                                                                            
                                                                           
                    trades = future.result()

                    if symbol:
                        trades_by_symbol[symbol] = trades
                        finished_symbols.add(symbol)

                                                                          
                        all_trades_merged = []
                        for tlist in trades_by_symbol.values():
                            if isinstance(tlist, list):
                                all_trades_merged.extend(tlist)

                                                      
                        all_trades_merged.sort(key=lambda x: x.get("time_close", ""))
                        curr_bal = VON_BAN_DAU
                        equity_curve = [{"time": "Start", "balance": curr_bal}]
                        for t in all_trades_merged:
                            curr_bal += t.get("pnl_usd", 0)
                            t["balance"] = curr_bal
                            equity_curve.append(
                                {"time": t.get("time_close"), "balance": curr_bal}
                            )

                                                               
                        if callback:
                            progress = int(
                                (len(finished_symbols) / len(DS_SYMBOL)) * 100
                            )
                            callback(
                                {
                                    "trades": all_trades_merged,
                                    "equity_curve": equity_curve,
                                    "initial_capital": VON_BAN_DAU,
                                    "final_capital": curr_bal,
                                    "progress": progress,
                                }
                            )

                except Exception as exc:
                    logger.error(f"{symbol} gặp lỗi: {exc}")

    all_trades_merged = []
    for tlist in trades_by_symbol.values():
        if isinstance(tlist, list):
            all_trades_merged.extend(tlist)
    all_trades_merged.sort(key=lambda x: x.get("time_close", 0))

    curr_bal = VON_BAN_DAU
    equity_curve = [{"time": "Start", "balance": curr_bal}]
    for t in all_trades_merged:
        curr_bal += t.get("pnl_usd", 0)
        t["balance"] = curr_bal
        equity_curve.append({"time": t.get("time_close"), "balance": curr_bal})

    loi_nhuan = curr_bal - VON_BAN_DAU
    wins_da = [x for x in all_trades_merged if x.get("pnl_usd", 0) > 0]
    wr_da = len(wins_da) / len(all_trades_merged) * 100 if all_trades_merged else 0

    from utils.log import banner_ket_qua

    banner_ket_qua(
        "KẾT QUẢ  —  Backtest Đa Luồng",
        [
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.2f} USDT"),
            ("Vốn cuối", f"{curr_bal:,.2f} USDT"),
            (
                "Lợi nhuận",
                f"{loi_nhuan:+,.2f} USDT  ({loi_nhuan/VON_BAN_DAU*100:+.2f}%)",
            ),
            (
                "Tổng lệnh",
                f"{len(all_trades_merged)}  (Thắng {len(wins_da)}  /  Thua {len(all_trades_merged)-len(wins_da)})",
            ),
            ("Win Rate", f"{wr_da:.1f}%"),
        ],
    )

    wins = [x for x in all_trades_merged if x["pnl_usd"] > 0]
    losses = [x for x in all_trades_merged if x["pnl_usd"] <= 0]
    logger.info(f"Thắng: {len(wins)} | Thua: {len(losses)}")
    if len(all_trades_merged) > 0:
        win_rate = len(wins) / len(all_trades_merged) * 100
        logger.info(f"Tỷ lệ thắng (Winrate): {win_rate:.2f}%")

    if all_trades_merged:
        folder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "du_lieu", "lich_su_gia"
        )
        os.makedirs(folder_path, exist_ok=True)
        save_path = os.path.join(
            folder_path, f"ket_qua_backtest_daluong_{int(time.time())}.csv"
        )
        pl.DataFrame(
            [{k: v for k, v in t.items() if k != "packet"} for t in all_trades_merged]
        ).write_csv(save_path)
        logger.info(f"Da luu lich su lenh tai: {save_path}")

        try:
            from chien_luoc.quan_ly_chien_luoc_vectorized import ten_cac_chien_luoc_kich_hoat
            ten_chien_luoc = ten_cac_chien_luoc_kich_hoat()
        except Exception:
            ten_chien_luoc = ""
        luu_ket_qua_backtest(
            all_trades_merged,
            run_id,
            "backtest_da_luong",
            config={
                "tu_ngay": config_backtest.get("ngay_bat_dau", ""),
                "den_ngay": config_backtest.get("ngay_ket_thuc", ""),
                "symbols": DS_SYMBOL,
                "von_ban_dau": VON_BAN_DAU,
                "phi_gd": float(config_backtest.get("phi_giao_dich", 0.001)),
                "slippage": float(config_backtest.get("do_truot_gia", 0.0005)),
                "don_bay": int(config_trading.get("don_bay", 1)),
                "ten_chien_luoc": ten_chien_luoc,
            },
        )
        logger.info(
            f"Da luu {len(all_trades_merged)} lenh vao warehouse [run_id={run_id}]"
        )

    final_output = {
        "trades": all_trades_merged,
        "equity_curve": equity_curve,
        "initial_capital": VON_BAN_DAU,
        "final_capital": curr_bal,
    }
    if callback:
        callback({**final_output, "progress": 100})
    return final_output if return_data else all_trades_merged


if __name__ == "__main__":
    chay_backtest()
