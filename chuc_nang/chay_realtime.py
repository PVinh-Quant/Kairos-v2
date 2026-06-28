"""
chuc_nang/chay_realtime.py – Bot giao dịch tự động (Live Trading)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2 thread chạy song song:
  • Thread-Scanner  (luong_quet_thi_truong)  – quét từng coin, phát hiện tín hiệu,
                                               đặt lệnh thật qua CCXT
  • Thread-Manager  (luong_quan_ly_vi_the)   – theo dõi vị thế đang mở,
                                               đóng lệnh khi SL/TP/tín hiệu đảo chiều

Sau mỗi lệnh đóng: ghi reward vào trading_memory.csv để AI tự học kinh nghiệm.
"""

import threading
import time
import sys
import os
import signal
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_thong_tin_san
from utils.chuyen_doi_don_vi import (
    usdt_sang_so_luong_coin,
    lam_tron_khoi_luong,
    mili_giay_sang_phut,
)
from utils.thoi_gian import ngu_an_toan, lay_timestamp_ms
from utils.ham_tien_ich import chuyen_doi_symbol_chuan, tinh_pnl

from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from thong_bao.gui_telegram import gui_tin_nhan_telegram
from utils.log import logger
from lay_du_lieu.lay_ohlcv import lay_du_lieu_nen
from lay_du_lieu.lay_marketsnapshot import mo_theo_doi, dong_theo_doi
from thuc_thi_lenh import quan_ly_lenh
from lay_du_lieu.lay_thong_tin_tai_khoan import lay_so_du_kha_dung
from thuc_thi_lenh.mo_lenh import thuc_hien_mo_lenh
from thuc_thi_lenh.dong_lenh import thuc_hien_dong_lenh
from thuc_thi_lenh.theo_doi_lenh import kiem_tra_trang_thai_vi_the
from thuc_thi_lenh.quan_ly_danh_muc import kiem_tra_phan_bo_von

from chien_luoc.quan_ly_chien_luoc_bar_to_bar import (
    chien_luoc_vao_lenh,
    chien_luoc_thoat_lenh,
    danh_gia_ml,
)
from utils.kho_du_lieu import luu_lenh_don, luu_run, tao_run_id

CONFIG = lay_cau_hinh_giao_dich()
SAN_CHINH = CONFIG.get("san_giao_dich_chinh", "binance").lower()
raw_coins = CONFIG.get("cap_giao_dich", [])
DON_BAY = int(
    CONFIG.get(
        "don_bay",
    )
)
COOLDOWN_NEN = int(CONFIG.get("cooldown_nen", 5))
GIAY_COOLDOWN = COOLDOWN_NEN * 60

LIST_COIN = [chuyen_doi_symbol_chuan(SAN_CHINH, coin) for coin in raw_coins]

VON_BAN_DAU = float(lay_so_du_kha_dung(SAN_CHINH, "USDT"))

MAX_OPEN_ORDERS = CONFIG.get("max_lenh_cho_phep")

CHUC_NANG = "realtime"
DANG_CHAY = True
REALTIME_RUN_ID = tao_run_id()
data_san = lay_thong_tin_san()
MIN_NOTIONAL = data_san.get(SAN_CHINH, {}).get("min_notional", 5.0)
VON_MOI_LENH = float(CONFIG.get("von_moi_lenh_usdt", 0) or 0)


def luong_quet_thi_truong():
    """Luồng quét từng coin tìm tín hiệu vào lệnh và đặt lệnh thật qua CCXT."""
    logger.info(f"Bắt đầu quét thị trường trên {SAN_CHINH}...")

    while DANG_CHAY:

        so_lenh_dang_mo = len(quan_ly_lenh.lay_danh_sach_symbol_dang_co())
        if not kiem_tra_phan_bo_von(
            VON_BAN_DAU, so_lenh_dang_mo, max_lenh_cho_phep=MAX_OPEN_ORDERS
        ):
            logger.info("Đã đạt giới hạn số lệnh. Tạm nghỉ quét...")
            ngu_an_toan(60)
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

                    san = quan_ly_san.lay_san(SAN_CHINH)
                    ticker = san.fetch_ticker(symbol)
                    gia_hien_tai = ticker["last"]

                    gia_tri_lenh = CONFIG["von_moi_lenh_usdt"] * don_bay

                    if gia_tri_lenh < MIN_NOTIONAL:
                        logger.warning(
                            f"Giá trị lệnh {gia_tri_lenh}$ < Min {MIN_NOTIONAL}$. Bỏ qua."
                        )
                        continue

                    so_luong_raw = usdt_sang_so_luong_coin(gia_tri_lenh, gia_hien_tai)
                    so_luong = lam_tron_khoi_luong(so_luong_raw, precision_amount=4)

                    order = thuc_hien_mo_lenh(
                        SAN_CHINH, symbol, tin_hieu, so_luong, don_bay=don_bay
                    )

                    if order:

                        sl_pct = float(packet.get("sl_pct") or 0.0)
                        tp_pct = float(packet.get("tp_pct") or 0.0)
                        if tin_hieu == "buy":
                            sl_price = gia_hien_tai * (1 - sl_pct)
                            tp_price = gia_hien_tai * (1 + tp_pct)
                        else:
                            sl_price = gia_hien_tai * (1 + sl_pct)
                            tp_price = gia_hien_tai * (1 - tp_pct)

                        quan_ly_lenh.luu_lenh_moi(
                            CHUC_NANG,
                            symbol,
                            {
                                "side": tin_hieu,
                                "entry_price": gia_hien_tai,
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

                        gui_tin_nhan_telegram(
                            f"KHOP LENH {symbol}: {tin_hieu.upper()} {symbol}\nGia: {gia_hien_tai}\nSL: {sl_price} | TP: {tp_price}"
                        )

                end_time = lay_timestamp_ms()
                thoi_gian_xu_ly_ms = end_time - start_time
                if thoi_gian_xu_ly_ms > 2000:
                    logger.warning(
                        f"Mạng chậm! {symbol} xử lý mất {thoi_gian_xu_ly_ms:.0f}ms"
                    )

            except Exception as e:
                logger.error(f"Lỗi quét {symbol}: {e}")

            ngu_an_toan(0.075)

        ngu_an_toan(5)


def luong_quan_ly_vi_the():
    """Luồng theo dõi vị thế đang mở trên sàn, đóng lệnh khi chạm SL/TP hoặc tín hiệu đảo chiều."""
    logger.info("Bắt đầu quản lý vị thế...")




    von_uoc_tinh = VON_BAN_DAU
    dinh_tai_khoan = von_uoc_tinh

    while DANG_CHAY:
        try:
            ds_symbol = quan_ly_lenh.lay_danh_sach_symbol_dang_co()

            if not ds_symbol:
                ngu_an_toan(5)
                continue

            for symbol in ds_symbol:
                info_lenh = quan_ly_lenh.lay_thong_tin_lenh(symbol)

                vi_the = kiem_tra_trang_thai_vi_the(SAN_CHINH, symbol)

                if not vi_the:
                    logger.warning(
                        f"Không tìm thấy vị thế {symbol} trên sàn -> Xóa khỏi bot."
                    )
                    quan_ly_lenh.xoa_lenh(CHUC_NANG, symbol)
                    continue

                lai_lo_percent = vi_the["pnl_percent"]
                size = vi_the["amount"]
                vi_the_side = vi_the["side"]

                try:
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

                    sl_price = info_lenh.get("sl_price")
                    tp_price = info_lenh.get("tp_price")
                    chien_luoc = info_lenh.get("chien_luoc")

                    packet_ml = info_lenh.get("packet_ml")

                    can_thoat = False
                    ly_do = ""
                    gia_dong_du_kien = gia_hien_tai

                    if sl_price and tp_price:
                        if vi_the_side == "buy":
                            if gia_high >= tp_price:
                                can_thoat = True
                                ly_do = f"Chạm giá TP ({gia_high} >= {tp_price})"
                                gia_dong_du_kien = tp_price
                            elif gia_low <= sl_price:
                                can_thoat = True
                                ly_do = f"Chạm giá SL ({gia_low} <= {sl_price})"
                                gia_dong_du_kien = sl_price
                        elif vi_the_side == "sell":
                            if gia_low <= tp_price:
                                can_thoat = True
                                ly_do = f"Chạm giá TP ({gia_low} <= {tp_price})"
                                gia_dong_du_kien = tp_price
                            elif gia_high >= sl_price:
                                can_thoat = True
                                ly_do = f"Chạm giá SL ({gia_high} >= {sl_price})"
                                gia_dong_du_kien = sl_price


                    if not can_thoat:
                        can_thoat_som, ly_do_thoat = chien_luoc_thoat_lenh(
                            symbol,
                            vi_the_side,
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
                        if can_thoat_som:
                            can_thoat = True
                            ly_do = f"SIGNAL ({ly_do_thoat})"

                    if can_thoat:
                        logger.info(f"Dang dong {symbol}: {ly_do}")

                        ket_qua = thuc_hien_dong_lenh(
                            SAN_CHINH, symbol, vi_the_side, size
                        )
                        if ket_qua:

                            lich_su = {
                                "day": datetime.now().strftime("%Y-%m-%d"),
                                "symbol": symbol,
                                "side": vi_the_side,
                                "entry_price": info_lenh["entry_price"],
                                "exit_price": gia_dong_du_kien,
                                "open_time": info_lenh["time"],
                                "close_time": datetime.now().strftime("%H:%M:%S"),
                                "pnl": lai_lo_percent,
                                "score": info_lenh["diem"],
                                "strategy": chien_luoc,
                                "reason": ly_do,
                                "leverage": info_lenh.get("leverage", 1),
                                "so_du": 0.0,
                                "packet_ml": packet_ml,
                            }

                            luu_lenh_don(REALTIME_RUN_ID, "realtime", lich_su)
                            quan_ly_lenh.lich_su_lenh(CHUC_NANG, lich_su)
                            quan_ly_lenh.xoa_lenh(CHUC_NANG, symbol)
                            gui_tin_nhan_telegram(f"Da dong {symbol}: {ly_do}")



                            von_uoc_tinh += VON_MOI_LENH * (lai_lo_percent / 100.0)
                            if von_uoc_tinh > dinh_tai_khoan:
                                dinh_tai_khoan = von_uoc_tinh
                            account_drawdown = (
                                (von_uoc_tinh - dinh_tai_khoan) / dinh_tai_khoan * 100
                                if dinh_tai_khoan
                                else 0.0
                            )


                            if packet_ml and packet_ml.get("state_name"):
                                danh_gia_ml(packet_ml, lai_lo_percent, account_drawdown)

                except Exception as e:
                    logger.error(f"Lỗi xử lý {symbol}: {e}")

                ngu_an_toan(0.2)

        except Exception as e:
            logger.error(f"Lỗi quản lý vị thế: {e}")

        ngu_an_toan(5)


def chay_realtime():
    """Khởi động bot realtime: load trạng thái cũ và chạy 2 luồng scanner + manager."""
    from utils.log import banner_khoi_dong

    banner_khoi_dong(
        "REALTIME  —  Live Trading",
        [
            ("Vốn ban đầu", f"{VON_BAN_DAU:,.2f} USDT"),
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
    luu_run(
        REALTIME_RUN_ID, "realtime",
        {"von_ban_dau": VON_BAN_DAU, "symbols": LIST_COIN, "ten_chien_luoc": _ten_cl},
    )

    try:
        quan_ly_lenh.dang_ky_chay_bot(CHUC_NANG, REALTIME_RUN_ID)
    except Exception as e:
        print(f"[chay_realtime] Lỗi đăng ký bot: {e}", flush=True)

    t1 = threading.Thread(target=luong_quet_thi_truong, name="Thread-Scanner")
    t2 = threading.Thread(target=luong_quan_ly_vi_the, name="Thread-Manager")

    t1.daemon = True
    t2.daemon = True

    t1.start()
    t2.start()


if __name__ == "__main__":
    chay_realtime()
