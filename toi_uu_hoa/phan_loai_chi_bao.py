"""
toi_uu_hoa_low/phan_loai_chi_bao.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phân loại chỉ báo kỹ thuật và tạo tín hiệu giao dịch tổng quát.

Hỗ trợ bộ tối ưu hóa  chạy thử nghiệm chiến lược cho mọi chỉ báo
trong INDICATOR_REGISTRY mà không cần biết logic nội bộ của từng hàm.

Hệ thống tự động:
1. Nhận diện loại chỉ báo (Oscillator, Channel, Trend, Volume) qua whitelist hoặc chạy thử.
2. Sinh tín hiệu giao dịch tương ứng theo template thiết kế cho từng nhóm chỉ báo.
"""

import inspect
import pandas as pd
import numpy as np







_OSCILLATOR_FUNCS = [
    'pt_rsi', 'pt_stochastic',
    'pt_mfi', 'pt_ultimate_oscillator',
    'pt_stoch_rsi', 'pt_stc',
    'pt_elder_ray', 'pt_choppiness_index',
]
_CHANNEL_FUNCS = [
    'pt_bollinger_squeeze', 'pt_keltner_channel', 'pt_donchian_channel', 'pt_atr_bands',
    'pt_chandelier_exit',
]
_TREND_FUNCS = [
    'pt_ema_trend', 'pt_sma', 'pt_adx', 'pt_supertrend', 'pt_macd', 'pt_psar',
    'pt_aroon', 'pt_vortex', 'pt_fractals',
    'pt_hma', 'pt_kama', 'pt_alma', 'pt_vwma',
]
_VOLUME_FUNCS = [
    'pt_volume', 'pt_obv', 'pt_vwap', 'pt_cmf', 'pt_mfi_volume',
    'pt_pvt', 'pt_chaikin_oscillator',
]


_OSCILLATOR_KEYWORDS = ['rsi', 'stoch', 'mfi', 'ultimate']
_CHANNEL_KEYWORDS    = ['upper', 'lower', 'band', 'channel', 'ub', 'lb', 'high_band', 'low_band']
_TREND_KEYWORDS      = ['ema', 'sma', 'ma', 'trend', 'direction', 'psar', 'supertrend', 'adx', 'aroon', 'vortex', 'macd']
_VOLUME_KEYWORDS     = ['obv', 'vwap', 'cmf', 'volume', 'mfi_vol']


_OSCILLATOR_FUNCS_SET = set(f.lower() for f in _OSCILLATOR_FUNCS)
_CHANNEL_FUNCS_SET    = set(f.lower() for f in _CHANNEL_FUNCS)
_TREND_FUNCS_SET      = set(f.lower() for f in _TREND_FUNCS)
_VOLUME_FUNCS_SET     = set(f.lower() for f in _VOLUME_FUNCS)








_CENTERED_OSC_BASES = {'power', 'eom'}


def is_centered_oscillator(col):
    """True nếu cột chỉ báo là oscillator dao động quanh 0 (xét theo token tên cột).

    Khớp theo token tách bởi '_' nên 's0_bull_power_1h', 'bear_power_1h' đều
    nhận đúng nhờ token 'power'.
    """
    if not isinstance(col, str):
        return False
    return any(tok in _CENTERED_OSC_BASES for tok in col.lower().split('_'))






def _build_test_df(n=200):
    """
    Tạo một DataFrame OHLCV tổng hợp giả lập đủ dài để các chỉ báo tính toán.
    Sử dụng numpy seed cố định để đảm bảo kết quả phân loại luôn đồng nhất.
    """
    import polars as pl
    np.random.seed(42)
    close = 50000.0 + np.cumsum(np.random.randn(n) * 100)
    close = np.maximum(close, 100.0)
    high  = close * (1 + np.abs(np.random.randn(n) * 0.005))
    low   = close * (1 - np.abs(np.random.randn(n) * 0.005))
    open_ = close + np.random.randn(n) * 50
    vol   = np.abs(np.random.randn(n) * 1000) + 500
    ts    = pd.date_range(start='2024-01-01', periods=n, freq='1h')
    return pl.DataFrame({
        'timestamp': ts, 'open': open_, 'high': high,
        'low': low, 'close': close, 'volume': vol,
    })


def get_cols_by_type(new_cols, t_type):
    """
    Hàm chuẩn chọn lọc cột đầu ra chính đại diện từ danh sách các cột mới sinh ra.
    Dùng chung bởi  (bo_dieu_phoi) và JSONStrategy để đảm bảo 'Một nguồn sự thật',
    không bị trôi lệch cột tín hiệu khi chạy thực tế.
    """
    if not new_cols:
        return None if t_type != 'channel' else (None, None)

    col_lower = next((c for c in new_cols if any(k in c.lower() for k in ['lower', 'low_band', 'bot', 'support', 'lb'])), None)
    col_upper = next((c for c in new_cols if any(k in c.lower() for k in ['upper', 'high_band', 'top', 'resist', 'ub'])), None)
    col_rsi = next((c for c in new_cols if any(k in c.lower() for k in ['rsi', 'mfi', 'stoch', 'ult'])), None)

    col_bool_signal = next((c for c in new_cols if any(k in c.lower() for k in [
        'has_trend', 'is_strong_trend',
        'is_st_uptrend',
        'macd_cross_up', 'macd_cross_down', 'macd_bullish',
        'is_bull', 'is_uptrend', 'is_psar_bull'
    ])), None)
    col_ma = next((c for c in new_cols if any(k in c.lower() for k in ['ema', 'sma', 'ma', 'trend', 'line', 'signal', 'psar', 'aroon'])), None)
    col_adx_raw = next((c for c in new_cols if c.lower().startswith('adx_')), None)

    if t_type == 'oscillator':
        return col_rsi if col_rsi else new_cols[0]
    elif t_type == 'channel':
        if col_upper and col_lower:
            return (col_upper, col_lower)
        elif len(new_cols) >= 2:
            return (new_cols[0], new_cols[1])
        else:
            return (new_cols[0], new_cols[0])
    else:
        if col_bool_signal:
            return col_bool_signal
        elif col_ma:
            return col_ma
        elif col_adx_raw:
            return col_adx_raw
        return new_cols[0]


def _pick_primary_col(new_cols, indicator_type, fallback_name):
    """
    Chọn lọc cột đầu ra chính đại diện từ danh sách các cột mới sinh ra.
    Ủy quyền xử lý cho hàm chuẩn get_cols_by_type.
    """
    res = get_cols_by_type(new_cols, indicator_type)
    if isinstance(res, tuple):
        return res[0] if res[0] else fallback_name
    return res if res else fallback_name






def detect_indicator_type(indicator_func, time_frame='1h'):
    """
    Tự động phát hiện loại chỉ báo (oscillator, channel, trend, volume)
    và tên cột đầu ra chính đại diện cho nó.

    Cơ chế hoạt động 2 tầng:
    1. So khớp tên hàm với Whitelist đã định nghĩa sẵn → Rất nhanh (O(1)).
    2. Fallback: Nếu là chỉ báo lạ, chạy thử hàm trên một DataFrame giả lập,
       quét tên các cột đầu ra mới để suy đoán loại chỉ báo thích hợp.

    Args:
        indicator_func: Đối tượng hàm chỉ báo kỹ thuật cần nhận diện.
        time_frame: Khung thời gian dùng khi chạy thử (mặc định là '1h').

    Returns:
        tuple: (target_type, target_col_base)
            - target_type: 'oscillator' | 'channel' | 'trend' | 'volume'
            - target_col_base: Tên cột chính (str) chứa giá trị chỉ báo.
    """
    func_name = indicator_func.__name__.lower()


    if func_name in _OSCILLATOR_FUNCS_SET:
        indicator_type = 'oscillator'
    elif func_name in _CHANNEL_FUNCS_SET:
        indicator_type = 'channel'
    elif func_name in _VOLUME_FUNCS_SET:
        indicator_type = 'volume'
    elif func_name in _TREND_FUNCS_SET:
        indicator_type = 'trend'
    else:
        indicator_type = None


    test_df = _build_test_df()
    sig     = inspect.signature(indicator_func)
    params  = sig.parameters


    kwargs = {}
    if 'window'    in params: kwargs['window']    = 14
    if 'deviation' in params: kwargs['deviation'] = 2.0
    if 'lookback'  in params: kwargs['lookback']  = 10
    if 'fast'      in params: kwargs['fast']      = 12
    if 'slow'      in params: kwargs['slow']      = 26

    try:
        result_df = indicator_func(test_df.clone(), time_frame, **kwargs)
        new_cols  = [c for c in result_df.columns if c not in test_df.columns]
    except Exception as e:
        print(f"[WARN] Không thể chạy thử chỉ báo '{indicator_func.__name__}': {e}")
        new_cols  = []


    if indicator_type is None:
        col_str  = ' '.join(new_cols).lower()
        has_upper = any(k in col_str for k in ['upper', 'ub', 'high_band', 'band_h', 'resist'])
        has_lower = any(k in col_str for k in ['lower', 'lb', 'low_band',  'band_l', 'support'])

        if has_upper and has_lower:
            indicator_type = 'channel'
        elif any(k in col_str for k in _OSCILLATOR_KEYWORDS):
            indicator_type = 'oscillator'
        elif any(k in col_str for k in _VOLUME_KEYWORDS):
            indicator_type = 'volume'
        else:
            indicator_type = 'trend'


    target_col_base = _pick_primary_col(new_cols, indicator_type, func_name)
    return (indicator_type, target_col_base)


def generate_generic_signals(df, target_type, target_col, suggested_params):
    """
    Tạo cột tín hiệu 'signal' (1=LONG, -1=SHORT, 0=NO POSITION) theo loại chỉ báo bằng Polars.
    Hỗ trợ cả Pandas và Polars DataFrame đầu vào để đảm bảo tính tương thích ngược.
    """
    import polars as pl
    import numpy as np

    is_pandas = not hasattr(df, "clone")
    if is_pandas:
        df_pl = pl.from_pandas(df)
    else:
        df_pl = df.clone()

    df_pl = df_pl.with_columns(pl.lit(0).cast(pl.Int64).alias("signal"))

    def _get_col(tc):
        return tc if isinstance(tc, str) else (tc[0] if tc else None)


    if target_type == 'oscillator':
        col = _get_col(target_col)
        if col is None or col not in df_pl.columns:
            return df if is_pandas else df_pl

        series = pl.col(col)

        if is_centered_oscillator(col):

            oversold = suggested_params.get('oversold')
            overbought = suggested_params.get('overbought')

            if oversold is not None and overbought is not None:

                prev = pl.col(col).shift(1)
                buy_signal = (prev < oversold) & (series >= oversold)
                sell_signal = (prev > overbought) & (series <= overbought)
                sig_expr = pl.when(buy_signal).then(1) \
                    .when(sell_signal).then(-1) \
                    .otherwise(0)
            else:

                sig_expr = pl.when(series > 0).then(1) \
                    .when(series < 0).then(-1) \
                    .otherwise(0)
        else:

            oversold   = suggested_params.get('oversold',   30)
            overbought = suggested_params.get('overbought', 70)
            prev = pl.col(col).shift(1)
            buy_signal = (prev < oversold) & (series >= oversold)
            sell_signal = (prev > overbought) & (series <= overbought)
            sig_expr = pl.when(buy_signal).then(1) \
                .when(sell_signal).then(-1) \
                .otherwise(0)

        df_pl = df_pl.with_columns(sig_expr.alias("signal"))

        df_pl = df_pl.with_columns(
            pl.when(pl.col("signal") == 0).then(None).otherwise(pl.col("signal"))
            .forward_fill()
            .fill_null(0)
            .cast(pl.Int64)
            .alias("signal")
        )


    elif target_type == 'channel':
        if isinstance(target_col, tuple):
            col_upper, col_lower = target_col
        else:
            col_upper = col_lower = target_col

        if col_upper not in df_pl.columns or col_lower not in df_pl.columns:
            return df if is_pandas else df_pl

        lower_mult = suggested_params.get('lower_mult', 1.0)
        upper_mult = suggested_params.get('upper_mult', 1.0)

        buy_signal  = pl.col('close') <= pl.col(col_lower) * lower_mult
        sell_signal = pl.col('close') >= pl.col(col_upper) * upper_mult

        sig_expr = pl.when(buy_signal).then(1) \
            .when(sell_signal).then(-1) \
            .otherwise(0)

        df_pl = df_pl.with_columns(sig_expr.alias("signal"))


    elif target_type == 'trend':
        col = _get_col(target_col)
        if col is None or col not in df_pl.columns:
            return df if is_pandas else df_pl


        col_dtype = df_pl.schema[col]
        is_bool_col = col_dtype == pl.Boolean

        if is_bool_col:

            col_lower = col.lower()
            is_cross_signal = 'cross_up' in col_lower or 'cross_down' in col_lower

            if is_cross_signal:


                if 'cross_up' in col_lower:
                    sig_expr = pl.when(pl.col(col) == True).then(1).otherwise(0)
                else:
                    sig_expr = pl.when(pl.col(col) == True).then(-1).otherwise(0)
                df_pl = df_pl.with_columns(sig_expr.alias("signal"))
            else:


                signal_col = pl.col(col)
                prev_signal = pl.col(col).shift(1)

                buy_signal  = (prev_signal == False) & (signal_col == True)
                sell_signal = (prev_signal == True) & (signal_col == False)

                sig_expr = pl.when(buy_signal).then(1) \
                    .when(sell_signal).then(-1) \
                    .otherwise(0)

                df_pl = df_pl.with_columns(sig_expr.alias("signal"))


                df_pl = df_pl.with_columns(
                    pl.when(pl.col("signal") == 0).then(None).otherwise(pl.col("signal"))
                    .forward_fill()
                    .fill_null(0)
                    .cast(pl.Int64)
                    .alias("signal")
                )
        else:

            dev_above = suggested_params.get('dev_above', 1.0) / 100.0
            dev_below = suggested_params.get('dev_below', 1.0) / 100.0

            ma = pl.col(col)
            prev_close = pl.col('close').shift(1)
            prev_ma = pl.col(col).shift(1)

            buy_signal  = (prev_close < prev_ma * (1.0 + dev_above)) & (pl.col('close') >= ma * (1.0 + dev_above))
            sell_signal = (prev_close > prev_ma * (1.0 - dev_below)) & (pl.col('close') <= ma * (1.0 - dev_below))

            sig_expr = pl.when(buy_signal).then(1) \
                .when(sell_signal).then(-1) \
                .otherwise(0)

            df_pl = df_pl.with_columns(sig_expr.alias("signal"))

            df_pl = df_pl.with_columns(
                pl.when(pl.col("signal") == 0).then(None).otherwise(pl.col("signal"))
                .forward_fill()
                .fill_null(0)
                .cast(pl.Int64)
                .alias("signal")
            )


    elif target_type == 'volume':
        col = _get_col(target_col)
        if col is None or col not in df_pl.columns:
            return df if is_pandas else df_pl




        vol_enter = suggested_params.get('vol_enter', 1.0)
        vol_exit  = suggested_params.get('vol_exit', 1.0)

        series       = pl.col(col)
        rolling_mean = pl.col(col).rolling_mean(window_size=20, min_periods=5)
        prev_close   = pl.col('close').shift(1)

        enter_long  = (series > rolling_mean * vol_enter) & (pl.col('close') > prev_close)
        enter_short = (series > rolling_mean * vol_enter) & (pl.col('close') < prev_close)
        exit_flat   = series < rolling_mean * vol_exit


        sig_expr = pl.when(enter_long).then(1) \
            .when(enter_short).then(-1) \
            .when(exit_flat).then(0) \
            .otherwise(None)

        df_pl = df_pl.with_columns(sig_expr.alias("signal"))

        df_pl = df_pl.with_columns(
            pl.col("signal")
            .forward_fill()
            .fill_null(0)
            .cast(pl.Int64)
            .alias("signal")
        )

    return df_pl.to_pandas() if is_pandas else df_pl


def ket_hop_tin_hieu_spec(df, resolved_specs, logic="and", persistence=1):
    """
    Kết hợp tín hiệu của nhiều spec chỉ báo thành 1 cột `signal` (1/-1/0).

    ĐÂY LÀ NGUỒN DUY NHẤT cho việc kết hợp tín hiệu đa-chỉ-báo, dùng CHUNG bởi:
      • optimizer  (toi_uu_hoa_low/bo_dieu_phoi._chay_backtest_combo)
      • JSONStrategy (chien_luoc/json_strategy.tinh_tin_hieu_vectorized → vectorized/bar-to-bar/live)
    Trước đây hai nơi tự cài bản sao gần giống hệt → dễ trôi lệch. Gộp về 1 hàm để loại nguy cơ đó.

    Mỗi phần tử `resolved_specs` là dict (theo đúng thứ tự muốn xử lý):
        t_type     : loại chỉ báo ('oscillator'/'channel'/'trend'/'volume')
        tcol       : tên cột mục tiêu (str, hoặc tuple cho channel) — đã có sẵn trong df
        thresholds : dict ngưỡng truyền cho generate_generic_signals
        role       : 'trigger' (mặc định) hoặc 'filter'

    Quy tắc (giữ nguyên hành vi cũ):
      • Trigger kết hợp theo `logic` ('and' = mọi trigger đồng thuận / 'or' = bất kỳ).
      • Filter LUÔN AND (mọi filter phải cùng chiều mới cho vào lệnh).
      • Persistence N: tín hiệu trigger còn hiệu lực N nến sau khi xuất hiện (rolling_max).
      • Xung đột long & short cùng đúng tại 1 nến → 0.
      • Spec có tcol=None bị bỏ qua.

    Trả về (df, co_trigger):
        df         : df đã thêm cột `signal` (Int64); không có trigger hợp lệ → signal toàn 0.
        co_trigger : True nếu có ≥1 spec role='trigger' hợp lệ (caller dùng để quyết bỏ qua symbol).
    Giữ nguyên kiểu Pandas/Polars của đầu vào.
    """
    import polars as pl

    is_pandas = not hasattr(df, "clone")
    df_pl = pl.from_pandas(df) if is_pandas else df.clone()

    persistence = int(persistence or 1)
    logic = (logic or "and").lower()

    trig_long_list, trig_short_list = [], []
    filt_long_list, filt_short_list = [], []

    for rspec in resolved_specs:
        tcol = rspec.get("tcol")
        if tcol is None:
            continue
        df_sig = generate_generic_signals(df_pl, rspec.get("t_type"), tcol, rspec.get("thresholds", {}) or {})
        sig = df_sig["signal"]
        long_i = (sig == 1)
        short_i = (sig == -1)
        if rspec.get("role", "trigger") == "filter":
            filt_long_list.append(long_i)
            filt_short_list.append(short_i)
        else:
            if persistence > 1:
                long_i = (long_i.cast(pl.Int8).rolling_max(window_size=persistence, min_periods=1) == 1)
                short_i = (short_i.cast(pl.Int8).rolling_max(window_size=persistence, min_periods=1) == 1)
            trig_long_list.append(long_i)
            trig_short_list.append(short_i)

    if not trig_long_list:
        df_pl = df_pl.with_columns(pl.lit(0).cast(pl.Int64).alias("signal"))
        return (df_pl.to_pandas() if is_pandas else df_pl), False

    def _ket_hop(ds, che_do):
        out = ds[0]
        for s in ds[1:]:
            out = (out & s) if che_do == "and" else (out | s)
        return out

    trig_long = _ket_hop(trig_long_list, logic)
    trig_short = _ket_hop(trig_short_list, logic)
    filt_long = _ket_hop(filt_long_list, "and") if filt_long_list else None
    filt_short = _ket_hop(filt_short_list, "and") if filt_short_list else None

    final_long = trig_long if filt_long is None else (trig_long & filt_long)
    final_short = trig_short if filt_short is None else (trig_short & filt_short)

    df_pl = df_pl.with_columns([final_long.alias("_fl"), final_short.alias("_fs")])
    df_pl = df_pl.with_columns(
        pl.when(pl.col("_fl") & ~pl.col("_fs")).then(1)
        .when(pl.col("_fs") & ~pl.col("_fl")).then(-1)
        .otherwise(0)
        .cast(pl.Int64)
        .alias("signal")
    ).drop(["_fl", "_fs"])

    return (df_pl.to_pandas() if is_pandas else df_pl), True


