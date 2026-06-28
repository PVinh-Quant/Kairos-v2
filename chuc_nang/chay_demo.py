"""
chuc_nang/chay_demo.py – Paper Trading (Giao dịch giả lập)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logic giống chay_realtime.py nhưng KHÔNG đặt lệnh thật.
Thay vào đó mô phỏng:
  • Slippage: giá vào/ra dịch ±do_truot_gia
  • Phí giao dịch: trừ trực tiếp vào VON_AO
  • PnL: tính theo giá đóng thực tế (sau slippage)

Dùng để validate chiến lược trước khi chuyển sang realtime.
"""

import threading
import time
import sys
import os
import signal
import polars as pl
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
from utils.ham_tien_ich import chuyen_doi_symbol_chuan, tinh_pnl
from utils.chuyen_doi_don_vi import (
    usdt_sang_so_luong_coin,
    lam_tron_khoi_luong,
    mili_giay_sang_phut,
)
from utils.thoi_gian import ngu_an_toan, lay_timestamp_ms
from utils.log import logger
from lay_du_lieu.lay_ohlcv import lay_du_lieu_nen
from lay_du_lieu.lay_marketsnapshot import mo_theo_doi, dong_theo_doi
from chien_luoc.quan_ly_chien_luoc_bar_to_bar import (
    chien_luoc_vao_lenh,
    chien_luoc_thoat_lenh,
    danh_gia_ml,
)

from thuc_thi_lenh.quan_ly_danh_muc import kiem_tra_phan_bo_von
from thuc_thi_lenh import quan_ly_lenh
from utils.kho_du_lieu import luu_lenh_don, luu_run, tao_run_id

CONFIG = lay_cau_hinh_giao_dich()
SAN_CHINH = CONFIG.get("san_giao_dich_chinh", "binance").lower()
RAW_COINS = CONFIG.get("cap_giao_dich", [])
DON_BAY = int(
    CONFIG.get(
        "don_bay",
    )
)
COOLDOWN_NEN = int(CONFIG.get("cooldown_nen", 5))
GIAY_COOLDOWN = COOLDOWN_NEN * 60

LIST_COIN = [chuyen_doi_symbol_chuan(SAN_CHINH, coin) for coin in RAW_COINS]

MAX_OPEN_ORDERS = CONFIG.get("max_lenh_cho_phep")

config_demo = lay_cau_hinh_ao()
VON_AO = float(config_demo.get("so_du_ban_dau"))
PHI_GIAO_DICH = float(config_demo.get("phi_giao_dich"))
DO_TRUOT_GIA = float(config_demo.get("do_truot_gia"))

CHUC_NANG = "demo"
DANG_CHAY = True
lich_su_lenh_ao = []
DEMO_RUN_ID = tao_run_id()


def luong_quet_thi_truong_demo():
    """Luồng quét từng coin tìm tín hiệu vào lệnh, mô phỏng đặt lệnh với vốn ảo."""
    global VON_AO
    logger.info(f"[DEMO] Bắt đầu quét thị trường (Vốn: {VON_AO:,.2f}$)...")

    while DANG_CHAY:
        so_lenh_dang_mo = len(quan_ly_lenh.lay_danh_sach_symbol_dang_co())
        if not kiem_tra_phan_bo_von(
            VON_AO, so_lenh_dang_mo, max_lenh_cho_phep=MAX_OPEN_ORDERS
        ):
            logger.info(
                f"[DEMO] Đã đạt giới hạn {MAX_OPEN_ORDERS} lệnh. Tạm nghỉ quét..."
            )
            ngu_an_toan(10)
            continue

        for symbol in LIST_COIN:
            if quan_ly_lenh.kiem_tra_ton_tai(symbol):
                continue

            dang_cooldown, thoi_gian_con_lai = quan_ly_lenh.kiem_tra_cooldown(symbol, GIAY_COOLDOWN)
            if dang_cooldown:
                continue

            try:
                start_time = lay_timestamp_ms()

                df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d = (
                    lay_du_lieu_nen(SAN_CHINH, symbol)
                )

                MarketSnapshot = mo_theo_doi(symbol)

                Datetime = datetime.now()

                if df_1m is None or df_1m.is_empty():
                    continue

                last_n = df_1m.tail(1).to_dicts()[0]
                gia_hien_tai = last_n["close"]

                tin_hieu, diem, chien_luoc, ly_do, packet = chien_luoc_vao_lenh(
                    symbol,
                    Datetime,
                    df_1m,
                    df_3m,
                    df_5m,
                    df_15m,
                    df_30m,
                    df_1h,
                    df_4h,
                    df_1d,
                    MarketSnapshot,
                )

                if tin_hieu:

                    don_bay = int(packet.get("leverage") or DON_BAY)

                    msg = f"Tin hieu {tin_hieu.upper()} cho {symbol} (Diem: {diem:.2f})"
                    logger.info(msg)

                    gia_tri_lenh = CONFIG["von_moi_lenh_usdt"] * don_bay

                    gia_vao = (
                        gia_hien_tai * (1 + DO_TRUOT_GIA)
                        if tin_hieu == "buy"
                        else gia_hien_tai * (1 - DO_TRUOT_GIA)
                    )

                    so_luong_raw = usdt_sang_so_luong_coin(gia_tri_lenh, gia_hien_tai)
                    so_luong = lam_tron_khoi_luong(so_luong_raw, precision_amount=4)

                    phi_mo = gia_tri_lenh * PHI_GIAO_DICH
                    VON_AO -= phi_mo


                    sl_pct = float(packet.get("sl_pct") or 0.0)
                    tp_pct = float(packet.get("tp_pct") or 0.0)
                    if tin_hieu == "buy":
                        sl_price = gia_vao * (1 - sl_pct)
                        tp_price = gia_vao * (1 + tp_pct)
                    else:
                        sl_price = gia_vao * (1 + sl_pct)
                        tp_price = gia_vao * (1 - tp_pct)

                    quan_ly_lenh.luu_lenh_moi(
                        CHUC_NANG,
                        symbol,
                        {
                            "side": tin_hieu,
                            "entry_price": gia_vao,
                            "amount": so_luong,
                            "leverage": don_bay,
                            "time": Datetime.strftime("%H:%M:%S"),
                            "sl_price": sl_price,
                            "tp_price": tp_price,
                            "chien_luoc": chien_luoc,
                            "diem": diem,
                            "ly_do_mo": ly_do,
                            "packet_ml": packet,
                        },
                    )

                    logger.info(
                        f"[ IN  ] {symbol:<9} {tin_hieu.upper():<4} | "
                        f"Entry: {gia_vao:>9.2f} | "
                        f"Fee: {phi_mo:>6.2f}$ (Sc:{diem:>5}) | "
                        f"S: {chien_luoc}"
                    )

                    end_time = lay_timestamp_ms()
                    thoi_gian_xu_ly_ms = end_time - start_time
                    if thoi_gian_xu_ly_ms > 2000:
                        phut_xu_ly = mili_giay_sang_phut(thoi_gian_xu_ly_ms)
                        logger.warning(
                            f"Mạng chậm! {symbol} xử lý mất {thoi_gian_xu_ly_ms:.0f}ms"
                        )

            except Exception as e:
                logger.error(f"Lỗi quét demo {symbol}: {e}")

            ngu_an_toan(0.2)

        ngu_an_toan(5)


def luong_quan_ly_vi_the_demo():
    """Luồng theo dõi vị thế đang mở, đóng lệnh khi chạm SL/TP hoặc tín hiệu đảo chiều."""
    global VON_AO
    logger.info("[DEMO] Bat dau quan ly vi the...")

    dinh_tai_khoan = VON_AO

    while DANG_CHAY:
        ds_dang_giu = quan_ly_lenh.lay_danh_sach_symbol_dang_co()

        if not ds_dang_giu:
            time.sleep(5)
            continue

        for symbol in ds_dang_giu:
            start_time = lay_timestamp_ms()

            try:
                vt = quan_ly_lenh.lay_thong_tin_lenh(symbol)
                if not vt:
                    continue

                df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d = (
                    lay_du_lieu_nen(SAN_CHINH, symbol)
                )

                MarketSnapshot = mo_theo_doi(symbol)

                if df_1m is None or df_1m.is_empty():
                    continue

                quan_ly_lenh.data_vi_the_update(
                    symbol, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d
                )

                last_n = df_1m.tail(1).to_dicts()[0]
                gia_hien_tai = last_n["close"]
                gia_high = last_n["high"]
                gia_low = last_n["low"]

                sl_price = vt.get("sl_price")
                tp_price = vt.get("tp_price")
                chien_luoc = vt.get("chien_luoc")


                packet_ml = vt.get("packet_ml")

                can_thoat = False
                ly_do = ""
                gia_dong_du_kien = gia_hien_tai

                if sl_price and tp_price:
                    if vt["side"] == "buy":
                        if gia_high >= tp_price:
                            can_thoat = True
                            ly_do = f"Chạm giá TP ({gia_high} >= {tp_price})"
                            gia_dong_du_kien = tp_price
                        elif gia_low <= sl_price:
                            can_thoat = True
                            ly_do = f"Chạm giá SL ({gia_low} <= {sl_price})"
                            gia_dong_du_kien = sl_price
                    else:
                        if gia_low <= tp_price:
                            can_thoat = True
                            ly_do = f"Chạm giá TP ({gia_low} <= {tp_price})"
                            gia_dong_du_kien = tp_price
                        elif gia_high >= sl_price:
                            can_thoat = True
                            ly_do = f"Chạm giá SL ({gia_high} >= {sl_price})"
                            gia_dong_du_kien = sl_price


                if not can_thoat:
                    check_thoat_chien_luoc, ly_do_cl = chien_luoc_thoat_lenh(
                        symbol,
                        vt["side"],
                        chien_luoc,
                        df_1m,
                        df_3m,
                        df_5m,
                        df_15m,
                        df_30m,
                        df_1h,
                        df_4h,
                        df_1d,
                        MarketSnapshot,
                    )
                    if check_thoat_chien_luoc:
                        can_thoat = True
                        ly_do = f"Tín hiệu đảo chiều ({ly_do_cl})"

                if can_thoat:

                    gia_dong_thuc = (
                        gia_dong_du_kien * (1 - DO_TRUOT_GIA)
                        if vt["side"] == "buy"
                        else gia_dong_du_kien * (1 + DO_TRUOT_GIA)
                    )

                    real_pnl_usdt, real_pnl_percent = tinh_pnl(
                        vt["entry_price"], gia_dong_thuc, vt["side"], vt["amount"]
                    )
                    phi_dong = abs(gia_dong_thuc * vt["amount"]) * PHI_GIAO_DICH

                    net_profit = real_pnl_usdt - phi_dong
                    VON_AO += net_profit

                    logger.info(
                        f"[DEMO ĐÓNG] {symbol} | Lý do: {ly_do} | Giá: {gia_dong_thuc:,.2f} | PnL: {net_profit:+.2f}$"
                    )

                    lich_su = {
                        "day": datetime.now().strftime("%Y-%m-%d"),
                        "symbol": symbol,
                        "side": vt["side"],
                        "entry_price": vt["entry_price"],
                        "exit_price": gia_dong_thuc,
                        "open_time": vt["time"],
                        "close_time": datetime.now().strftime("%H:%M:%S"),
                        "pnl": net_profit,
                        "score": vt["diem"],
                        "strategy": chien_luoc,
                        "reason": ly_do,
                        "leverage": vt.get("leverage", 1),
                        "so_du": VON_AO,
                        "packet_ml": vt.get("packet_ml"),
                    }

                    lich_su_lenh_ao.append(lich_su)
                    luu_lenh_don(DEMO_RUN_ID, "demo", lich_su)

                    quan_ly_lenh.lich_su_lenh(CHUC_NANG, lich_su)

                    quan_ly_lenh.xoa_lenh(CHUC_NANG, symbol)



                    if VON_AO > dinh_tai_khoan:
                        dinh_tai_khoan = VON_AO
                    account_drawdown = (VON_AO - dinh_tai_khoan) / dinh_tai_khoan * 100
                    if packet_ml and packet_ml.get("state_name"):
                        real_roe_percent = real_pnl_percent * 100 * vt.get("leverage", 1)
                        danh_gia_ml(packet_ml, real_roe_percent, account_drawdown)

                end = lay_timestamp_ms()
                thoi_gian_xu_ly_ms = end - start_time
                if thoi_gian_xu_ly_ms > 2000:
                    logger.warning(
                        f"[DEMO MANAGER] Xử lý chậm {symbol}: {thoi_gian_xu_ly_ms:.0f}ms"
                    )

                time.sleep(0.2)

            except Exception as e:
                logger.error(f"Lỗi quản lý demo {symbol}: {e}")

        time.sleep(5)


def chay_demo():
    """Khởi động demo paper trading: load trạng thái cũ và chạy 2 luồng scanner + manager."""
    from utils.log import banner_khoi_dong

    banner_khoi_dong(
        "DEMO  —  Paper Trading",
        [
            ("Vốn giả lập", f"{VON_AO:,.2f} USDT"),
            ("Sàn dữ liệu", SAN_CHINH.upper()),
            ("Max Orders", MAX_OPEN_ORDERS),
            ("Symbols", ", ".join(LIST_COIN) if LIST_COIN else "—"),
        ],
    )
    quan_ly_lenh.load_trang_thai(CHUC_NANG)
    try:
        from chien_luoc.quan_ly_chien_luoc_vectorized import ten_cac_chien_luoc_kich_hoat
        _ten_cl = ten_cac_chien_luoc_kich_hoat()
    except Exception:
        _ten_cl = ""
    luu_run(DEMO_RUN_ID, "demo", {"von_ban_dau": VON_AO, "symbols": LIST_COIN, "ten_chien_luoc": _ten_cl})

    try:
        quan_ly_lenh.dang_ky_chay_bot(CHUC_NANG, DEMO_RUN_ID)
    except Exception as e:
        print(f"[chay_demo] Lỗi đăng ký bot: {e}", flush=True)

    t1 = threading.Thread(target=luong_quet_thi_truong_demo, name="Demo-Scanner")
    t2 = threading.Thread(target=luong_quan_ly_vi_the_demo, name="Demo-Manager")

    t1.daemon = True
    t2.daemon = True

    t1.start()
    t2.start()


if __name__ == "__main__":
    chay_demo()
