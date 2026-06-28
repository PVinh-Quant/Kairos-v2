"""
utils/save_dataflie.py – Xuất dữ liệu backtest ra file
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lưu DataFrame kết quả backtest thành CSV theo đường dẫn:
  du_lieu/du_lieu_vectorized/<SYMBOL>/<SYMBOL>_<TF>_<LABEL>_<TIMESTAMP>.csv
Hỗ trợ cả Pandas DataFrame và Polars DataFrame.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import polars as pl


def luu_du_lieu_vectorized_pd(df, symbol, time_frame, label="backtest"):
    """
    Lưu trữ DataFrame đa khung thời gian sang định dạng CSV để mở trực tiếp bằng Excel.
    Tự động xử lý lỗi thư mục và làm sạch tên file.
    """
    try:

        clean_symbol = (
            str(symbol).replace("/", "_").replace("\\", "_").replace(":", "_")
        )


        base_dir = Path(__file__).resolve().parents[1]
        folder_path = base_dir / "du_lieu" / "du_lieu_vectorized" / clean_symbol


        folder_path.mkdir(parents=True, exist_ok=True)


        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_name = f"{clean_symbol}_{time_frame}_{label}_{timestamp}.csv"
        full_path = folder_path / file_name



        df.to_csv(full_path, index=True)

        print(f"✅ Đã lưu file CSV thành công!")
        print(f"📍 Đường dẫn: {full_path}")

        return str(full_path)

    except Exception as e:
        print(f"❌ Lỗi khi lưu file CSV: {e}")
        return None


def luu_du_lieu_vectorized_pl(
    df: pl.DataFrame, symbol: str, time_frame: str, label: str = "backtest"
):
    """
    Lưu trữ DataFrame đa khung thời gian sang định dạng CSV để mở trực tiếp bằng Excel.
    Tự động xử lý lỗi thư mục và làm sạch tên file.
    """
    try:

        clean_symbol = (
            str(symbol).replace("/", "_").replace("\\", "_").replace(":", "_")
        )


        base_dir = Path(__file__).resolve().parents[1]
        folder_path = base_dir / "du_lieu" / "du_lieu_vectorized" / clean_symbol


        folder_path.mkdir(parents=True, exist_ok=True)


        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_name = f"{clean_symbol}_{time_frame}_{label}_{timestamp}.csv"
        full_path = folder_path / file_name




        df.write_csv(full_path)

        print(f"✅ Đã lưu file CSV thành công!")
        print(f"📍 Đường dẫn: {full_path}")

        return str(full_path)

    except Exception as e:
        print(f"❌ Lỗi khi lưu file CSV: {e}")
        return None
