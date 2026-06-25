"""
utils/doc_cau_hinh.py – Loader cấu hình hệ thống
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Đọc các file cấu hình từ thư mục config/ và trả về dict.
Mọi module khác đều lấy tham số qua file này thay vì hardcode.
  • tai_khoan_api.json       – API keys các sàn (KHÔNG commit lên git)
  • cau_hinh_giao_dich.yaml – danh sách coin, đòn bẩy, vốn mỗi lệnh
  • thong_tin_san.yaml       – phí giao dịch, giới hạn đòn bẩy từng sàn
  • cau_hinh_ao_config.json  – tham số paper trading (vốn ảo, phí, slippage)
"""

import json
import re
import yaml
import os
from utils.log import logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def duong_dan_config(ten_file: str) -> str:
    """Trả về đường dẫn tuyệt đối của 1 file trong thư mục config/."""
    return os.path.join(BASE_DIR, "config", ten_file)


def lay_cau_hinh_api():
    """Đọc file tai_khoan_api.json và trả về dict API keys; trả về {} nếu lỗi."""
    path = os.path.join(BASE_DIR, "config", "tai_khoan_api.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}


def lay_cau_hinh_giao_dich():
    """Đọc file cau_hinh_giao_dich.yaml và trả về dict cấu hình; trả về {} nếu lỗi.

    Khi chạy LẺ 1 chiến lược từ thư viện, tiến trình con đặt biến môi trường
    `KAIROS_RUN_SYMBOLS` (JSON list) để GIỚI HẠN `cap_giao_dich` ở đúng các coin
    người dùng đã chọn (tránh tải toàn bộ coin). App chính không đặt biến này → không ảnh hưởng.
    """
    path = os.path.join(BASE_DIR, "config", "cau_hinh_giao_dich.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}
    ovr = os.environ.get("KAIROS_RUN_SYMBOLS")
    if ovr:
        try:
            syms = json.loads(ovr)
            if isinstance(syms, list) and syms:
                cfg = dict(cfg)
                cfg["cap_giao_dich"] = syms
        except Exception:
            pass
    return cfg


def lay_thong_tin_san():
    """Đọc file thong_tin_san.yaml và trả về dict thông tin sàn; trả về {} nếu lỗi."""
    path = os.path.join(BASE_DIR, "config", "thong_tin_san.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except:
        return {}


def lay_cau_hinh_ao():
    """Đọc file cau_hinh_ao_config.json và trả về dict; dùng giá trị mặc định nếu lỗi.

    Khi chạy LẺ backtest từ thư viện, tiến trình con đặt `KAIROS_RUN_TU_NGAY` /
    `KAIROS_RUN_DEN_NGAY` (yyyy-MM-dd) để giới hạn khoảng dữ liệu cần tải.
    """
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "cau_hinh_ao_config.json"
    )
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            cfg = json.loads(content)
    except Exception as e:
        logger.warning(
            f"Không đọc được cau_hinh_ao_config.json ({e}). Sử dụng mặc định."
        )
        cfg = {
            "so_du_ban_dau": 10000,
            "ngay_bat_dau": "2025-01-01",
            "ngay_ket_thuc": "2025-01-05",
            "phi_giao_dich": 0.0004,
            "do_truot_gia": 0.0001,
        }
    tu = os.environ.get("KAIROS_RUN_TU_NGAY")
    den = os.environ.get("KAIROS_RUN_DEN_NGAY")
    if tu or den:
        cfg = dict(cfg)
        if tu:
            cfg["ngay_bat_dau"] = tu
        if den:
            cfg["ngay_ket_thuc"] = den
    return cfg


                                                                                


def _yaml_scalar(val) -> str:
    """Định dạng 1 giá trị scalar theo phong cách file YAML hiện có."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    return f'"{val}"'                                                          


def luu_cau_hinh_ao(data: dict) -> bool:
    """Ghi đè cau_hinh_ao_config.json bằng dict mới (JSON, giữ Unicode)."""
    path = duong_dan_config("cau_hinh_ao_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def luu_cau_hinh_giao_dich(data: dict) -> bool:
    """Ghi đè cau_hinh_giao_dich.yaml, GIỮ NGUYÊN comment bằng cách thay tại chỗ.

    PyYAML không round-trip được comment nên ta sửa từng dòng `key: value`:
    chỉ thay phần giá trị, giữ lại chú thích `# ...` và các dòng còn lại.
    """
    path = duong_dan_config("cau_hinh_giao_dich.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    con_lai = dict(data)
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        m = re.match(r"^(\s*)([A-Za-z_][\w]*):(.*)$", line.rstrip("\n"))
        if m and not line.lstrip().startswith("#"):
            indent, key, rest = m.groups()
            if key in con_lai:
                val = con_lai.pop(key)
                if isinstance(val, (list, tuple)):
                    out.append(f"{indent}{key}:\n")
                    out.extend(f"{indent}- {_yaml_scalar(x)}\n" for x in val)
                    i += 1                                               
                    while i < n and re.match(r"^\s*-\s", lines[i]):
                        i += 1
                    continue
                hash_idx = rest.find(" #")                                   
                comment = rest[hash_idx:] if hash_idx != -1 else ""
                out.append(f"{indent}{key}: {_yaml_scalar(val)}{comment}\n")
                i += 1
                continue
        out.append(line)
        i += 1

                                                      
    for key, val in con_lai.items():
        if isinstance(val, (list, tuple)):
            out.append(f"{key}:\n")
            out.extend(f"- {_yaml_scalar(x)}\n" for x in val)
        else:
            out.append(f"{key}: {_yaml_scalar(val)}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)
    return True
