"""
ml/trang_thai_thi_truong_ml/ml_predict.py – Inference & đánh giá ML
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3 hàm chính:
  • du_doan_trang_thai_ml()        – dự đoán 1 cây nến (bar-to-bar, realtime)
  • du_doan_trang_thai_ml_vector() – dự đoán hàng loạt (batch inference, backtest)
  • danh_gia_ml()                  – ghi reward vào trading_memory.csv sau khi đóng lệnh

STATE_MAP định nghĩa 8 regime và chiến lược tương ứng:
  0 Đóng_Băng → không trade  |  1 Nén_Chặt → chờ breakout
  2 Đầu_XH → vào sớm         |  3 XH_Mạnh → follow trend
  4 Cao_Trào → chốt lời       |  5 Hồi_Quy → counter-trend
  6 Nhiễu_Động → range trade  |  7 Quét_TK → risk-off
"""

import os
import json
from datetime import datetime
import pandas as pd
import csv


import torch
import numpy as np
import polars as pl

from ml.trang_thai_thi_truong_ml.ml_model import AI_Engine, DATA_DIR
from ml.trang_thai_thi_truong_ml.tao_feature import feature_dataset, features_vectorized
from utils.log import logger

LOG_FILE = os.path.join(DATA_DIR, "trading_memory.csv")
engine = AI_Engine()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


STATE_MAP = {
    0: "Đóng_Băng",
    1: "Nén_Chặt",
    2: "Đầu_Xu_Hướng",
    3: "Xu_Hướng_Mạnh",
    4: "Cao_Trào",
    5: "Hồi_Quy",
    6: "Nhiễu_Động",
    7: "Quét_Thanh_Khoản",
}


STRATEGY_MAP = {
    0: None,
    1: "Squeeze",
    2: "Breakout",
    3: "Trend_following",
    4: "Mean_reversion",
    5: "Mean_reversion",
    6: "Scalping",
    7: None,
}


def du_doan_trang_thai_ml(df_5m, df_15m, df_1h, df_4h, last_state=None):
    """Dự đoán regime hiện tại (bar-to-bar) từ 4 khung thời gian; trả về ML packet hoặc None."""


    feature_dict = feature_dataset(df_5m, df_15m, df_1h, df_4h, last_state=last_state)


    if feature_dict is None or (
        isinstance(feature_dict, pd.DataFrame) and feature_dict.empty
    ):
        return None


    input_vector = {k: v.iloc[-1] for k, v in feature_dict.items()}



    state_id, conf, probs = engine.predict(input_vector)

    if state_id is None:
        return None


    strategy = STRATEGY_MAP.get(state_id)


    if strategy is None:
        return None


    packet = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state_id": state_id,
        "state_name": STATE_MAP.get(state_id, "UNKNOWN"),
        "strategy_name": strategy,
        "confidence": round(conf, 4),
        "probs": probs,
        "features_snapshot": input_vector,
    }
    return packet


def du_doan_trang_thai_ml_vector(df_1m: pl.DataFrame) -> pl.DataFrame:
    """
    Nhận DataFrame 1m gốc. Xuất ra DataFrame có cột 'regime' và 'confidence'
    do mô hình AI dự đoán (Xử lý hàng loạt - Vectorized Inference).
    """


    df_dummy = df_1m.with_columns(pl.lit(0).alias("regime"))
    df_feat = features_vectorized(df_dummy)


    if df_feat is None or df_feat.is_empty():
        return df_1m.with_columns(
            [pl.lit(0).alias("regime"), pl.lit(0.0).alias("confidence")]
        )

    engine_vector = AI_Engine()


    if engine_vector.model is None or engine_vector.scaler is None:
        print(
            "⚠️ CẢNH BÁO: AI Model hoặc Scaler chưa được huấn luyện! Trả về Regime 0 mặc định."
        )
        return df_1m.with_columns(
            [pl.lit(0).alias("regime"), pl.lit(0.0).alias("confidence")]
        )

    feature_cols = engine_vector.feature_names


    missing_cols = [c for c in feature_cols if c not in df_feat.columns]
    if len(missing_cols) > 0:
        print(
            f"❌ LỖI: Dataset bị thiếu {len(missing_cols)} cột Features (Vd: {missing_cols[:3]}). Đã Bypass về Regime 0."
        )
        return df_1m.with_columns(
            [pl.lit(0).alias("regime"), pl.lit(0.0).alias("confidence")]
        )


    X_numpy = df_feat.select(feature_cols).to_numpy().copy()
    ctx_indices = [feature_cols.index(f"ctx_last_state_{i}") for i in range(8)]


    for idx in ctx_indices:
        X_numpy[:, idx] = 0.0

    preds_np = np.zeros(len(df_feat), dtype=np.int32)
    confs_np = np.zeros(len(df_feat), dtype=np.float64)


    mean_np = engine_vector.scaler.mean.cpu().numpy()
    std_np = engine_vector.scaler.std.cpu().numpy()


    X_scaled = (X_numpy - mean_np) / std_np


    val_ctx_1 = (1.0 - mean_np[ctx_indices]) / std_np[ctx_indices]


    X_scaled_tensor = torch.tensor(X_scaled, dtype=torch.float32)

    engine_vector.model.eval()


    try:
        dummy_input = torch.randn(1, len(feature_cols)).to(device)
        model_traced = torch.jit.trace(engine_vector.model, dummy_input)
    except Exception:
        model_traced = engine_vector.model


    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)

    last_state = 0
    tong = len(df_feat)




    log_progress = tong >= 5000
    buoc_log = max(1, tong // 10)
    if log_progress:
        logger.info(f"[ML] Suy diễn regime (autoregressive) cho {tong:,} nến trên {device}...")

    try:
        with torch.no_grad():
            for t in range(tong):

                X_scaled_tensor[t, ctx_indices[last_state]] = float(val_ctx_1[last_state])


                row_tensor = X_scaled_tensor[t].unsqueeze(0).to(device)
                logits = model_traced(row_tensor)
                probs = torch.softmax(logits, dim=1)[0]
                conf, pred_class = torch.max(probs, 0)

                pred_state = int(pred_class.item())
                preds_np[t] = pred_state
                confs_np[t] = float(conf.item())


                last_state = pred_state

                if log_progress and (t + 1) % buoc_log == 0:
                    logger.info(f"[ML]   regime {t + 1:,}/{tong:,} nến ({(t + 1) * 100 // tong}%)")
    finally:

        torch.set_num_threads(old_threads)

    if log_progress:
        logger.info(f"[ML] Hoàn tất suy diễn regime cho {tong:,} nến.")


    df_results = pl.DataFrame(
        {
            "timestamp": df_feat["timestamp"],
            "regime": preds_np.astype(np.int32),
            "confidence": confs_np.astype(np.float64),
        }
    )





    cols_goc = [c for c in df_1m.columns if c not in ("regime", "confidence")]
    df_final = df_1m.select(cols_goc).join(df_results, on="timestamp", how="left").with_columns(
        [
            pl.col("regime").fill_null(0).cast(pl.Int32),
            pl.col("confidence").fill_null(0.0).cast(pl.Float64),
        ]
    )

    return df_final.select(
        ["timestamp", "open", "high", "low", "close", "volume", "regime", "confidence"]
    )


def danh_gia_ml(packet, pnl, dd, correct=None):
    """Tính reward từ PnL/DD và ghi vào trading_memory.csv để phục vụ self-supervised learning."""


    if not packet or not isinstance(packet, dict) or "state_name" not in packet:
        return

    if correct is None:
        correct = "NaN"

    state_name = packet["state_name"]



    if pnl > 0:
        reward = pnl * 1.0
    else:
        reward = pnl * 2.0


    if state_name == "Nhiễu_Động":
        if pnl < 0:
            reward -= 2.0
        elif 0 < pnl < 0.5:
            reward += 0.5
    elif state_name in (
        "Nén_Chặt",
        "Đầu_Xu_Hướng",
    ):
        if pnl < 0:
            reward -= 2.0
        elif pnl > 2.0:
            reward += 2.0
    elif (
        state_name == "Xu_Hướng_Mạnh"
    ):
        if pnl < 0:
            reward *= 1.5
        elif pnl > 3.0:
            reward += 3.0
    elif state_name in (
        "Cao_Trào",
        "Hồi_Quy",
    ):
        if pnl < -1.0:
            reward -= 3.0
        elif pnl > 1.5:
            reward += 2.0
    else:

        if dd < -1.0:
            reward -= 1.0


    reward = max(min(reward, 10), -10)



    log_row = {
        "timestamp": packet["timestamp"],
        "state": packet["state_id"],
        "correct": correct,
        "state_name": packet["state_name"],
        "confidence": packet["confidence"],
        "pnl": round(pnl, 4),
        "reward": round(reward, 4),
        "features_json": json.dumps(packet["features_snapshot"]),
    }

    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_row)
