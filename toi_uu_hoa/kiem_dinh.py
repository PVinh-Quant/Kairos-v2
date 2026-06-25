"""
toi_uu_hoa_low/kiem_dinh.py – Hàng Rào Kiểm Định Tự Động (Auto-Guardrails Audit)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Đánh giá kết quả tối ưu hóa (Walk-Forward IS/OOS) theo bộ tiêu chuẩn định lượng
để quyết định một chiến lược có đủ tin cậy để DEPLOY hay không.

Một chiến lược chỉ được DEPLOY khi vượt qua TẤT CẢ các chốt sau (xem
khao_sat_thiet_ke_toi_uu_hoa.md – Mô-đun 5):
  1. DSR (Deflated Sharpe Ratio) >= 90%  — không phải ăn may do thử nhiều lần.
  2. OOS / IS Ratio >= 0.8               — không suy giảm > 20% so với In-Sample.
  3. OOS Trades >= 30                    — đủ ý nghĩa thống kê.
  4. OOS Profit Factor >= 1.2            — tổng thắng vượt trội tổng thua.
"""

                                                                                
DSR_MIN = 0.90
OOS_IS_MIN = 0.8
MIN_TRADES_OOS = 30
PF_MIN = 1.2
WF_DUONG_MIN = 0.6                                                               

                                                                                   
_NO_DATA_SHARPE = -10.0


def _safe_float(value, default=0.0):
    try:
        f = float(value)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _oos_thieu_lenh(result):
    """OOS không đủ lệnh để đánh giá: <=1 lệnh, hoặc Sharpe = giá trị phạt (≤ -9.99)."""
    oos = (result or {}).get("oos_metrics", {}) or {}
    return _safe_float(oos.get("total_trades")) <= 1 or _safe_float(oos.get("sharpe_ratio")) <= -9.99


def danh_gia_guardrails(result, nguong=None):
    """
    Đánh giá guardrail cho 1 kết quả chiến lược (output của run_combo_optimization).

    Args:
        result: dict có 'oos_metrics' (dsr, sharpe, profit_factor, total_trades) và 'oos_is_ratio'.
        nguong: dict tuỳ chọn override ngưỡng, vd {'dsr': 0.95, 'pf': 1.5}.

    Returns:
        dict:
          - verdict : 'DEPLOY' | 'REJECT' | 'NO_TRADE'
          - checks  : list[{id, ten, gia_tri, nguong, dat, hien_thi}]
          - failed  : list[str] tên các chốt chưa đạt
    """
    nguong = nguong or {}
    dsr_min = nguong.get("dsr", DSR_MIN)
    oos_is_min = nguong.get("oos_is", OOS_IS_MIN)
    min_trades = nguong.get("trades", MIN_TRADES_OOS)
    pf_min = nguong.get("pf", PF_MIN)

    if not result:
        return {"verdict": "REJECT", "checks": [], "failed": ["Không có kết quả"]}

    ism = result.get("is_metrics", {}) or {}
    oos = result.get("oos_metrics", {}) or {}
                                                                               
                                                                                      
    dsr = _safe_float(ism.get("deflated_sharpe_ratio"))
    sharpe = _safe_float(oos.get("sharpe_ratio"))
    pf = _safe_float(oos.get("profit_factor"))
    trades = int(_safe_float(oos.get("total_trades")))
    ratio = _safe_float(result.get("oos_is_ratio"))

    checks = [
        {
            "id": "dsr", "ten": "DSR (IS, khử multiple-testing) ≥ 90%",
            "gia_tri": dsr, "nguong": dsr_min, "dat": dsr >= dsr_min,
            "hien_thi": f"{dsr * 100:.1f}%  (cần ≥ {dsr_min * 100:.0f}%)",
        },
        {
            "id": "oos_is", "ten": "OOS / IS ≥ 0.8",
            "gia_tri": ratio, "nguong": oos_is_min, "dat": ratio >= oos_is_min,
            "hien_thi": f"{ratio:.2f}  (cần ≥ {oos_is_min:.1f})",
        },
        {
            "id": "trades", "ten": f"OOS Trades ≥ {min_trades}",
            "gia_tri": trades, "nguong": min_trades, "dat": trades >= min_trades,
            "hien_thi": f"{trades}  (cần ≥ {min_trades})",
        },
        {
            "id": "pf", "ten": "OOS Profit Factor ≥ 1.2",
            "gia_tri": pf, "nguong": pf_min, "dat": pf >= pf_min,
            "hien_thi": f"{pf:.2f}  (cần ≥ {pf_min:.1f})",
        },
    ]

                                                                                           
    wf = result.get("wf_summary") or {}
    if wf.get("so_doan_co_du_lieu", 0) >= 2:
        wf_min = nguong.get("wf_duong", WF_DUONG_MIN)
        ty_le = _safe_float(wf.get("ty_le_doan_duong"))
        checks.append({
            "id": "wf",
            "ten": f"% đoạn OOS dương ≥ {int(wf_min * 100)}% (walk-forward)",
            "gia_tri": ty_le, "nguong": wf_min, "dat": ty_le >= wf_min,
            "hien_thi": f"{ty_le * 100:.0f}%  ({wf.get('so_doan_co_du_lieu')}/{wf.get('so_doan')} đoạn; cần ≥ {int(wf_min * 100)}%)",
        })

    failed = [c["ten"] for c in checks if not c["dat"]]

                        
    if _oos_thieu_lenh(result):
        verdict = "NO_TRADE"
    elif not failed and sharpe > 0:
        verdict = "DEPLOY"
    else:
        verdict = "REJECT"

    return {"verdict": verdict, "checks": checks, "failed": failed}
