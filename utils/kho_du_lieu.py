"""
utils/kho_du_lieu.py – Data Warehouse (DuckDB)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lưu kết quả từ TẤT CẢ các chế độ vận hành vào DuckDB để phân tích SQL.

Chế độ được hỗ trợ:
  backtest_vector   – vectorized_backtest.py   (batch)
  backtest_bar      – backtest_donluong.py     (batch)
  backtest_da_luong – backtest_daluong.py      (batch, collect ở main process)
  demo              – chay_demo.py             (streaming, từng lệnh)

Schema:
  backtest_run – metadata mỗi lần chạy (run_id, mode, thời gian, config)
  lenh         – lịch sử từng lệnh đóng (đầy đủ: session, hold_duration, sl/tp_pct, exit_reason, r_multiple)
  signal_log   – log tất cả tín hiệu kể cả tín hiệu bị lọc (executed=False)

Views:
  v_lenh_day_du       – lenh + session_derived + r_multiple_calc
  v_regime_chien_luoc – cross-tab regime × chiến lược

Queries phân tích:
  thong_ke_theo_gio()        – winrate/PnL theo giờ (0-23)
  thong_ke_theo_thu()        – winrate/PnL theo thứ trong tuần
  thong_ke_theo_regime()     – PnL theo ML regime (0-7)
  thong_ke_theo_chien_luoc() – PnL theo chiến lược
  thong_ke_theo_mode()       – so sánh kết quả giữa các chế độ
  thong_ke_theo_symbol()     – PnL theo cặp tài sản
  thong_ke_tong_quat()       – summary stats + profit factor
  max_drawdown()             – equity curve + underwater
  thong_ke_hold_duration()   – phân phối thời gian giữ lệnh
  thong_ke_theo_session()    – winrate/PnL theo phiên Á/Âu/Mỹ
  phan_tich_exit_reason()    – tỷ lệ SL/TP/signal flip
  phan_tich_r_multiple()     – phân phối R-multiple
  ti_le_tin_hieu_vao_lenh()  – tỷ lệ signal → executed (từ signal_log)
  sharpe_ratio()             – Sharpe + Sortino ratio
  kelly_criterion()          – Kelly f* và half-Kelly
  phan_tich_streak()         – chuỗi thắng/thua liên tiếp
  monte_carlo()              – bootstrap equity curve, VaR 5%, tỷ lệ cháy TK
  regime_transition()        – ma trận xác suất chuyển đổi regime
  lich_su_run()              – danh sách tất cả lần chạy
  chay_sql()                 – ad-hoc SQL query
"""

import os
import uuid
import math
from datetime import datetime

import duckdb
import numpy as np
import pandas as pd

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "du_lieu", "kairos_warehouse.duckdb"
)

REGIME_NAME = {
    0: "Đóng_Băng",
    1: "Nén_Chặt",
    2: "Đầu_Xu_Hướng",
    3: "Xu_Hướng_Mạnh",
    4: "Cao_Trào",
    5: "Hồi_Quy",
    6: "Nhiễu_Động",
    7: "Quét_Thanh_Khoản",
}


def _ket_noi() -> duckdb.DuckDBPyConnection:
    """Mở kết nối DuckDB tới file warehouse, tạo thư mục nếu chưa có."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def _tao_schema(con: duckdb.DuckDBPyConnection):
    """Tạo các bảng và view cần thiết nếu chưa tồn tại, áp dụng migration cột mới."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS backtest_run (
            run_id      VARCHAR PRIMARY KEY,
            chuc_nang   VARCHAR,
            ngay_chay   TIMESTAMP,
            tu_ngay     VARCHAR,
            den_ngay    VARCHAR,
            symbols     VARCHAR,
            von_ban_dau DOUBLE,
            phi_gd      DOUBLE,
            slippage    DOUBLE,
            don_bay     INTEGER,
            ten_chien_luoc VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS lenh (
            run_id         VARCHAR,
            chuc_nang      VARCHAR,
            symbol         VARCHAR,
            loai           VARCHAR,
            chien_luoc     VARCHAR,
            regime         INTEGER,
            regime_name    VARCHAR,
            gia_vao        DOUBLE,
            gia_dong       DOUBLE,
            leverage       INTEGER,
            pnl            DOUBLE,
            thang          BOOLEAN,
            thoi_gian      TIMESTAMP,
            so_du          DOUBLE,
            gio            INTEGER,
            thu            INTEGER,
            ngay           DATE,
            hold_duration  DOUBLE,
            session        VARCHAR,
            sl_pct         DOUBLE,
            tp_pct         DOUBLE,
            exit_reason    VARCHAR,
            r_multiple     DOUBLE
        )
    """)
                                                 
    for col, dtype, default in [
        ("hold_duration", "DOUBLE", "0.0"),
        ("session", "VARCHAR", "''"),
        ("sl_pct", "DOUBLE", "0.0"),
        ("tp_pct", "DOUBLE", "0.0"),
        ("exit_reason", "VARCHAR", "''"),
        ("r_multiple", "DOUBLE", "0.0"),
    ]:
        try:
            con.execute(
                f"ALTER TABLE lenh ADD COLUMN IF NOT EXISTS {col} {dtype} DEFAULT {default}"
            )
        except Exception:
            pass

                                                                                
    try:
        con.execute("ALTER TABLE backtest_run ADD COLUMN IF NOT EXISTS ten_chien_luoc VARCHAR DEFAULT ''")
    except Exception:
        pass

    con.execute("""
        CREATE TABLE IF NOT EXISTS signal_log (
            run_id      VARCHAR,
            chuc_nang   VARCHAR,
            thoi_gian   TIMESTAMP,
            symbol      VARCHAR,
            signal      INTEGER,
            regime      INTEGER,
            chien_luoc  VARCHAR,
            ly_do_loc   VARCHAR,
            executed    BOOLEAN
        )
    """)

           
    con.execute("""
        CREATE OR REPLACE VIEW v_lenh_day_du AS
        SELECT *,
            CASE
                WHEN gio BETWEEN 1  AND 8  THEN 'ASIA'
                WHEN gio BETWEEN 8  AND 12 THEN 'LONDON'
                WHEN gio BETWEEN 13 AND 17 THEN 'OVERLAP'
                WHEN gio BETWEEN 17 AND 22 THEN 'NEW_YORK'
                ELSE 'OFF'
            END AS session_derived,
            pnl / NULLIF(ABS(gia_vao * NULLIF(sl_pct, 0)), 0) AS r_multiple_calc
        FROM lenh
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_regime_chien_luoc AS
        SELECT regime_name, chien_luoc,
               COUNT(*)                        AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)   AS winrate_pct,
               ROUND(SUM(pnl), 2)              AS tong_pnl,
               ROUND(AVG(pnl), 2)              AS tb_pnl
        FROM lenh
        GROUP BY regime_name, chien_luoc
        ORDER BY tong_pnl DESC
    """)


def tao_run_id() -> str:
    """Tạo run_id duy nhất từ timestamp + UUID ngắn."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]


                                                                               


def _chuan_hoa_lenh_vector(row: dict) -> dict:
    """Normalize một lệnh từ vectorized_backtest."""
    loai = str(row.get("Loại", "")).upper()
    return {
        "symbol": row.get("Symbol", ""),
        "loai": "LONG" if loai in ("BUY", "LONG") else "SHORT",
        "chien_luoc": row.get("Strategy", ""),
        "regime": int(row.get("Regime", -1)),
        "gia_vao": float(row.get("Giá vào", 0)),
        "gia_dong": float(row.get("Giá đóng", 0)),
        "leverage": int(row.get("Leverage", 1)),
        "pnl": float(row.get("PnL", 0)),
        "thoi_gian": pd.to_datetime(row.get("Time")),
        "so_du": float(row.get("Balance", 0)),
        "entry_time": pd.to_datetime(row.get("Entry_Time", row.get("Time"))),
        "sl_pct": float(row.get("SL_pct", row.get("sl_pct", 0.0))),
        "tp_pct": float(row.get("TP_pct", row.get("tp_pct", 0.0))),
        "exit_reason": str(row.get("Exit_Reason", row.get("exit_reason", ""))),
    }


def _chuan_hoa_lenh_bar(row: dict) -> dict:
    """Normalize một lệnh từ backtest_donluong / backtest_daluong."""
    side = str(row.get("side", "")).lower()
    packet = row.get("packet") or {}
    return {
        "symbol": row.get("symbol", ""),
        "loai": "LONG" if side == "buy" else "SHORT",
        "chien_luoc": row.get("strategy", row.get("chien_luoc", "")),
        "regime": int(packet.get("state_id", row.get("regime", -1))),
        "gia_vao": float(row.get("entry", 0)),
        "gia_dong": float(row.get("exit", 0)),
        "leverage": int(row.get("leverage", 1)),
        "pnl": float(row.get("pnl_usd", row.get("pnl", 0))),
        "thoi_gian": pd.to_datetime(row.get("time_close", row.get("close_time"))),
        "so_du": float(row.get("balance", row.get("so_du", 0))),
        "entry_time": pd.to_datetime(
            row.get("time_open", row.get("open_time", row.get("time_close")))
        ),
        "sl_pct": float(row.get("sl_pct", row.get("stop_loss_pct", 0.0))),
        "tp_pct": float(row.get("tp_pct", row.get("take_profit_pct", 0.0))),
        "exit_reason": str(row.get("exit_reason", row.get("ly_do_dong", ""))),
    }


def _chuan_hoa_lenh_demo(row: dict) -> dict:
    """Normalize một lệnh từ chay_demo."""
    side = str(row.get("side", "")).lower()
    packet = row.get("packet_ml") or {}
    time_str = row.get("close_time", "")
    day_str = row.get("day", datetime.now().strftime("%Y-%m-%d"))
    try:
        thoi_gian = pd.to_datetime(f"{day_str} {time_str}")
    except Exception:
        thoi_gian = pd.Timestamp.now()
    return {
        "symbol": row.get("symbol", ""),
        "loai": "LONG" if side == "buy" else "SHORT",
        "chien_luoc": row.get("strategy", ""),
        "regime": int(packet.get("state_id", -1)),
        "gia_vao": float(row.get("entry_price", 0)),
        "gia_dong": float(row.get("exit_price", 0)),
        "leverage": int(row.get("leverage", 1)),
        "pnl": float(row.get("pnl", 0)),
        "thoi_gian": thoi_gian,
        "so_du": float(row.get("so_du", 0)),
    }


_NORMALIZER = {
    "backtest_vector": _chuan_hoa_lenh_vector,
    "backtest_bar": _chuan_hoa_lenh_bar,
    "backtest_da_luong": _chuan_hoa_lenh_bar,
    "demo": _chuan_hoa_lenh_demo,
    "realtime": _chuan_hoa_lenh_demo,                             
}


def _session_tu_gio(gio: int) -> str:
    """Xác định phiên giao dịch (ASIA/LONDON/OVERLAP/NEW_YORK/OFF) từ giờ UTC."""
    if 1 <= gio <= 8:
        return "ASIA"
    if 8 <= gio <= 12:
        return "LONDON"
    if 13 <= gio <= 17:
        return "OVERLAP"
    if 17 <= gio <= 22:
        return "NEW_YORK"
    return "OFF"


def _build_row(chuc_nang: str, run_id: str, norm: dict) -> dict:
    """Thêm các cột derived vào normalized dict."""
    regime = norm.get("regime", -1)
    ts_close = pd.to_datetime(norm.get("thoi_gian", pd.Timestamp.now()))
    ts_open = pd.to_datetime(norm.get("entry_time", ts_close))
    hold_min = (ts_close - ts_open).total_seconds() / 60 if ts_close != ts_open else 0.0

    gia_vao = norm.get("gia_vao", 0.0)
    sl_pct = norm.get("sl_pct", 0.0)
    pnl = norm.get("pnl", 0.0)
    r_multiple = pnl / abs(gia_vao * sl_pct) if gia_vao and sl_pct else 0.0

    return {
        "run_id": run_id,
        "chuc_nang": chuc_nang,
        "symbol": norm["symbol"],
        "loai": norm["loai"],
        "chien_luoc": norm.get("chien_luoc", ""),
        "regime": regime,
        "regime_name": REGIME_NAME.get(regime, "unknown"),
        "gia_vao": gia_vao,
        "gia_dong": norm.get("gia_dong", 0.0),
        "leverage": norm.get("leverage", 1),
        "pnl": pnl,
        "thang": pnl > 0,
        "thoi_gian": ts_close,
        "so_du": norm.get("so_du", 0.0),
        "gio": int(ts_close.hour),
        "thu": int(ts_close.dayofweek),
        "ngay": ts_close.date(),
        "hold_duration": round(hold_min, 2),
        "session": norm.get("session", _session_tu_gio(int(ts_close.hour))),
        "sl_pct": sl_pct,
        "tp_pct": norm.get("tp_pct", 0.0),
        "exit_reason": norm.get("exit_reason", ""),
        "r_multiple": round(r_multiple, 4),
    }


                                                                               


def luu_run(run_id: str, chuc_nang: str, config: dict):
    """Tạo một bản ghi run mới trong bảng backtest_run."""
    con = _ket_noi()
    _tao_schema(con)
    con.execute(
        """
        INSERT OR REPLACE INTO backtest_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            run_id,
            chuc_nang,
            datetime.now(),
            config.get("tu_ngay", ""),
            config.get("den_ngay", ""),
            ", ".join(config.get("symbols", [])),
            config.get("von_ban_dau", 0),
            config.get("phi_gd", 0),
            config.get("slippage", 0),
            config.get("don_bay", 1),
            config.get("ten_chien_luoc", ""),
        ],
    )
    con.close()


def luu_lenh_don(run_id: str, chuc_nang: str, lenh_raw: dict):
    """
    Lưu một lệnh đơn lẻ — dùng cho chế độ streaming (demo, realtime).
    lenh_raw: dict lệnh theo format của từng chế độ (tự động normalize).
    """
    normalizer = _NORMALIZER.get(chuc_nang, _chuan_hoa_lenh_bar)
    norm = normalizer(lenh_raw)
    row = _build_row(chuc_nang, run_id, norm)
    df = pd.DataFrame([row])
    con = _ket_noi()
    _tao_schema(con)
    con.register("df_tmp", df)
    con.execute("INSERT INTO lenh SELECT * FROM df_tmp")
    con.close()


def luu_ket_qua_backtest(
    ds_lenh: list,
    run_id: str,
    chuc_nang: str,
    config: dict,
):
    """
    Lưu toàn bộ lịch sử lệnh — dùng cho chế độ batch (backtest).
    ds_lenh: list[dict] các lệnh đã đóng theo format của từng chế độ.
    chuc_nang: 'backtest_vector' | 'backtest_bar' | 'backtest_da_luong'
    """
    if not ds_lenh:
        return

    luu_run(run_id, chuc_nang, config)

    normalizer = _NORMALIZER.get(chuc_nang, _chuan_hoa_lenh_bar)
    rows = [_build_row(chuc_nang, run_id, normalizer(r)) for r in ds_lenh]
    df = pd.DataFrame(rows)

    con = _ket_noi()
    _tao_schema(con)
    con.register("df_tmp", df)
    con.execute("INSERT INTO lenh SELECT * FROM df_tmp")
    con.close()


                                                                               


def _where(run_id=None, chuc_nang=None) -> str:
    """Tạo mệnh đề WHERE SQL từ các tham số lọc tùy chọn."""
    parts = []
    if run_id:
        parts.append(f"run_id = '{run_id}'")
    if chuc_nang:
        parts.append(f"chuc_nang = '{chuc_nang}'")
    return ("WHERE " + " AND ".join(parts)) if parts else ""


def thong_ke_theo_gio(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Winrate và PnL theo giờ trong ngày (0-23)."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT gio,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY gio ORDER BY gio
    """).df()
    con.close()
    return df


def thong_ke_theo_thu(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Winrate và PnL theo thứ trong tuần (0=Thứ Hai … 6=Chủ Nhật)."""
    thu_map = {
        0: "Thứ 2",
        1: "Thứ 3",
        2: "Thứ 4",
        3: "Thứ 5",
        4: "Thứ 6",
        5: "Thứ 7",
        6: "CN",
    }
    con = _ket_noi()
    df = con.execute(f"""
        SELECT thu,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY thu ORDER BY thu
    """).df()
    con.close()
    df["thu_ten"] = df["thu"].map(thu_map)
    return df


def thong_ke_theo_regime(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """PnL và winrate theo ML regime — regime nào hiệu quả nhất."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT regime, regime_name,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl,
               ROUND(MIN(pnl), 2)                AS pnl_xau_nhat,
               ROUND(MAX(pnl), 2)                AS pnl_tot_nhat
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY regime, regime_name
        ORDER BY tong_pnl DESC
    """).df()
    con.close()
    return df


def thong_ke_theo_chien_luoc(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """PnL và winrate theo chiến lược."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT chien_luoc,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY chien_luoc ORDER BY tong_pnl DESC
    """).df()
    con.close()
    return df


def thong_ke_theo_mode(run_id=None) -> pd.DataFrame:
    """So sánh kết quả giữa các chế độ (backtest_bar vs backtest_vector vs demo)."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT chuc_nang,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl
        FROM lenh {_where(run_id)}
        GROUP BY chuc_nang ORDER BY tong_pnl DESC
    """).df()
    con.close()
    return df


def thong_ke_theo_symbol(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """PnL và winrate theo từng cặp tài sản."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT symbol,
               COUNT(*)                          AS so_lenh,
               ROUND(AVG(thang::INT)*100, 1)     AS winrate_pct,
               ROUND(SUM(pnl), 2)                AS tong_pnl,
               ROUND(AVG(pnl), 2)                AS tb_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY symbol ORDER BY tong_pnl DESC
    """).df()
    con.close()
    return df


def thong_ke_tong_quat(run_id: str) -> pd.DataFrame:
    """Summary stats đầy đủ cho một lần chạy backtest."""
    con = _ket_noi()
    df = con.execute(f"""
        WITH stats AS (
            SELECT COUNT(*)                               AS tong_lenh,
                   SUM(thang::INT)                        AS so_thang,
                   COUNT(*) - SUM(thang::INT)             AS so_thua,
                   ROUND(AVG(thang::INT)*100, 1)          AS winrate_pct,
                   ROUND(SUM(pnl), 2)                     AS tong_pnl,
                   ROUND(AVG(pnl), 2)                     AS tb_pnl_lenh,
                   ROUND(MAX(so_du), 2)                   AS dinh_von,
                   ROUND(MIN(so_du), 2)                   AS day_von,
                   MIN(thoi_gian)                         AS tu_ngay,
                   MAX(thoi_gian)                         AS den_ngay
            FROM lenh WHERE run_id = '{run_id}'
        ),
        pf AS (
            SELECT ROUND(
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0), 2
            ) AS profit_factor
            FROM lenh WHERE run_id = '{run_id}'
        )
        SELECT s.*, p.profit_factor FROM stats s, pf p
    """).df()
    con.close()
    return df


def max_drawdown(run_id: str) -> pd.DataFrame:
    """Tính max drawdown theo equity curve."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT thoi_gian, so_du,
               MAX(so_du) OVER (ORDER BY thoi_gian ROWS UNBOUNDED PRECEDING) AS peak,
               so_du - MAX(so_du) OVER (ORDER BY thoi_gian ROWS UNBOUNDED PRECEDING) AS drawdown
        FROM lenh WHERE run_id = '{run_id}'
        ORDER BY thoi_gian
    """).df()
    con.close()
    return df


def lich_su_run() -> pd.DataFrame:
    """Danh sách tất cả các lần chạy đã lưu, kèm summary."""
    con = _ket_noi()
    _tao_schema(con)
    df = con.execute("""
        SELECT r.run_id, r.chuc_nang, r.ngay_chay,
               r.tu_ngay, r.den_ngay, r.symbols, r.von_ban_dau,
               COUNT(l.run_id)                   AS so_lenh,
               ROUND(SUM(l.pnl), 2)              AS tong_pnl,
               ROUND(AVG(l.thang::INT)*100, 1)   AS winrate_pct
        FROM backtest_run r
        LEFT JOIN lenh l ON r.run_id = l.run_id
        GROUP BY r.run_id, r.chuc_nang, r.ngay_chay,
                 r.tu_ngay, r.den_ngay, r.symbols, r.von_ban_dau
        ORDER BY r.ngay_chay DESC
    """).df()
    con.close()
    return df


def chay_sql(query: str) -> pd.DataFrame:
    """Chạy câu SQL tùy ý. Dùng để khám phá dữ liệu ad-hoc."""
    con = _ket_noi()
    _tao_schema(con)
    df = con.execute(query).df()
    con.close()
    return df


def luu_signal(run_id: str, chuc_nang: str, signal_raw: dict):
    """
    Ghi một tín hiệu vào signal_log — kể cả tín hiệu bị lọc (không vào lệnh).
    signal_raw cần có: symbol, signal (-1/0/1), regime, chien_luoc, ly_do_loc, executed (bool), thoi_gian.
    """
    row = {
        "run_id": run_id,
        "chuc_nang": chuc_nang,
        "thoi_gian": pd.to_datetime(signal_raw.get("thoi_gian", pd.Timestamp.now())),
        "symbol": signal_raw.get("symbol", ""),
        "signal": int(signal_raw.get("signal", 0)),
        "regime": int(signal_raw.get("regime", -1)),
        "chien_luoc": signal_raw.get("chien_luoc", ""),
        "ly_do_loc": signal_raw.get("ly_do_loc", ""),
        "executed": bool(signal_raw.get("executed", False)),
    }
    df = pd.DataFrame([row])
    con = _ket_noi()
    _tao_schema(con)
    con.register("df_tmp", df)
    con.execute("INSERT INTO signal_log SELECT * FROM df_tmp")
    con.close()


                                                                               


def thong_ke_hold_duration(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Phân phối thời gian giữ lệnh (phút) — phát hiện cắt lời sớm hoặc gồng lỗ."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            CASE
                WHEN hold_duration < 5   THEN '< 5m'
                WHEN hold_duration < 15  THEN '5-15m'
                WHEN hold_duration < 60  THEN '15-60m'
                WHEN hold_duration < 240 THEN '1-4h'
                WHEN hold_duration < 1440 THEN '4-24h'
                ELSE '> 1 ngày'
            END AS khung_giu,
            COUNT(*)                        AS so_lenh,
            ROUND(AVG(thang::INT)*100, 1)   AS winrate_pct,
            ROUND(AVG(pnl), 2)              AS tb_pnl,
            ROUND(SUM(pnl), 2)              AS tong_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY khung_giu
        ORDER BY MIN(hold_duration)
    """).df()
    con.close()
    return df


def thong_ke_theo_session(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Winrate và PnL theo phiên giao dịch (Asia / London / Overlap / New York)."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            COALESCE(NULLIF(session, ''),
                CASE
                    WHEN gio BETWEEN 1  AND 8  THEN 'ASIA'
                    WHEN gio BETWEEN 8  AND 12 THEN 'LONDON'
                    WHEN gio BETWEEN 13 AND 17 THEN 'OVERLAP'
                    WHEN gio BETWEEN 17 AND 22 THEN 'NEW_YORK'
                    ELSE 'OFF'
                END
            ) AS phien,
            COUNT(*)                        AS so_lenh,
            ROUND(AVG(thang::INT)*100, 1)   AS winrate_pct,
            ROUND(SUM(pnl), 2)              AS tong_pnl,
            ROUND(AVG(pnl), 2)              AS tb_pnl,
            ROUND(AVG(hold_duration), 1)    AS tb_hold_phut
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY phien
        ORDER BY tong_pnl DESC
    """).df()
    con.close()
    return df


def phan_tich_exit_reason(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Tỷ lệ đóng lệnh theo lý do: SL_HIT / TP_HIT / SIGNAL_FLIP / ..."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            CASE WHEN exit_reason = '' THEN 'UNKNOWN' ELSE exit_reason END AS ly_do,
            COUNT(*)                        AS so_lenh,
            ROUND(AVG(thang::INT)*100, 1)   AS winrate_pct,
            ROUND(AVG(pnl), 2)              AS tb_pnl,
            ROUND(SUM(pnl), 2)              AS tong_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        GROUP BY ly_do
        ORDER BY so_lenh DESC
    """).df()
    con.close()
    return df


def phan_tich_r_multiple(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Phân phối R-multiple (PnL / risk). 1R = đạt đúng TP, <0 = lỗ."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            CASE
                WHEN r_multiple >=  2   THEN '>= 2R'
                WHEN r_multiple >=  1   THEN '1-2R'
                WHEN r_multiple >=  0   THEN '0-1R'
                WHEN r_multiple >= -1   THEN '-1-0R'
                ELSE '< -1R'
            END AS nhom_r,
            COUNT(*)                       AS so_lenh,
            ROUND(AVG(pnl), 2)             AS tb_pnl,
            ROUND(SUM(pnl), 2)             AS tong_pnl
        FROM lenh {_where(run_id, chuc_nang)}
        WHERE r_multiple != 0
        GROUP BY nhom_r
        ORDER BY MIN(r_multiple) DESC
    """).df()
    con.close()
    return df


def ti_le_tin_hieu_vao_lenh(run_id=None, chuc_nang=None) -> pd.DataFrame:
    """Từ signal_log: bao nhiêu % tín hiệu được chuyển thành lệnh thực."""
    w = _where(run_id, chuc_nang)
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            chien_luoc,
            COUNT(*)                                              AS tong_tin_hieu,
            SUM(executed::INT)                                    AS da_vao_lenh,
            ROUND(SUM(executed::INT)*100.0/COUNT(*), 1)          AS ti_le_vao_pct,
            ly_do_loc,
            COUNT(*) FILTER (WHERE NOT executed)                  AS bi_loc
        FROM signal_log {w}
        GROUP BY chien_luoc, ly_do_loc
        ORDER BY tong_tin_hieu DESC
    """).df()
    con.close()
    return df


def sharpe_ratio(run_id: str, risk_free_rate: float = 0.0) -> dict:
    """
    Tính Sharpe Ratio và Sortino Ratio từ chuỗi PnL theo ngày.
    risk_free_rate: lãi suất phi rủi ro hàng năm (mặc định 0).
    """
    con = _ket_noi()
    run_info = con.execute(f"""
        SELECT von_ban_dau, tu_ngay, den_ngay FROM backtest_run WHERE run_id = '{run_id}'
    """).df()
    
    if run_info.empty:
                                 
        von_ban_dau = 10000.0
        dates_df = con.execute(f"SELECT MIN(ngay) as min_d, MAX(ngay) as max_d FROM lenh WHERE run_id = '{run_id}'").df()
        if dates_df.empty or dates_df.iloc[0]["min_d"] is None:
            con.close()
            return {"sharpe": 0.0, "sortino": 0.0, "n_days": 0}
        start_date = dates_df.iloc[0]["min_d"]
        end_date = dates_df.iloc[0]["max_d"]
    else:
        von_ban_dau = float(run_info.iloc[0]["von_ban_dau"] or 10000.0)
        tu_ngay = run_info.iloc[0]["tu_ngay"]
        den_ngay = run_info.iloc[0]["den_ngay"]
        
        try:
            import datetime
            if isinstance(tu_ngay, str):
                start_date = datetime.datetime.strptime(tu_ngay[:10], "%Y-%m-%d").date()
            else:
                start_date = tu_ngay
            if isinstance(den_ngay, str):
                end_date = datetime.datetime.strptime(den_ngay[:10], "%Y-%m-%d").date()
            else:
                end_date = den_ngay
        except Exception:
            dates_df = con.execute(f"SELECT MIN(ngay) as min_d, MAX(ngay) as max_d FROM lenh WHERE run_id = '{run_id}'").df()
            if dates_df.empty or dates_df.iloc[0]["min_d"] is None:
                con.close()
                return {"sharpe": 0.0, "sortino": 0.0, "n_days": 0}
            start_date = dates_df.iloc[0]["min_d"]
            end_date = dates_df.iloc[0]["max_d"]

                                      
    import datetime
    if isinstance(start_date, str):
        start_date = datetime.datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    elif hasattr(start_date, "date"):
        start_date = start_date.date()
        
    if isinstance(end_date, str):
        end_date = datetime.datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    elif hasattr(end_date, "date"):
        end_date = end_date.date()

    df_pnl = con.execute(f"""
        SELECT ngay, SUM(pnl) AS daily_pnl
        FROM lenh WHERE run_id = '{run_id}'
        GROUP BY ngay ORDER BY ngay
    """).df()
    con.close()

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    delta = end_date - start_date
    all_dates = [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]
    
    pnl_dict = {}
    for r in df_pnl.itertuples():
        d_val = r.ngay
        if isinstance(d_val, str):
            d_val = datetime.datetime.strptime(d_val[:10], "%Y-%m-%d").date()
        elif hasattr(d_val, "date"):
            d_val = d_val.date()
        pnl_dict[d_val] = float(r.daily_pnl)

    daily_returns = []
    curr_balance = von_ban_dau
    for d in all_dates:
        daily_pnl = pnl_dict.get(d, 0.0)
        daily_ret = daily_pnl / curr_balance if curr_balance > 0 else 0.0
        daily_returns.append(daily_ret)
        curr_balance += daily_pnl

    returns = np.array(daily_returns)
    n_days = len(returns)
    if n_days < 2:
        return {"sharpe": 0.0, "sortino": 0.0, "n_days": n_days}

    mean_r = returns.mean()
    std_r = returns.std(ddof=1)
    downside = returns[returns < 0]
    down_std = downside.std(ddof=1) if len(downside) > 1 else 1e-9

    trading_days = 365
    daily_rf = risk_free_rate / trading_days

    sharpe = (mean_r - daily_rf) / std_r * math.sqrt(trading_days) if std_r > 0 else 0.0
    sortino = (
        (mean_r - daily_rf) / down_std * math.sqrt(trading_days)
        if down_std > 0
        else 0.0
    )

    return {
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "n_days": n_days,
        "daily_mean_return": round(mean_r, 6),
        "daily_std_return": round(std_r, 6),
    }


def kelly_criterion(run_id: str) -> dict:
    """
    Tính Kelly Criterion: f* = w - (1-w)/R
    R = avg_win / avg_loss (win/loss ratio không đơn vị).
    Trả về full kelly và half kelly (an toàn hơn).
    """
    con = _ket_noi()
    df = con.execute(f"""
        SELECT
            AVG(thang::INT)                                          AS win_rate,
            AVG(pnl) FILTER (WHERE pnl > 0)                         AS avg_win,
            ABS(AVG(pnl) FILTER (WHERE pnl < 0))                    AS avg_loss
        FROM lenh WHERE run_id = '{run_id}'
    """).df()
    con.close()

    if df.empty:
        return {"kelly": 0.0, "half_kelly": 0.0}

    row = df.iloc[0]
    w = row["win_rate"] or 0.0
    avg_win = row["avg_win"] or 0.0
    avg_loss = row["avg_loss"] or 0.0

    if avg_loss > 0 and avg_win > 0:
        R = avg_win / avg_loss
        kelly = w - (1.0 - w) / R
    else:
        kelly = 0.0
        
    kelly = max(0.0, min(kelly, 1.0))

    return {
        "kelly": round(kelly, 4),
        "half_kelly": round(kelly / 2, 4),
        "win_rate": round(w, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
    }


def phan_tich_streak(run_id: str) -> dict:
    """Phân tích chuỗi thắng/thua liên tiếp tối đa và trung bình."""
    con = _ket_noi()
    df = con.execute(f"""
        SELECT thang FROM lenh
        WHERE run_id = '{run_id}'
        ORDER BY thoi_gian
    """).df()
    con.close()

    if df.empty:
        return {}

    results = df["thang"].tolist()
    max_win = max_loss = cur_win = cur_loss = 0
    win_streaks = []
    loss_streaks = []

    for r in results:
        if r:
            cur_win += 1
            if cur_loss > 0:
                loss_streaks.append(cur_loss)
            cur_loss = 0
        else:
            cur_loss += 1
            if cur_win > 0:
                win_streaks.append(cur_win)
            cur_win = 0
        max_win = max(max_win, cur_win)
        max_loss = max(max_loss, cur_loss)

    if cur_win > 0:
        win_streaks.append(cur_win)
    if cur_loss > 0:
        loss_streaks.append(cur_loss)

    return {
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
        "avg_win_streak": (
            round(sum(win_streaks) / len(win_streaks), 2) if win_streaks else 0
        ),
        "avg_loss_streak": (
            round(sum(loss_streaks) / len(loss_streaks), 2) if loss_streaks else 0
        ),
        "n_win_streaks": len(win_streaks),
        "n_loss_streaks": len(loss_streaks),
    }


def monte_carlo(run_id: str, n_sim: int = 1000, von_ban_dau: float = None) -> dict:
    """
    Bootstrap Monte Carlo trên chuỗi PnL để ước tính phân phối kết quả.
    Trả về VaR 5%, median, và tỷ lệ cháy tài khoản.
    """
    con = _ket_noi()
    df_pnl = con.execute(f"""
        SELECT pnl FROM lenh WHERE run_id = '{run_id}' ORDER BY thoi_gian
    """).df()

    if von_ban_dau is None:
        row = con.execute(f"""
            SELECT von_ban_dau FROM backtest_run WHERE run_id = '{run_id}'
        """).df()
        von_ban_dau = float(row.iloc[0]["von_ban_dau"]) if not row.empty else 10000.0
    con.close()

    if df_pnl.empty:
        return {}

    pnl_arr = df_pnl["pnl"].values
    n = len(pnl_arr)
    rng = np.random.default_rng(42)

    final_balances = []
    n_chay_tai_khoan = 0

    for _ in range(n_sim):
        shuffled = rng.choice(pnl_arr, size=n, replace=True)
        equity = von_ban_dau + np.cumsum(shuffled)
        final_balances.append(equity[-1])
        if np.any(equity <= von_ban_dau * 0.2):
            n_chay_tai_khoan += 1

    fb = np.array(final_balances)
    return {
        "von_ban_dau": round(von_ban_dau, 2),
        "median_final": round(float(np.median(fb)), 2),
        "p5_final": round(float(np.percentile(fb, 5)), 2),
        "p95_final": round(float(np.percentile(fb, 95)), 2),
        "var_5pct": round(float(von_ban_dau - np.percentile(fb, 5)), 2),
        "ti_le_chay_tk_pct": round(n_chay_tai_khoan / n_sim * 100, 1),
        "n_sim": n_sim,
    }


def regime_transition(run_id: str) -> pd.DataFrame:
    """
    Ma trận chuyển đổi regime: xác suất từ regime A sang regime B ở lệnh tiếp theo.
    Hữu ích để phân tích tính liên tục của trạng thái thị trường.
    """
    con = _ket_noi()
    df = con.execute(f"""
        SELECT regime, regime_name,
               LEAD(regime)      OVER (ORDER BY thoi_gian) AS next_regime,
               LEAD(regime_name) OVER (ORDER BY thoi_gian) AS next_regime_name
        FROM lenh WHERE run_id = '{run_id}'
        ORDER BY thoi_gian
    """).df()
    con.close()

    df = df.dropna(subset=["next_regime"])
    if df.empty:
        return pd.DataFrame()

    matrix = (
        df.groupby(["regime_name", "next_regime_name"]).size().unstack(fill_value=0)
    )
    matrix = matrix.div(matrix.sum(axis=1), axis=0).round(3)
    return matrix
