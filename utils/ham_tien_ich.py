"""
utils/ham_tien_ich.py – Hàm tiện ích đa năng
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tập hợp các hàm được dùng ở nhiều tầng khác nhau:
  • Chuẩn hóa symbol giữa các sàn (BTC/USDT vs BTCUSDT vs BTC-USDT-SWAP)
  • Tính PnL theo side
  • Merge multi-timeframe data không lookahead
"""

import pandas as pd
import numpy as np
import polars as pl


def chuyen_doi_symbol_chuan(san, symbol):
    """
    Chuẩn hóa symbol về dạng BASE/QUOTE (VD: 'BTCUSDT' -> 'BTC/USDT').
    Xử lý đặc biệt cho OKX (BTC-USDT-SWAP -> BTC/USDT).
    """
    if not symbol:
        return symbol

    symbol = symbol.upper().strip()
    san = san.lower().strip() if san else "binance"

    if "/" in symbol:
        return symbol

    if san == "okx":
        clean_symbol = symbol.replace("-SWAP", "").replace("-", "/")
        return clean_symbol

    quote_currencies = ["USDT", "USDC", "BUSD", "TUSD", "DAI", "BTC", "ETH", "BNB"]

    for quote in quote_currencies:
        if symbol.endswith(quote):
            base = symbol[: -len(quote)]
            return f"{base}/{quote}"
    return f"{symbol}/USDT"


def tinh_pnl(entry, current_price, side, amount):
    """Tính PnL tuyệt đối (USDT) và tương đối (%) cho cả long lẫn short."""
    if side == "buy":
        pnl_usdt = (current_price - entry) * amount
        pnl_percent = (current_price - entry) / entry
    else:
        pnl_usdt = (entry - current_price) * amount
        pnl_percent = (entry - current_price) / entry
    return pnl_usdt, pnl_percent


def gop_va_dong_bo_data(dfs_dict):
    """
    Merge nhiều DataFrame khác khung thời gian thành 1 DataFrame gốc 1m.
    Dùng merge_asof (backward) để tránh lookahead – indicator HTF chỉ forward-fill.
    """

    def chuẩn_hóa_df(df, name):
        """Làm sạch và chuẩn hóa tên cột, đảm bảo cột timestamp tồn tại."""
                                                                   
        df = df.loc[:, ~df.columns.str.contains("^unnamed", case=False)]

                          
        if "" in df.columns:
            df = df.drop(columns=[""])

                                         
        df.columns = [col.strip().lower() for col in df.columns]

                                                              
        if "timestamp" not in df.columns:
            if df.index.name and df.index.name.lower() == "timestamp":
                df = df.reset_index()
            else:
                raise KeyError(f"Không tìm thấy cột 'timestamp' trong khung {name}.")

        df["timestamp"] = pd.to_datetime(df["timestamp"])

                                         
        return df.sort_values("timestamp").reset_index(drop=True)

                          
    if "1m" not in dfs_dict:
        return None

    main_df = chuẩn_hóa_df(dfs_dict["1m"].copy(), "1m")

    for tf, df in dfs_dict.items():
        if tf == "1m":
            continue

        df_tf = chuẩn_hóa_df(df.copy(), tf)

                                                                     
        cols_to_exclude = ["open", "high", "low", "close", "volume"]
        cols_to_use = [
            col
            for col in df_tf.columns
            if col not in cols_to_exclude or col == "timestamp"
        ]

        main_df = pd.merge_asof(
            main_df,
            df_tf[cols_to_use],
            on="timestamp",
            direction="backward",
            suffixes=("", f"_{tf}"),                                               
        )

                                                      
                                                      
    main_df.set_index("timestamp", inplace=True)

                                        
    if "index" in main_df.columns:
        main_df.drop(columns=["index"], inplace=True)

    return main_df


def gop_va_dong_bo_data_polars(dfs_dict):
    """
    Merge nhiều Polars DataFrame khác khung thời gian thành 1 DataFrame gốc 1m.
    Dùng join_asof (backward) để tránh lookahead.
    """
    def chuẩn_hóa_df_pl(df, name):
        clean_cols = [c for c in df.columns if c and not c.lower().startswith("unnamed") and c != "index"]
        df_clean = df.select(clean_cols)
        df_clean = df_clean.rename({c: c.strip().lower() for c in df_clean.columns})
        if "timestamp" not in df_clean.columns:
            raise KeyError(f"Không tìm thấy cột 'timestamp' trong khung {name}.")
        if df_clean.schema["timestamp"] in (pl.String, pl.Utf8):
            df_clean = df_clean.with_columns(pl.col("timestamp").str.to_datetime())
        return df_clean.sort("timestamp")

    if "1m" not in dfs_dict:
        return None

    main_df = chuẩn_hóa_df_pl(dfs_dict["1m"], "1m")

    for tf, df in dfs_dict.items():
        if tf == "1m":
            continue

        df_tf = chuẩn_hóa_df_pl(df, tf)

        cols_to_exclude = ["open", "high", "low", "close", "volume"]
        cols_to_use = [
            col
            for col in df_tf.columns
            if col not in cols_to_exclude or col == "timestamp"
        ]

        rename_map = {}
        for col in cols_to_use:
            if col == "timestamp":
                continue
            if col in main_df.columns:
                rename_map[col] = f"{col}_{tf}"

        if rename_map:
            df_tf_sub = df_tf.select(cols_to_use).rename(rename_map)
        else:
            df_tf_sub = df_tf.select(cols_to_use)

        main_df = main_df.join_asof(df_tf_sub, on="timestamp", strategy="backward")

    return main_df

