"""
lay_du_lieu/lay_ohlcv.py – Lấy và chuẩn bị dữ liệu OHLCV
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3 chức năng chính:
  1. lay_du_lieu_nen()          – fetch 8 khung thời gian (1m→1d) cho bot realtime/demo
  2. tai_du_lieu_lich_su()      – tải toàn bộ lịch sử 1m từ Binance cho backtest
  3. chuan_bi_du_lieu_da_khung_vectorized() – build 8 khung từ 1m gốc cho vectorized backtest

Dùng Polars thay Pandas để xử lý nhanh hơn ~3-5x trên dataset lớn.
"""

import polars as pl
from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from utils.log import logger
import ccxt
import os
import sys
import time
from datetime import datetime, timedelta

                                                                                          
_CACHE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "du_lieu", "cache_ohlcv"
)


def gop_nen(df, timeframe_dich):
    """Gộp nến 1m thành khung lớn hơn bằng Polars group_by_dynamic (không lookahead)."""
    if df is None or df.is_empty():
        return None

    rule = timeframe_dich.lower().replace("min", "m")

    try:
        df_res = (
            df.group_by_dynamic(
                "timestamp",
                every=rule,
                closed="left",                             
                label="left",                            
                start_by="window",                                                      
            )
            .agg(
                [
                    pl.col("open").first(),
                    pl.col("high").max(),
                    pl.col("low").min(),
                    pl.col("close").last(),
                    pl.col("volume").sum(),
                ]
            )
            .drop_nulls()
        )

                                   
        return df_res if len(df_res) >= 25 else None

    except Exception as e:
        logger.error(f"Lỗi gộp nến {timeframe_dich}: {e}")
        return None


def chuan_bi_du_lieu_da_khung(df_goc, current_time, limit_lookback=43200):
    """
    Cắt DataFrame đến current_time rồi gộp ra 8 khung thời gian (dùng cho backtest bar-to-bar).
    Trả về list [df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d].
    """
    MAX_OUTPUT = 300
    df_den_hien_tai = df_goc.filter(pl.col("timestamp") <= current_time)

    if df_den_hien_tai.is_empty():
        return None
    df_working = df_den_hien_tai.tail(limit_lookback)

    timeframes = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }

    results = []
    for label, interval in timeframes.items():
        if interval == "1m":
            df_res = df_working
        else:
            df_res = gop_nen(df_working, interval)
        results.append(df_res.tail(MAX_OUTPUT))
    return results


def fetch_raw(exchange, symbol, timeframe, limit=1000):
    """Fetch OHLCV thô từ sàn qua CCXT, trả về Polars DataFrame với timestamp đã parse."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                                                          
        schema = {
            "timestamp": pl.Int64,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        }
                                                              
        df = pl.DataFrame(ohlcv, schema=list(schema.keys()), orient="row").with_columns(
            [pl.from_epoch("timestamp", time_unit="ms")]
        )
        return df
    except Exception as e:
        logger.error(f"Lỗi fetch {symbol} {timeframe}: {e}")
        return None


def lay_du_lieu_nen(
    ten_san, symbol
):                                                                                                                                                   
    """Fetch 8 khung thời gian đồng thời cho một symbol từ sàn chỉ định."""
    exchange = quan_ly_san.lay_san(ten_san)
    df_1m = df_3m = df_5m = df_15m = df_30m = df_1h = df_4h = df_1d = None
    if not exchange:
        return df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d

    df_1m = fetch_raw(exchange, symbol, "1m", limit=300)
    if df_1m is not None:
        df_3m = gop_nen(df_1m, "3m")       

    df_5m = fetch_raw(exchange, symbol, "5m", limit=300)
    if df_5m is not None:
        df_15m = gop_nen(df_5m, "15m")       

    df_30m = fetch_raw(exchange, symbol, "30m", limit=300)
    if df_30m is not None:
        df_1h = gop_nen(df_30m, "1h")       

    df_4h = fetch_raw(exchange, symbol, "4h", limit=300)
    if df_4h is not None:
        df_1d = gop_nen(df_4h, "1d")      

    return df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d


def _thu_muc_cache(symbol):
    """Thư mục cache cho một symbol (tự tạo nếu chưa có). Vd: du_lieu/cache_ohlcv/BTC_USDT/."""
    safe = symbol.replace("/", "_").replace(":", "_")
    path = os.path.join(_CACHE_ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path


def _file_cache_ngay(cache_dir, ngay):
    """Đường dẫn file parquet cache cho một ngày cụ thể (YYYY-MM-DD.parquet)."""
    return os.path.join(cache_dir, f"{ngay.strftime('%Y-%m-%d')}.parquet")


def _gom_ngay_lien_tuc(ngays):
    """Gom danh sách ngày thành các đoạn liên tục [(start, end), ...] để tải gộp 1 lần."""
    if not ngays:
        return []
    ngays = sorted(ngays)
    ranges = []
    g_start = g_prev = ngays[0]
    for d in ngays[1:]:
        if (d - g_prev).days == 1:
            g_prev = d
        else:
            ranges.append((g_start, g_prev))
            g_start = g_prev = d
    ranges.append((g_start, g_prev))
    return ranges


def _tai_1m_tu_san(exchange, symbol, since_ms, end_ms):
    """Paginate fetch nến 1m từ sàn trong [since_ms, end_ms]; trả Polars df (timestamp datetime)."""
    all_ohlcv = []
    since = since_ms
    while since < end_ms:
        try:
            data = exchange.fetch_ohlcv(symbol, "1m", since=since, limit=1000)
            if not data:
                break
            last_ts = data[-1][0]
            if last_ts <= since:
                break
            all_ohlcv.extend(data)
            since = last_ts + 60_000
        except Exception as e:
            logger.error(f"Lỗi tải data: {e}")
            time.sleep(2)

    if not all_ohlcv:
        return None

    schema = ["timestamp", "open", "high", "low", "close", "volume"]
    return (
        pl.DataFrame(all_ohlcv, schema=schema, orient="row")
        .with_columns([pl.from_epoch("timestamp", time_unit="ms")])
        .unique(subset=["timestamp"], keep="first")
        .sort("timestamp")
    )


def tai_du_lieu_lich_su(symbol, start_str, end_str):
    """
    Tải nến 1m theo khoảng ngày (YYYY-MM-DD), có CACHE LOCAL theo từng ngày.

    Cơ chế:
      1. Tự thêm 30 ngày buffer trước start để indicator warm-up không bị null.
      2. Mỗi ngày (đã qua) được lưu 1 file parquet trong du_lieu/cache_ohlcv/<symbol>/.
      3. Ngày nào đã có cache thì đọc thẳng từ đĩa (không gọi sàn).
      4. Ngày nào thiếu thì gom các ngày thiếu liền nhau thành đoạn, tải gộp 1 lần
         từ sàn rồi lưu bổ sung vào cache → lần sau chỉ tải phần còn thiếu.
      5. Ngày hiện tại (UTC) luôn tải mới (chưa đóng nến đủ) và KHÔNG cache.
    """
    try:
        start_obj = datetime.strptime(start_str, "%Y-%m-%d")
        since_obj = start_obj - timedelta(days=30)
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=0
        )
    except ValueError:
        logger.error(f"Định dạng ngày {start_str}/{end_str} không hợp lệ. Dùng YYYY-MM-DD")
        return pl.DataFrame()

    cache_dir = _thu_muc_cache(symbol)
    today_utc = datetime.utcnow().date()
    start_date = since_obj.date()
    end_date = end_dt.date()
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    day_frames = {}                                           
    missing = []                           

                                                                                          
    for d in all_dates:
        path = _file_cache_ngay(cache_dir, d)
        if d < today_utc and os.path.exists(path):
            try:
                day_frames[d] = pl.read_parquet(path)
                continue
            except Exception:
                pass                       
        missing.append(d)

                                                             
    if missing:
        n_cached = len(all_dates) - len(missing)
        logger.info(
            f"[Cache] {symbol}: {n_cached}/{len(all_dates)} ngày có sẵn local · "
            f"tải {len(missing)} ngày còn thiếu từ sàn ({since_obj.strftime('%Y-%m-%d')} → {end_str})..."
        )
        exchange = ccxt.binance()
        for g_start, g_end in _gom_ngay_lien_tuc(missing):
            try:
                since_ms = exchange.parse8601(f"{g_start.strftime('%Y-%m-%d')} 00:00:00")
                end_ms = exchange.parse8601(f"{g_end.strftime('%Y-%m-%d')} 23:59:59")
            except Exception as e:
                logger.error(f"Lỗi parse ngày tháng: {e}")
                continue
            df_range = _tai_1m_tu_san(exchange, symbol, since_ms, end_ms)
            if df_range is None or df_range.is_empty():
                continue
                                                                                                      
            d = g_start
            while d <= g_end:
                df_day = df_range.filter(pl.col("timestamp").dt.date() == d)
                if not df_day.is_empty():
                    day_frames[d] = df_day
                    if d < today_utc:
                        try:
                            df_day.write_parquet(_file_cache_ngay(cache_dir, d))
                        except Exception as e:
                            logger.warning(f"[Cache] Không lưu được ngày {d}: {e}")
                d += timedelta(days=1)
    else:
        logger.info(f"[Cache] {symbol}: dùng 100% dữ liệu local ({len(all_dates)} ngày), không cần gọi sàn.")

    if not day_frames:
        return pl.DataFrame()

                                                                             
    df = (
        pl.concat([day_frames[d] for d in sorted(day_frames)])
        .unique(subset=["timestamp"], keep="first")
        .filter((pl.col("timestamp") >= since_obj) & (pl.col("timestamp") <= end_dt))
        .sort("timestamp")
    )
    return df
