"""
ml/trang_thai_thi_truong_ml/ml_model.py – PyTorch MLP phân loại regime thị trường
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kiến trúc TradingMLP:
  Input (18 features × 4 TF = 72+8 ctx = 80 dim)
  → Linear + BatchNorm + GELU
  → 3 × ResBlock (256 dim, Dropout 0.3)
  → Linear(256→64) + BN + GELU + Dropout
  → Linear(64→8 classes)

8 Regime: Đóng_Băng / Nén_Chặt / Đầu_XH / XH_Mạnh /
          Cao_Trào / Hồi_Quy / Nhiễu_Động / Quét_TK

Huấn luyện online: bot tự ghi log kết quả → tu_dong_hoc_tu_log() tái huấn luyện
khi có đủ dữ liệu thực chiến (reinforcement learning đơn giản).
"""

import os
import json
import random
import pandas as pd
import polars as pl
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.model_selection import train_test_split
from .tao_feature import feature_dataset, features_vectorized

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

FILE_PATH = Path(__file__).resolve()
ROOT_DIR = FILE_PATH.parent.parent.parent
for parent in FILE_PATH.parents:
    if (parent / "du_lieu_ml").exists():
        ROOT_DIR = parent
        break

DATA_DI = os.path.join(ROOT_DIR, "trang_thai_thi_truong_ml")
DATA_DIR = os.path.join(ROOT_DIR, "du_lieu_ml")

MODEL_PATH = os.path.join(DATA_DIR, "model_pytorch.pth")
SCALER_PATH = os.path.join(DATA_DIR, "scaler_params.json")
INFO_PATH = os.path.join(DATA_DIR, "model_info.json")


class MyTorchScaler:
    """Z-score scaler thuần PyTorch – tránh dùng sklearn để không bị dependency mismatch giữa train/inference."""

    def __init__(self):
        self.mean = None
        self.std = None

    def fit(self, x_tensor):
        """Tính mean và std từ tensor huấn luyện."""
        self.mean = x_tensor.mean(dim=0).cpu()
        self.std = x_tensor.std(dim=0).cpu()
        self.std[self.std == 0] = 1e-7

    def transform(self, x_tensor):
        """Chuẩn hóa tensor đầu vào theo mean/std đã fit."""
        if self.mean is None:
            raise ValueError("Scaler chưa fit!")
        return (x_tensor - self.mean.to(x_tensor.device)) / self.std.to(x_tensor.device)

    def save(self, path):
        """Lưu mean/std xuống file JSON."""
        with open(path, "w") as f:
            json.dump({"mean": self.mean.tolist(), "std": self.std.tolist()}, f)

    def load(self, path):
        """Nạp mean/std từ file JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        self.mean = torch.tensor(data["mean"])
        self.std = torch.tensor(data["std"])


class ResBlock(nn.Module):
    """Residual block: giúp gradient không bị vanish khi mạng sâu, GELU thay ReLU để smooth hơn."""

    def __init__(self, dim, dropout_rate=0.3):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )

    def forward(self, x):

        return torch.nn.functional.gelu(x + self.block(x))


class TradingMLP(nn.Module):
    """
    MLP phân loại 8 regime. Input → 3 ResBlock → Output.
    Kaiming He init giúp hội tụ nhanh từ epoch đầu.
    """

    def __init__(self, input_dim, output_dim, hidden_dim=256, dropout_rate=0.3):
        super(TradingMLP, self).__init__()


        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout_rate * 0.5),
        )


        self.res_blocks = nn.Sequential(
            ResBlock(hidden_dim, dropout_rate),
            ResBlock(hidden_dim, dropout_rate),
            ResBlock(hidden_dim, dropout_rate),
        )


        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(64, output_dim),
        )


        self.apply(self._init_weights)

    def _init_weights(self, m):
        """Giúp mô hình hội tụ nhanh hơn ngay từ Epoch đầu tiên."""
        if isinstance(m, nn.Linear):
            nn.init.kaiming_normal_(m.weight, mode="fan_in", nonlinearity="relu")
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)

    def forward(self, x):
        """Truyền xuôi qua input_layer, res_blocks và output_layer."""
        x = self.input_layer(x)
        x = self.res_blocks(x)
        return self.output_layer(x)


class AI_Engine:
    """Singleton wrapper load model + scaler từ file, cung cấp hàm predict() cho inference."""

    def __init__(self, model_path=MODEL_PATH):
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.load(model_path)

    def load(self, model_path):
        """Nạp model và scaler từ file; in cảnh báo nếu thiếu file."""
        if not os.path.exists(model_path) or not os.path.exists(SCALER_PATH):
            print(
                f"❌ CẢNH BÁO: Không tìm thấy model tại {model_path} hoặc Scaler tại {SCALER_PATH}"
            )
            return

        try:
            with open(INFO_PATH, "r") as f:
                info = json.load(f)
            self.feature_names = info.get("feature_names", [])
            input_dim = info["input_dim"]


            output_dim = info.get("output_dim", 8)

            self.model = TradingMLP(input_dim, output_dim).to(device)
            self.model.load_state_dict(
                torch.load(model_path, map_location=device, weights_only=True)
            )
            self.model.eval()
            self.scaler = MyTorchScaler()
            self.scaler.load(SCALER_PATH)
        except Exception as e:
            print(f"❌ CRITICAL ERROR khi load model: {e}")
            raise e

    def predict(self, feature_vector_dict, explore=True):
        """Dự đoán regime từ dict feature; hỗ trợ epsilon-greedy exploration."""
        if not self.model:

            raise RuntimeError("Chưa load model mà đã gọi hàm predict!")

        vals = []
        for name in self.feature_names:
            vals.append(feature_vector_dict.get(name, 0.0))

        x_tensor = torch.tensor(vals, dtype=torch.float32).unsqueeze(0).to(device)

        with torch.no_grad():
            x_scaled = self.scaler.transform(x_tensor)
            logits = self.model(x_scaled)
            probs = torch.softmax(logits, dim=1)[0]
            conf, pred_class = torch.max(probs, 0)


        if explore and conf.item() < 0.2:
            pred_class = torch.tensor(random.randint(0, probs.shape[0] - 1)).to(device)
            conf = torch.tensor(0.1).to(device)

        return int(pred_class.item()), float(conf.item()), probs.tolist()



def huan_luyen_model(df_5m, df_15m, df_1h, df_4h):
    """Huấn luyện model từ dữ liệu 4 khung thời gian hoặc tạo 'bộ não trắng' nếu chưa có log."""
    os.makedirs(DATA_DIR, exist_ok=True)
    log_path = os.path.join(DATA_DIR, "trading_memory.csv")

    X_list, y_list = [], []
    VALID_FEATURES = []


    if os.path.exists(log_path):
        try:
            df_log = pd.read_csv(log_path)
            if len(df_log) >= 10:
                print(
                    f"🧠 Phát hiện {len(df_log)} mẫu kinh nghiệm. AI đang học từ thực tế..."
                )
                for _, row in df_log.iterrows():
                    try:
                        if pd.isna(row["correct"]):
                            continue
                        feats = json.loads(row["features_json"])
                        label = int(row["correct"])
                        X_list.append(list(feats.values()))
                        y_list.append(label)
                        if not VALID_FEATURES:
                            VALID_FEATURES = list(feats.keys())
                    except:
                        continue
        except Exception as e:
            print(f"❌ Lỗi đọc log: {e}")


    if len(X_list) < 10:
        print(
            "⚠️ Không có dữ liệu log. Tiến hành khởi tạo 'Bộ não trắng' để thu thập dữ liệu..."
        )
        feats = feature_dataset(df_5m, df_15m, df_1h, df_4h)

        if feats is None or feats.empty:
            print("❌ Lỗi: Không trích xuất được features hiện tại.")
            return

        df_feat = pd.DataFrame(feats).ffill().fillna(0.0)
        VALID_FEATURES = df_feat.columns.tolist()
        INPUT_DIM = len(VALID_FEATURES)
        OUTPUT_DIM = 8



        scaler = MyTorchScaler()
        scaler.mean = torch.zeros(INPUT_DIM, dtype=torch.float32)
        scaler.std = torch.ones(INPUT_DIM, dtype=torch.float32)
        scaler.save(SCALER_PATH)



        model = TradingMLP(INPUT_DIM, OUTPUT_DIM).to(device)
        torch.save(model.state_dict(), MODEL_PATH)


        with open(INFO_PATH, "w") as f:
            json.dump(
                {
                    "input_dim": INPUT_DIM,
                    "output_dim": OUTPUT_DIM,
                    "feature_names": VALID_FEATURES,
                },
                f,
            )

        print(
            f"✅ Đã tạo xong 'Bộ não trắng' (Input: {INPUT_DIM}). Các file weights, scaler, info đã được lưu!"
        )
        print(
            "ℹ️ Hệ thống KAIROS giờ có thể tiếp tục chạy để dự đoán mù và ghi Log. Hãy chạy lại hàm train khi có đủ dữ liệu thực tế."
        )

        return

    X_tensor = torch.tensor(X_list, dtype=torch.float32)
    y_tensor = torch.tensor(y_list, dtype=torch.long).to(device)

    scaler = MyTorchScaler()
    scaler.fit(X_tensor)
    X_train_scaled = scaler.transform(X_tensor).to(device)
    scaler.save(SCALER_PATH)

    INPUT_DIM = X_train_scaled.shape[1]
    OUTPUT_DIM = 8
    model = TradingMLP(INPUT_DIM, OUTPUT_DIM).to(device)

    optimizer = optim.AdamW(model.parameters(), lr=0.001)

    counts = np.bincount(y_list, minlength=8)
    weights = torch.tensor(
        (1.0 / (counts + 1)) / (1.0 / (counts + 1)).sum() * 8, dtype=torch.float32
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    print(f"🚀 Đang huấn luyện bộ lọc trên {len(X_list)} mẫu (Device: {device})...")
    model.train()
    for epoch in range(50):
        optimizer.zero_grad()
        outputs = model(X_train_scaled)
        loss = criterion(outputs, y_tensor)
        loss.backward()
        optimizer.step()

    torch.save(model.state_dict(), MODEL_PATH)
    with open(INFO_PATH, "w") as f:
        json.dump(
            {
                "input_dim": INPUT_DIM,
                "output_dim": OUTPUT_DIM,
                "feature_names": VALID_FEATURES,
            },
            f,
        )

    print(f"✅ Đã cập nhật xong Bộ lọc AI. Model sẵn sàng chạy (Input: {INPUT_DIM}).")


def tu_dong_hoc_tu_log():
    """Đọc trading_memory.csv và tinh chỉnh model theo kinh nghiệm thực chiến."""
    log_path = os.path.join(DATA_DIR, "trading_memory.csv")
    if not os.path.exists(log_path):
        return

    print("🧠 Đang ôn bài từ kinh nghiệm thực chiến...")
    try:
        df_log = pd.read_csv(log_path)
    except Exception as e:
        return


    good_memories = df_log[df_log["reward"] > 0.0].copy()
    bad_memories = df_log[df_log["reward"] < 0.0].copy()

    if len(good_memories) + len(bad_memories) < 10:
        return

    X_list, y_list = [], []


    for _, row in good_memories.iterrows():
        try:
            feats = (
                json.loads(row["features_json"])
                if isinstance(row["features_json"], str)
                else row["features_json"]
            )
            X_list.append(list(feats.values()))
            y_list.append(int(row["state"]))
        except:
            continue


    if len(bad_memories) > 0:
        for _, row in bad_memories.iterrows():
            try:
                feats = (
                    json.loads(row["features_json"])
                    if isinstance(row["features_json"], str)
                    else row["features_json"]
                )
                wrong_state = int(row["state"])
                corrected_state = wrong_state

                has_teacher = (
                    "correct" in row
                    and pd.notna(row["correct"])
                    and row["correct"] != ""
                )
                if has_teacher:
                    corrected_state = int(row["correct"])
                else:

                    if wrong_state in [0, 1, 3]:
                        corrected_state = 2
                    elif wrong_state == 2:
                        corrected_state = 0
                    elif wrong_state == 5:
                        corrected_state = 0

                if corrected_state != wrong_state:
                    X_list.append(list(feats.values()))
                    y_list.append(corrected_state)
            except:
                continue

    if not X_list:
        return


    X_train = torch.tensor(X_list, dtype=torch.float32)
    y_train = torch.tensor(y_list, dtype=torch.long).to(device)


    engine = AI_Engine()


    input_dim_new = X_train.shape[1]
    input_dim_old = 0


    if engine.scaler is not None and engine.scaler.mean is not None:
        input_dim_old = engine.scaler.mean.shape[0]

    model = None
    scaler = None


    if input_dim_new != input_dim_old:
        print(
            f"⚠️ Phát hiện thay đổi dữ liệu (Cũ: {input_dim_old} -> Mới: {input_dim_new}). Tiến hành huấn luyện lại từ đầu..."
        )


        scaler = MyTorchScaler()
        scaler.fit(X_train)


        model = TradingMLP(input_dim_new, 8).to(device)


        engine.model = model
        engine.scaler = scaler


        with open(INFO_PATH, "w") as f:

            feature_names_new = []
            try:
                first_row_feat = json.loads(good_memories.iloc[0]["features_json"])
                feature_names_new = list(first_row_feat.keys())
            except:
                pass

            json.dump(
                {
                    "input_dim": input_dim_new,
                    "output_dim": 8,
                    "feature_names": feature_names_new,
                },
                f,
            )

    else:

        print(f"✅ Dữ liệu khớp ({input_dim_new} features). Đang tinh chỉnh model...")
        model = engine.model
        scaler = engine.scaler


    model.train()
    optimizer = optim.Adam(model.parameters(), lr=0.0001)
    criterion = nn.CrossEntropyLoss()



    X_train_scaled = scaler.transform(X_train).cpu()
    y_train_cpu = y_train.cpu()



    batch_size = 256
    dataset = TensorDataset(X_train_scaled, y_train_cpu)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)


    model.train()
    optimizer = optim.Adam(model.parameters(), lr=0.0001)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(10):
        total_loss = 0.0
        for batch_X, batch_y in dataloader:

            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        print(f"  + Epoch {epoch+1}/10 - Loss: {total_loss/len(dataloader):.4f}")


    torch.save(model.state_dict(), MODEL_PATH)
    scaler.save(SCALER_PATH)

    print(
        f"✅ Đã học xong {len(X_list)} bài học mới trên GPU (Input: {input_dim_new})."
    )


def huan_luyen_tu_dataframe(df_labeled: pl.DataFrame, epochs=20, batch_size=512):
    """
    Nhận DataFrame đã được label bởi detect_regime_vectorized.
    Trích xuất feature, CẮT 30 NGÀY NHIỄU, CHỈ CẮT GỌT CLASS LỚN (KHÔNG NHÂN BẢN) và huấn luyện Model.
    """
    print("🧠 BƯỚC 1: Đang trích xuất Features (Vectorized)...")

    engine = AI_Engine()
    if engine.model is not None and engine.scaler is not None:
        print("🧠 Chạy mô phỏng tuần tự (rollout) trên tập train bằng model hiện tại...")
        from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml_vector
        df_rollout = du_doan_trang_thai_ml_vector(df_labeled)
        df_feat = features_vectorized(df_rollout)
    else:
        print("⚠️ Không tìm thấy model hiện tại. Sử dụng Teacher forcing làm dữ liệu khởi động...")
        df_feat = features_vectorized(df_labeled)


    df_final = df_feat.join(
        df_labeled.select(["timestamp", "regime"]), on="timestamp", how="inner"
    )




    df_final = df_final.sort("timestamp")

    DROP_ROWS = 30 * 24 * 60
    if df_final.height > DROP_ROWS:
        df_final = df_final.slice(DROP_ROWS)
        print(f"✂️ Đã cắt bỏ {DROP_ROWS} nến (30 ngày đầu) để loại bỏ nhiễu chỉ báo.")
    else:
        print("⚠️ Cảnh báo: Dữ liệu quá ngắn, không đủ 30 ngày để cắt!")


    feature_cols = [
        col for col in df_final.columns if col not in ["timestamp", "regime"]
    ]




    n_total = len(df_final)
    n_train_split = int(n_total * 0.8)

    df_train = df_final.slice(0, n_train_split)
    df_val = df_final.slice(n_train_split)

    X_train_full = df_train.select(feature_cols).to_numpy()
    y_train_full = df_train.select("regime").to_numpy().flatten()

    X_val_np = df_val.select(feature_cols).to_numpy()
    y_val_np = df_val.select("regime").to_numpy().flatten()

    print(f"📊 Dữ liệu trước cân bằng: Train = {len(X_train_full)}, Val = {len(X_val_np)} mẫu.")




    counts = np.bincount(y_train_full, minlength=8)
    print(f"📈 Phân bổ nhãn Train trước cân bằng: {counts}")


    minority_counts = counts[1:]
    valid_minorities = minority_counts[minority_counts > 0]

    if len(valid_minorities) > 0:

        limit_cap = int(np.min(valid_minorities))
    else:

        limit_cap = len(y_train_full)

    print(f"🎯 Thiết lập Mức Trần (Cap Limit) cho Train: {limit_cap} dòng.")

    balanced_indices = []
    for c in range(8):
        if counts[c] == 0:
            continue

        idx_c = np.where(y_train_full == c)[0]


        current_limit = int(limit_cap * 1.5) if c == 0 else limit_cap


        current_limit = min(current_limit, counts[c])

        if counts[c] > current_limit:

            idx_sampled = np.random.choice(idx_c, current_limit, replace=False)
            print(f"  🔻 Cắt gọt Train Regime {c}: {counts[c]} -> {current_limit} dòng")
        else:

            idx_sampled = idx_c
            print(f"  ✅ Giữ nguyên Train Regime {c}: {counts[c]} dòng")

        balanced_indices.extend(idx_sampled)


    np.random.shuffle(balanced_indices)

    X_train_np = X_train_full[balanced_indices]
    y_train_np = y_train_full[balanced_indices]
    print(f"🚀 Dữ liệu Train CHUẨN sau khi cân bằng: {len(X_train_np)} mẫu. Bắt đầu Train!")



    X_train_tensor = torch.tensor(X_train_np, dtype=torch.float32)
    y_train_tensor = torch.tensor(y_train_np, dtype=torch.long)

    scaler = MyTorchScaler()
    scaler.fit(X_train_tensor)
    X_scaled = scaler.transform(X_train_tensor)
    scaler.save(SCALER_PATH)


    X_val_tensor = None
    y_val_tensor = None
    if len(X_val_np) > 0:
        X_val_tensor = scaler.transform(torch.tensor(X_val_np, dtype=torch.float32))
        y_val_tensor = torch.tensor(y_val_np, dtype=torch.long)


    input_dim = len(feature_cols)
    output_dim = 8
    model = TradingMLP(input_dim, output_dim).to(device)


    dataset = TensorDataset(X_scaled, y_train_tensor)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)


    criterion = nn.CrossEntropyLoss().to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)

    print(f"🔥 BƯỚC 3: Bắt đầu huấn luyện Model trên {device}...")
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for batch_X, batch_y in dataloader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if (epoch + 1) % 5 == 0 or epoch == 0:
            msg = f"   + Epoch {epoch+1}/{epochs} | Loss: {total_loss/len(dataloader):.4f}"


            if X_val_tensor is not None:
                model.eval()
                with torch.no_grad():
                    val_X = X_val_tensor.to(device)
                    val_y = y_val_tensor.to(device)
                    val_logits = model(val_X)
                    val_loss = criterion(val_logits, val_y).item()
                    val_acc = (val_logits.argmax(dim=1) == val_y).float().mean().item()
                model.train()
                msg += f" | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2%}"

            print(msg)


    torch.save(model.state_dict(), MODEL_PATH)
    with open(INFO_PATH, "w") as f:
        json.dump(
            {
                "input_dim": input_dim,
                "output_dim": output_dim,
                "feature_names": feature_cols,
            },
            f,
        )

    print("✅ Đã học xong và lưu Model!")
