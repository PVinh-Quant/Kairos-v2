"""
chuc_nang/backtest_donluong.py – Backtest Bar-to-Bar Đơn Luồng
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chạy tuần tự từng symbol trong một luồng duy nhất.
Phù hợp để debug và kiểm tra logic chiến lược trước khi chạy đa luồng.
"""

import sys
import os
import time
import json
import polars as pl

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
    from utils.thoi_gian import lay_timestamp_ms
    from utils.kho_du_lieu import luu_ket_qua_backtest, tao_run_id
except ImportError as e:
    logger.error(f"Lỗi Import: {e}")
    logger.info(
        "Vui lòng chạy script từ thư mục gốc hoặc đảm bảo cấu trúc thư mục đúng."
    )
    sys.exit(1)


def chay_backtest(return_data=False, callback=None):
    """Chạy backtest bar-to-bar đơn luồng cho nhiều symbol theo thứ tự, trả về dict kết quả."""
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    VON_BAN_DAU = float(
        config_backtest.get(
            "so_du_ban_dau",
            10000.0,
        )
    )
    PHI_GD = float(
        config_backtest.get(
            "phi_giao_dich",
            0.001,
        )
    )
    SLIPPAGE = float(
        config_backtest.get(
            "do_truot_gia",
            0.0005,
        )
    )
    START_DATE = config_backtest.get("ngay_bat_dau", "")
    END_DATE = config_backtest.get("ngay_ket_thuc", "")

    DON_BAY = int(
        config_trading.get(
            "don_bay",
            1,
        )
    )
    DS_SYMBOL = config_trading.get("cap_giao_dich", [])
    VON_MOI_LENH = float(
        config_trading.get(
            "von_moi_lenh_usdt",
            100.0,
        )
    )

    lich_su_lenh = []
    run_id = tao_run_id()

    from utils.log import banner_khoi_dong

    banner_khoi_dong(
        "BACKTEST  —  Bar-to-Bar",
        [
            ("Thời gian", f"{START_DATE}  →  {END_DATE}"),
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.2f} USDT"),
            ("Phí GD", f"{PHI_GD*100:.3f}%"),
            ("Slippage", f"{SLIPPAGE*100:.3f}%"),
            ("Symbols", ", ".join(DS_SYMBOL) if DS_SYMBOL else "—"),
        ],
    )

    for symbol in DS_SYMBOL:
        logger.info(f"Đang xử lý cặp: {symbol}")
        von_hien_tai = VON_BAN_DAU
        bien_dong_tai_san = [{"time": START_DATE, "balance": VON_BAN_DAU}]

        df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)

        if df_goc is None or df_goc.is_empty():
            logger.warning(f"Không có dữ liệu cho {symbol}, bỏ qua.")
            continue

        # Pre-compute regime ML 1 lần trước khi vào loop bar-to-bar để tránh inference lặp lại mỗi nến
        try:
            from chien_luoc.quan_ly_chien_luoc_bar_to_bar import STRATEGIES
            if STRATEGIES:
                selected_strat = list(STRATEGIES.values())[0]
                use_ml = (
                    bool(selected_strat.config.get("dung_ml", False)) or
                    bool(selected_strat.logic.get("dung_ml", False)) or
                    bool(selected_strat.config.get("use_ml", False)) or
                    bool(selected_strat.risk.get("use_ml", False))
                )
                if use_ml:
                    from chien_luoc.optimizer.trang_thai_thi_truong import pre_compute_regime
                    logger.info(f"[ML] Đang pre-compute regime cho {symbol}...")
                    df_goc = pre_compute_regime(df_goc)
        except Exception as e:
            logger.warning(f"[ML] Không thể pre-compute regime: {e}")

        vi_the = None
        dem_cooldown = 0
        COOLDOWN_NEN = int(config_trading.get("cooldown_nen", 5))

        idx_start = 43200
        if df_goc.height < idx_start:
            logger.warning("Dữ liệu quá ngắn.")
            continue

        timestamps = df_goc.get_column("timestamp").slice(idx_start).to_list()

        last_price_close = 0
        last_time_str = ""


        dinh_tai_khoan = von_hien_tai

        for current_time in timestamps:

            set_log_time(current_time)
            start_time = lay_timestamp_ms()

            print(f"⏳ {current_time}", end="\r")

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
                side = vi_the["side"]
                value = vi_the["value"]
                entry = vi_the["entry"]
                sl_price = vi_the["sl_price"]
                tp_price = vi_the["tp_price"]
                amount = vi_the["amount"]
                don_bay = vi_the["leverage"]
                time_open = vi_the["time_open"]
                phi_mo_lenh = vi_the["phi_mo"]
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
                        ly_do_thoat = f"SIGNAL ({reason})"
                        gia_khop_thoat = gia_close

                if can_thoat:
                    if ly_do_thoat == "LIQUIDATION":

                        real_pnl_pct = -1 / don_bay
                        loi_nhuan_usdt = -value
                        phi_dong = 0.0
                    else:
                        phi_truot_dong = gia_khop_thoat * SLIPPAGE
                        if side == "buy":
                            gia_khop_thoat = gia_khop_thoat - phi_truot_dong
                            real_pnl_pct = (gia_khop_thoat - entry) / entry
                        else:
                            gia_khop_thoat = gia_khop_thoat + phi_truot_dong
                            real_pnl_pct = (entry - gia_khop_thoat) / entry
                        loi_nhuan_usdt = (value * don_bay) * real_pnl_pct
                        phi_dong = (value * don_bay) * PHI_GD
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
                            "time_open": time_open,
                            "time_close": str_time,
                            "side": side,
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

                    if callback:
                        callback(
                            {
                                "trades": lich_su_lenh,
                                "equity_curve": bien_dong_tai_san,
                                "initial_capital": VON_BAN_DAU,
                                "final_capital": von_hien_tai,
                            }
                        )


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

            end_time = lay_timestamp_ms()
            thoi_gian_xu_ly_ms = end_time - start_time

            print(f"⏳ {current_time} | Xử lý trong: {thoi_gian_xu_ly_ms} ms", end="\r")

        if vi_the:
            logger.warning(
                f"Đóng cưỡng bức lệnh treo {symbol} tại giá cuối cùng: {last_price_close}"
            )
            side = vi_the["side"]
            value = vi_the["value"]
            entry = vi_the["entry"]
            don_bay = vi_the["leverage"]
            time_open = vi_the["time_open"]
            phi_mo_lenh = vi_the.get("phi_mo", 0)

            gia_khop_thoat = last_price_close

            if side == "buy":
                raw_pnl_pct = (gia_khop_thoat - entry) / entry
            else:
                raw_pnl_pct = (entry - gia_khop_thoat) / entry

            gia_tri_lenh = value * don_bay
            loi_nhuan_tho = gia_tri_lenh * raw_pnl_pct
            phi_dong = gia_tri_lenh * PHI_GD

            balance_change = loi_nhuan_tho - phi_dong
            von_hien_tai += balance_change

            real_pnl_usd = loi_nhuan_tho - phi_dong - phi_mo_lenh

            lich_su_lenh.append(
                {
                    "symbol": symbol,
                    "time_open": time_open,
                    "time_close": last_time_str,
                    "side": side,
                    "entry": entry,
                    "exit": gia_khop_thoat,
                    "leverage": don_bay,
                    "pnl_usd": real_pnl_usd,
                    "pnl_pct": raw_pnl_pct,
                    "strategy": vi_the.get("chien_luoc", ""),
                    "reason": "FORCE CLOSE (END)",
                    "balance": von_hien_tai,
                    "packet": vi_the.get("packet"),
                }
            )
            bien_dong_tai_san.append({"time": last_time_str, "balance": von_hien_tai})

            if callback:
                callback(
                    {
                        "trades": lich_su_lenh,
                        "equity_curve": bien_dong_tai_san,
                        "initial_capital": VON_BAN_DAU,
                        "final_capital": von_hien_tai,
                    }
                )


    if lich_su_lenh:
        lich_su_lenh.sort(key=lambda x: x.get("time_close", ""))
        curr_bal = VON_BAN_DAU
        bien_dong_tai_san = [{"time": START_DATE, "balance": curr_bal}]
        for t in lich_su_lenh:
            curr_bal += t.get("pnl_usd", 0)
            t["balance"] = curr_bal
            bien_dong_tai_san.append({"time": t.get("time_close"), "balance": curr_bal})
        von_hien_tai = curr_bal

    loi_nhuan = von_hien_tai - VON_BAN_DAU
    wins = [x for x in lich_su_lenh if x["pnl_usd"] > 0]
    losses = [x for x in lich_su_lenh if x["pnl_usd"] <= 0]
    win_rate = len(wins) / len(lich_su_lenh) * 100 if lich_su_lenh else 0

    from utils.log import banner_ket_qua

    banner_ket_qua(
        "KẾT QUẢ  —  Backtest Bar-to-Bar",
        [
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.2f} USDT"),
            ("Vốn cuối", f"{von_hien_tai:,.2f} USDT"),
            (
                "Lợi nhuận",
                f"{loi_nhuan:+,.2f} USDT  ({loi_nhuan/VON_BAN_DAU*100:+.2f}%)",
            ),
            (
                "Tổng lệnh",
                f"{len(lich_su_lenh)}  (Thắng {len(wins)}  /  Thua {len(losses)})",
            ),
            ("Win Rate", f"{win_rate:.1f}%"),
        ],
    )

    if lich_su_lenh:
        save_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "du_lieu",
            "thong_tin_lenh",
            f"ket_qua_backtest_{int(time.time())}.csv",
        )
        pl.DataFrame(
            [{k: v for k, v in r.items() if k != "packet"} for r in lich_su_lenh]
        ).write_csv(save_path)
        logger.info(f"Đã lưu lịch sử lệnh tại: {save_path}")

        try:
            from chien_luoc.quan_ly_chien_luoc_vectorized import ten_cac_chien_luoc_kich_hoat
            ten_chien_luoc = ten_cac_chien_luoc_kich_hoat()
        except Exception:
            ten_chien_luoc = ""
        luu_ket_qua_backtest(
            lich_su_lenh,
            run_id,
            "backtest_bar",
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
        logger.info(f"Đã lưu {len(lich_su_lenh)} lệnh vào warehouse [run_id={run_id}]")

    if return_data:
        return {
            "initial_capital": VON_BAN_DAU,
            "final_capital": von_hien_tai,
            "trades": lich_su_lenh,
            "equity_curve": bien_dong_tai_san,
        }


if __name__ == "__main__":
    chay_backtest()
