import sys
import os
import time
import json
import matplotlib
import polars as pl
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from utils.log import logger
    from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
    from utils.save_dataflie import luu_du_lieu_vectorized_pl
    from ml.tool.trading_teacher import detect_regime_vectorized
    from lay_du_lieu.lay_ohlcv import tai_du_lieu_lich_su
    from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml_vector
    from ml.trang_thai_thi_truong_ml.ml_model import huan_luyen_tu_dataframe

    from ml.tool.regime_tren_ui import hien_thi_regime_tren_ui

except ImportError as e:
    logger.error(f"Lỗi Import: {e}")
    logger.info(
        "Vui lòng chạy script từ thư mục gốc hoặc đảm bảo cấu trúc thư mục đúng."
    )
    sys.exit(1)


def vectorized_backtest():
    """Chạy backtest vectorized cho tất cả symbol trong cấu hình, lưu kết quả và hiển thị biểu đồ."""
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    START_DATE = config_backtest.get("ngay_bat_dau", "")
    END_DATE = config_backtest.get("ngay_ket_thuc", "")

    DS_SYMBOL = config_trading.get("cap_giao_dich", [])

    logger.info(f"Bắt đầu training ML: {START_DATE} -> {END_DATE}")

    for symbol in DS_SYMBOL:
        logger.info(f"Đang xử lý cặp: {symbol}")
        df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)

        df = du_doan_trang_thai_ml_vector(df_goc)
        luu_du_lieu_vectorized_pl(df, symbol, "1m")
        hien_thi_regime_tren_ui(df)
        time.sleep(1000)                             


if __name__ == "__main__":
    vectorized_backtest()
