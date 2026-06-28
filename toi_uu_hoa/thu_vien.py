"""
toi_uu_hoa_low/thu_vien.py – Thư viện lưu các bộ tham số chiến lược ĐÃ NGHIÊN CỨU.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mỗi chiến lược lưu 1 file JSON trong du_lieu/danh_sach_chien_luoc/.
Là nền tảng để Analytics (M4) vẽ biểu đồ cho TỪNG bộ tham số đã lưu.
"""

import os
import re
import json
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
THU_MUC = os.path.join(PROJECT_ROOT, "du_lieu", "danh_sach_chien_luoc")


def _slug(s):
    """Chuẩn hóa thành tên file an toàn."""
    s = re.sub(r"[^0-9A-Za-z._@+-]+", "_", str(s)).strip("_")
    return s or "chien_luoc"


def _safe_float(v, d=0.0):
    try:
        f = float(v)
        return d if f != f else f
    except (TypeError, ValueError):
        return d


def parse_filename_metadata(ten):
    """
    Giải mã metadata từ tên file đã lưu trong thư viện.
    Format: name_part__vd_VERDICT__sh_SHARPE__rt_RATIO__TIMESTAMP
    """
    parts = ten.split("__")
    verdict = "UNKNOWN"
    sharpe = 0.0
    ratio = 0.0
    timestamp = ""
    name_parts = []

    for p in parts:
        if p.startswith("vd_"):
            verdict = p[3:]
        elif p.startswith("sh_"):
            try:
                sharpe = float(p[3:])
            except ValueError:
                sharpe = 0.0
        elif p.startswith("rt_"):
            try:
                ratio = float(p[3:])
            except ValueError:
                ratio = 0.0

        elif len(p) == 15 and p[8] == "_" and p.replace("_", "").isdigit():
            timestamp = p
        else:
            name_parts.append(p)


    name = "__".join(name_parts)


    ngay_luu = ""
    if timestamp:
        try:
            ngay_luu = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
        except Exception:
            ngay_luu = ""

    return {
        "name": name,
        "verdict": verdict,
        "oos_sharpe": sharpe,
        "oos_is_ratio": ratio,
        "ngay_luu": ngay_luu
    }


def luu_chien_luoc(result, ten=None):
    """
    Lưu 1 `result` (output của run_combo_optimization) vào thư viện.
    Trả về tên đã lưu (slug).
    """
    os.makedirs(THU_MUC, exist_ok=True)


    try:
        from toi_uu_hoa_low.kiem_dinh import danh_gia_guardrails
        verdict = danh_gia_guardrails(result)["verdict"]
    except Exception:
        verdict = "REJECT"

    oos = result.get("oos_metrics", {}) or {}
    sharpe = _safe_float(oos.get("sharpe_ratio"))
    ratio = _safe_float(result.get("oos_is_ratio"))


    if ten:

        parts = ten.split("__")
        cleaned_parts = []
        for p in parts:
            if p.startswith("vd_") or p.startswith("sh_") or p.startswith("rt_"):
                continue
            if len(p) == 15 and p[8] == "_" and p.replace("_", "").isdigit():
                continue
            cleaned_parts.append(p)
        base_name = "__".join(cleaned_parts)
        base_name = _slug(base_name)
    else:

        if not result.get("combo"):
            name_base = _slug(result.get("strategy_key", "plugin"))
            base_name = f"plugin__{name_base}"
        else:
            label_base = _slug(result.get("combo_label", "combo").replace('@', '_').replace('+', '_'))
            logic_val = result.get("logic")
            if isinstance(logic_val, dict):
                logic = logic_val.get("mode", "and")
                persistence = logic_val.get("persistence", 1)
            else:
                logic = logic_val or "and"
                persistence = result.get("persistence", 1)
            base_name = f"{label_base}__{logic}_p{persistence}"


    ts = time.strftime('%Y%m%d_%H%M%S')
    filename = f"{base_name}__vd_{verdict}__sh_{sharpe:.3f}__rt_{ratio:.2f}__{ts}"
    filename = _slug(filename)


    clean_config = result.get("best_params", result)

    filepath = os.path.join(THU_MUC, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(clean_config, f, indent=2, ensure_ascii=False)


    if verdict == "DEPLOY":
        ds_dir = os.path.join(PROJECT_ROOT, "du_lieu", "danh_sach_chien_luoc")
        os.makedirs(ds_dir, exist_ok=True)


        if not result.get("combo"):
            strategy_name = _slug(result.get("strategy_key", "plugin")).lower()
        else:
            strategy_name = _slug(result.get("combo_label", "combo").replace('@', '_').replace('+', '_')).lower()

        ds_filepath = os.path.join(ds_dir, f"{strategy_name}.json")
        with open(ds_filepath, "w", encoding="utf-8") as f:
            json.dump(clean_config, f, indent=2, ensure_ascii=False)

    return filename


def danh_sach_da_luu():
    """Trả list metadata các chiến lược đã lưu (mới nhất trước)."""
    if not os.path.isdir(THU_MUC):
        return []
    ds = []
    for fn in os.listdir(THU_MUC):
        if not fn.endswith(".json"):
            continue
        try:
            ten = fn[:-5]
            meta = parse_filename_metadata(ten)


            with open(os.path.join(THU_MUC, fn), "r", encoding="utf-8") as f:
                config = json.load(f)

            if isinstance(config, dict) and "result" in config and isinstance(config["result"], dict):

                old_result = config["result"]
                config = old_result.get("best_params", old_result)

            combo = []
            for k in sorted([x for x in config if x.startswith("s") and x[1:].isdigit()], key=lambda x: int(x[1:])):
                spec = config[k]
                combo.append({
                    "key": spec.get("key"),
                    "tf": spec.get("tf"),
                })

            if combo:
                combo_label = " + ".join([f"{c['key'].upper()}@{c['tf']}" for c in combo])
            else:

                combo_label = meta["name"].replace("plugin__", "").upper()

            ds.append({
                "ten": ten,
                "combo_label": combo_label,
                "ngay_luu": meta["ngay_luu"],
                "verdict": meta["verdict"],
                "oos_sharpe": meta["oos_sharpe"],
                "oos_is_ratio": meta["oos_is_ratio"],
            })
        except Exception:
            continue

    ds.sort(key=lambda x: x["ngay_luu"], reverse=True)
    return ds


def doc_chien_luoc(ten):
    """Đọc 1 chiến lược đã lưu (trả payload đầy đủ, gồm khóa 'result'). {} nếu không có."""
    p = os.path.join(THU_MUC, f"{_slug(ten)}.json")
    if not os.path.exists(p):
        return {}

    try:
        with open(p, "r", encoding="utf-8") as f:
            config = json.load(f)

        if isinstance(config, dict) and "result" in config and isinstance(config["result"], dict):

            old_result = config["result"]
            config = old_result.get("best_params", old_result)

        meta = parse_filename_metadata(ten)
        verdict = meta["verdict"]
        oos_sharpe = meta["oos_sharpe"]
        oos_is_ratio = meta["oos_is_ratio"]


        combo = []
        for k in sorted([x for x in config if x.startswith("s") and x[1:].isdigit()], key=lambda x: int(x[1:])):
            spec = config[k]
            combo.append({
                "key": spec.get("key"),
                "tf": spec.get("tf"),
                "role": spec.get("role", "trigger"),
                "type": spec.get("type", "oscillator"),
                "params": spec.get("params", {}),
                "thresholds": spec.get("thresholds", {})
            })

        if combo:
            combo_label = " + ".join([f"{c['key'].upper()}@{c['tf']}" for c in combo])
        else:
            combo_label = meta["name"].replace("plugin__", "").upper()

        logic_mode = config.get("logic", {}).get("mode", "and")
        persistence = config.get("logic", {}).get("persistence", 1)


        result = {
            "combo": combo,
            "combo_label": combo_label,
            "best_params": config,
            "logic": {
                "mode": logic_mode,
                "persistence": persistence
            },
            "oos_metrics": {
                "sharpe_ratio": oos_sharpe,
                "sortino_ratio": oos_sharpe * 1.1,
                "deflated_sharpe_ratio": oos_sharpe * 0.9,
                "win_rate": 55.0 if verdict == "DEPLOY" else 45.0,
                "max_drawdown_pct": 5.0 if verdict == "DEPLOY" else 15.0,
                "profit_factor": 1.35 if verdict == "DEPLOY" else 0.95,
                "total_trades": 35 if verdict == "DEPLOY" else 15,
            },
            "is_metrics": {
                "sharpe_ratio": oos_sharpe / oos_is_ratio if oos_is_ratio > 0 else oos_sharpe,
                "deflated_sharpe_ratio": 0.92 if verdict == "DEPLOY" else 0.75,
            },
            "oos_is_ratio": oos_is_ratio,
            "wf_summary": {
                "so_doan_co_du_lieu": 2 if verdict == "DEPLOY" else 0,
                "so_doan": 2,
                "ty_le_doan_duong": 0.8 if verdict == "DEPLOY" else 0.3,
                "sharpe_trung_binh": oos_sharpe,
            },
            "oos_folds": [
                {"ky": "Đoạn 1", "sharpe_ratio": oos_sharpe, "total_trades": 18},
                {"ky": "Đoạn 2", "sharpe_ratio": oos_sharpe, "total_trades": 17},
            ] if verdict == "DEPLOY" else [],
            "canh_bao": ["Nạp từ thư viện (chỉ lưu cấu hình chuẩn, các số liệu backtest là tượng trưng)."]
        }

        payload = {
            "ten": ten,
            "ngay_luu": meta["ngay_luu"],
            "combo_label": combo_label,
            "verdict": verdict,
            "oos_sharpe": oos_sharpe,
            "oos_is_ratio": oos_is_ratio,
            "result": result
        }
        return payload
    except Exception:
        return {}


def xoa_chien_luoc(ten):
    """Xóa 1 chiến lược đã lưu. Trả True nếu xóa được."""
    p = os.path.join(THU_MUC, f"{_slug(ten)}.json")
    if os.path.exists(p):
        os.remove(p)
        return True
    return False
