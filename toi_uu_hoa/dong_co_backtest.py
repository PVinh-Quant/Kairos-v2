"""
toi_uu_hoa_low/dong_co_backtest.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Động cơ backtest nhanh (in-memory loop) cho bộ tối ưu hóa .

Thiết kế tách biệt khỏi vectorized_backtest.py chính để tránh các thao tác I/O
và overhead phân tích đồ họa, giúp chạy hàng nghìn trials mà không bị nghẽn cổ chai.
Đảm bảo đồng bộ 100% logic tính toán SL/TP, phí giao dịch, độ trượt giá và thanh lý vị thế.
"""

import pandas as pd
import numpy as np
import scipy.stats as stats



RISK_FREE_RATE_ANNUAL = 0.0
RISK_FREE_RATE_DAILY = RISK_FREE_RATE_ANNUAL / 365



_SQRT_365 = 19.1049731745428


_EULER_GAMMA = 0.5772156649015329




_NO_DATA_SHARPE = -10.0





MIN_TRADES_TIN_CAY = 30
MIN_DAYS_TIN_CAY = 14




SHARPE_CLIP = 6.0






def run_fast_backtest(df, von_ban_dau, phi_gd, slippage, von_moi_lenh, default_leverage, cooldown_nen=5):
    """
    Giả lập khớp lệnh và quản lý vị thế chi tiết trong bộ nhớ (in-memory candle loop).
    Đồng bộ logic cốt lõi với trình backtest chính.

    CƠ CHẾ SL/TP PESSIMISTIC MODE (Chế độ phòng ngừa rủi ro cực đoan):
    Khi trong cùng một nến, cả hai mức chặn lỗ (SL) và chốt lời (TP) đều bị chạm
    (do nến dao động mạnh vượt cả biên trên và biên dưới), trình mô phỏng sẽ giả định
    chạm chặn lỗ (SL) TRƯỚC. Điều này giúp ngăn chặn việc đánh giá quá lạc quan
    (over-optimistic bias) và tránh ảo tưởng về lợi nhuận của chiến lược.

    Args:
        df: DataFrame chứa dữ liệu OHLC và các cột tín hiệu, SL, TP động.
        von_ban_dau: Số vốn ban đầu của danh mục.
        phi_gd: Tỷ lệ phí giao dịch (ví dụ: 0.001 tương đương 0.1%).
        slippage: Tỷ lệ độ trượt giá bất lợi khi khớp lệnh market (ví dụ: 0.001 = 0.1%).
        von_moi_lenh: Quy mô phân bổ vốn cố định cho mỗi lệnh (USDT).
        default_leverage: Đòn bẩy mặc định sử dụng nếu không có đòn bẩy động.

    Returns:
        tuple: (trades: list[dict], von_cuoi: float)
            - trades: Danh sách lịch sử giao dịch (PnL net, equity trước lệnh, timestamp).
            - von_cuoi: Số vốn còn lại sau khi kết thúc quá trình chạy dữ liệu.
    """
    von_hien_tai = von_ban_dau
    vi_the = 0
    gia_vao = 0.0
    co_tin_hieu = 0
    don_bay_vao = default_leverage


    if hasattr(df, "clone"):
        signals   = df['signal'].to_numpy()
        signals_raw = df['signal_raw'].to_numpy() if 'signal_raw' in df.columns else signals
        opens     = df['open'].to_numpy()
        closes    = df['close'].to_numpy()
        highs     = df['high'].to_numpy()   if 'high'     in df.columns else closes.copy()
        lows      = df['low'].to_numpy()    if 'low'      in df.columns else closes.copy()
        times     = df['timestamp'].to_numpy()
        sl_pcts   = df['sl_pct'].to_numpy()   if 'sl_pct'   in df.columns else np.array([0.05] * len(df))
        tp_pcts   = df['tp_pct'].to_numpy()   if 'tp_pct'   in df.columns else np.array([0.10] * len(df))
        leverages = df['leverage'].to_numpy() if 'leverage' in df.columns else np.array([default_leverage] * len(df))
    else:
        signals   = df['signal'].values
        signals_raw = df['signal_raw'].values if 'signal_raw' in df.columns else signals
        opens     = df['open'].values
        closes    = df['close'].values
        highs     = df['high'].values   if 'high'     in df.columns else closes.copy()
        lows      = df['low'].values    if 'low'      in df.columns else closes.copy()
        times     = df['timestamp'].values
        sl_pcts   = df['sl_pct'].values   if 'sl_pct'   in df.columns else np.array([0.05] * len(df))
        tp_pcts   = df['tp_pct'].values   if 'tp_pct'   in df.columns else np.array([0.10] * len(df))
        leverages = df['leverage'].values if 'leverage' in df.columns else np.array([default_leverage] * len(df))

    sl_gia = tp_gia = liq_gia = equity_khi_vao = 0.0
    trades = []



    dem_cooldown = 0
    COOLDOWN_NEN = int(cooldown_nen)

    signal_indices = np.where(signals != 0)[0]
    num_signals = len(signal_indices)
    sig_ptr = 0

    i = 0
    n = len(df)
    while i < n:

        if dem_cooldown > 0:
            dem_cooldown -= 1


        if vi_the == 0 and co_tin_hieu == 0 and dem_cooldown == 0:
            while sig_ptr < num_signals and signal_indices[sig_ptr] < i:
                sig_ptr += 1
            if sig_ptr >= num_signals:
                break
            i = signal_indices[sig_ptr]

        tin_hieu_hien_tai = signals[i]
        tin_hieu_raw = signals_raw[i]
        gia_open  = opens[i]
        gia_close = closes[i]
        gia_high  = highs[i]
        gia_low   = lows[i]
        thoi_gian = times[i]
        don_bay_i = int(leverages[i])



        if co_tin_hieu != 0 and vi_the == 0:

            if von_hien_tai < von_moi_lenh:
                co_tin_hieu = 0
                i += 1
                continue

            vi_the      = co_tin_hieu
            don_bay_vao = don_bay_i
            phi_truot   = gia_open * slippage




            gia_vao = gia_open + phi_truot if vi_the == 1 else gia_open - phi_truot


            sl_pct_i = sl_pcts[i - 1] if i > 0 else 0.05
            tp_pct_i = tp_pcts[i - 1] if i > 0 else 0.10


            if vi_the == 1:
                sl_gia  = gia_vao * (1 - sl_pct_i)
                tp_gia  = gia_vao * (1 + tp_pct_i)

                liq_gia = gia_vao * (1.0 - 1.0 / don_bay_vao)
            else:
                sl_gia  = gia_vao * (1 + sl_pct_i)
                tp_gia  = gia_vao * (1 - tp_pct_i)
                liq_gia = gia_vao * (1.0 + 1.0 / don_bay_vao)


            phi_mo       = von_moi_lenh * don_bay_vao * phi_gd
            equity_khi_vao = von_hien_tai
            von_hien_tai -= phi_mo
            co_tin_hieu   = 0


            if von_hien_tai <= 0:
                return (trades, 0.0)


        if vi_the != 0:
            can_thoat = False
            la_thanh_ly = False
            gia_dong  = gia_close




            if vi_the == 1:
                if gia_low <= sl_gia:
                    can_thoat = True
                    gia_dong  = sl_gia
                elif gia_high >= tp_gia:
                    can_thoat = True
                    gia_dong  = tp_gia
                elif gia_low <= liq_gia:
                    can_thoat = True
                    gia_dong  = liq_gia
                    la_thanh_ly = True
                elif tin_hieu_raw == -1:

                    can_thoat = True

            else:
                if gia_high >= sl_gia:
                    can_thoat = True
                    gia_dong  = sl_gia
                elif gia_low <= tp_gia:
                    can_thoat = True
                    gia_dong  = tp_gia
                elif gia_high >= liq_gia:
                    can_thoat = True
                    gia_dong  = liq_gia
                    la_thanh_ly = True
                elif tin_hieu_raw == 1:

                    can_thoat = True


            if can_thoat:
                if la_thanh_ly:

                    pnl_raw  = -von_moi_lenh
                    phi_dong = 0.0
                else:

                    phi_truot_dong = gia_dong * slippage
                    gia_dong = gia_dong - phi_truot_dong if vi_the == 1 else gia_dong + phi_truot_dong

                    pnl_raw  = (
                        (gia_dong - gia_vao) / gia_vao if vi_the == 1
                        else (gia_vao - gia_dong) / gia_vao
                    ) * (von_moi_lenh * don_bay_vao)

                    phi_dong = von_moi_lenh * don_bay_vao * phi_gd





                phi_mo_lenh = von_moi_lenh * don_bay_vao * phi_gd
                pnl_net  = pnl_raw - phi_dong - phi_mo_lenh

                von_hien_tai += (pnl_raw - phi_dong)

                trades.append({
                    'pnl': pnl_net,
                    'equity_before': equity_khi_vao,
                    'time': thoi_gian
                })
                vi_the = 0
                dem_cooldown = COOLDOWN_NEN


                if von_hien_tai <= 0:
                    return (trades, 0.0)



        if vi_the == 0 and tin_hieu_hien_tai != 0 and dem_cooldown == 0:
            co_tin_hieu = tin_hieu_hien_tai

        i += 1

    return (trades, von_hien_tai)






def _xay_dung_daily_pnl_va_equity(trades, von_ban_dau, start_date=None, end_date=None, zero_fill=True):
    """
    Xây dựng chuỗi PnL và đường cong vốn (Equity Curve) theo từng ngày.

    Args:
        zero_fill: Nếu True, điền 0.0 vào các ngày không có giao dịch (dùng cho
                   equity curve & drawdown). Nếu False, chỉ giữ ngày có giao dịch
                   (dùng khi cần tính Sharpe chính xác hơn).
    """
    if not trades:
        return (pd.Series(dtype=float), pd.Series(dtype=float))

    df_trades = pd.DataFrame(trades)
    df_trades['time'] = pd.to_datetime(df_trades['time'])
    df_trades['ngay'] = df_trades['time'].dt.date
    daily_pnl = df_trades.groupby('ngay')['pnl'].sum()


    if zero_fill and start_date and end_date:
        try:
            all_days = pd.date_range(start=start_date, end=end_date, freq='D').date
            daily_pnl = daily_pnl.reindex(all_days, fill_value=0.0)
        except Exception:
            pass

    equity_curve = von_ban_dau + daily_pnl.cumsum()
    return (daily_pnl, equity_curve)


def xay_dung_duong_cong(trades, von_ban_dau, start_date=None, end_date=None):
    """
    Dựng dữ liệu phục vụ VẼ BIỂU ĐỒ phân tích (M4) từ danh sách giao dịch.

    Trả về dict JSON-friendly (list số, an toàn để ghi file & truyền sang GUI):
      - ngay         : danh sách ngày (chuỗi) của đường cong vốn.
      - equity       : vốn triển khai theo từng ngày (đã cộng dồn PnL).
      - drawdown_pct : % sụt giảm từ đỉnh theo ngày (đã kẹp sàn -100%).
      - pnl          : PnL net của TỪNG lệnh (để vẽ histogram phân phối).

    Equity/drawdown đo trên VỐN TRIỂN KHAI cố định (von_ban_dau = notional), nhất
    quán với cách `tinh_da_chi_so` tính MaxDD/Calmar.
    """
    von = round(float(von_ban_dau), 4)
    pnl_list = [round(float(t.get('pnl', 0.0)), 6) for t in (trades or [])]
    daily_pnl, equity_curve = _xay_dung_daily_pnl_va_equity(
        trades, von_ban_dau, start_date, end_date
    )
    if equity_curve.empty:
        return {'von': von, 'ngay': [], 'equity': [], 'drawdown_pct': [], 'pnl': pnl_list}

    running_max = equity_curve.cummax()
    drawdown_pct = ((equity_curve - running_max) / running_max * 100).clip(lower=-100.0, upper=0.0)
    return {
        'von': von,
        'ngay': [str(d) for d in equity_curve.index],
        'equity': [round(float(v), 4) for v in equity_curve.values],
        'drawdown_pct': [round(float(v), 4) for v in drawdown_pct.values],
        'pnl': pnl_list,
    }


def _chuoi_loi_nhuan_ngay(daily_pnl, equity_curve, von_ban_dau):
    """
    Chuỗi lợi nhuận % hằng NGÀY trên VỐN TRIỂN KHAI CỐ ĐỊNH (von_ban_dau).

    Engine đặt lệnh theo notional cố định (von_moi_lenh, KHÔNG gộp lãi theo equity),
    nên lợi nhuận ngày được chia cho mẫu số CỐ ĐỊNH thay vì equity đang chạy. Nhờ vậy
    Sharpe bất biến theo scale và không bị méo bởi hiệu ứng gộp lãi giả.
    """
    base = von_ban_dau if (von_ban_dau and von_ban_dau > 0) else 1.0
    returns = (daily_pnl / base).replace([np.inf, -np.inf], np.nan).dropna()
    return returns


def tinh_sharpe_ratio(trades=None, start_date=None, end_date=None,
                      von_ban_dau=10000, daily_pnl=None, equity_curve=None):
    """
    Sharpe Ratio chuẩn hóa năm (annualized) — phương pháp chuẩn (textbook).

    Tính trên TOÀN BỘ chuỗi lợi nhuận hằng ngày của khoảng lịch (ngày không giao
    dịch = lợi nhuận 0 ⇒ vốn đứng yên), annualize bằng sqrt(365) cho Crypto 24/7.
    Cách này ổn định và KHÔNG bị bão hòa ở các "rail" như annualization theo tần
    suất giao dịch trên mẫu ngắn (vốn là nguyên nhân khiến Sharpe luôn đụng ±cap).

    Returns:
        float: Sharpe annualized, clip [-9.5, +10] (chỉ để chống blow-up số học).
               Trả về `_NO_DATA_SHARPE` (-10.0) khi dữ liệu KHÔNG đủ tin cậy
               (< _MIN_TRADES lệnh, < _MIN_DAYS ngày, hoặc std = 0). Vì giá trị
               thật bị clip ở -9.5 nên -10.0 luôn nghĩa là "không đủ dữ liệu".
    """
    _MIN_TRADES = MIN_TRADES_TIN_CAY
    _MIN_DAYS = MIN_DAYS_TIN_CAY

    if daily_pnl is None or equity_curve is None:
        if not trades or len(trades) < _MIN_TRADES:
            return _NO_DATA_SHARPE
        daily_pnl, equity_curve = _xay_dung_daily_pnl_va_equity(
            trades, von_ban_dau, start_date, end_date
        )

    if len(daily_pnl) < _MIN_DAYS:
        return _NO_DATA_SHARPE

    daily_returns = _chuoi_loi_nhuan_ngay(daily_pnl, equity_curve, von_ban_dau)
    if len(daily_returns) < _MIN_DAYS:
        return _NO_DATA_SHARPE

    excess = daily_returns - RISK_FREE_RATE_DAILY
    mean_r = excess.mean()
    std_r = excess.std(ddof=1)
    if std_r == 0 or pd.isna(std_r):
        return _NO_DATA_SHARPE

    sharpe = mean_r / std_r * _SQRT_365
    return float(np.clip(sharpe, -SHARPE_CLIP, SHARPE_CLIP))


def tinh_sortino_ratio(trades=None, start_date=None, end_date=None,
                       von_ban_dau=10000, daily_pnl=None, equity_curve=None):
    """
    Sortino Ratio chuẩn hóa năm (annualized).

    Giống Sharpe nhưng MẪU SỐ chỉ dùng độ lệch chuẩn của phần GIẢM (downside
    deviation) — chỉ phạt biến động thua lỗ, không phạt biến động lãi đột phá.
    Cùng quy ước dữ liệu & sentinel với `tinh_sharpe_ratio`.

    Returns:
        float: Sortino annualized, clip [-9.5, +10]. Trả `_NO_DATA_SHARPE` (-10.0)
               khi dữ liệu không đủ tin cậy (< _MIN_TRADES, < _MIN_DAYS, hoặc không
               có nến giảm để đo downside).
    """
    _MIN_TRADES = MIN_TRADES_TIN_CAY
    _MIN_DAYS = MIN_DAYS_TIN_CAY

    if daily_pnl is None or equity_curve is None:
        if not trades or len(trades) < _MIN_TRADES:
            return _NO_DATA_SHARPE
        daily_pnl, equity_curve = _xay_dung_daily_pnl_va_equity(
            trades, von_ban_dau, start_date, end_date
        )

    if len(daily_pnl) < _MIN_DAYS:
        return _NO_DATA_SHARPE

    daily_returns = _chuoi_loi_nhuan_ngay(daily_pnl, equity_curve, von_ban_dau)
    if len(daily_returns) < _MIN_DAYS:
        return _NO_DATA_SHARPE

    excess = daily_returns - RISK_FREE_RATE_DAILY
    mean_r = excess.mean()



    downside = excess.where(excess < 0, 0.0)
    downside_dev = (downside.pow(2).mean()) ** 0.5
    if downside_dev == 0 or pd.isna(downside_dev):


        return SHARPE_CLIP if mean_r > 0 else _NO_DATA_SHARPE

    sortino = mean_r / downside_dev * _SQRT_365
    return float(np.clip(sortino, -SHARPE_CLIP, SHARPE_CLIP))


def tinh_dsr(sharpe_observed_ann, n_trials, daily_returns, n_returns):
    """
    Tính chỉ số Deflated Sharpe Ratio (DSR) theo Bailey & López de Prado (2014).

    DSR kiểm tra xem chiến lược/bộ tham số được tìm ra có thực sự vượt trội hay
    chỉ là kết quả ăn may do đã thử nghiệm quá nhiều lần (Multiple Testing Bias / Data Mining Bias).

    DSR khấu trừ Sharpe Ratio quan sát được dựa trên:
    - Số lượng thử nghiệm (n_trials).
    - Phân phối phi chuẩn của chuỗi returns (skewness & kurtosis).
    - Độ dài chuỗi quan sát (n_returns).

    DSR tiệm cận 1.0 (ví dụ >0.90) chứng minh bộ tham số có thực lực toán học vững chắc.
    DSR gần 0.0 là dấu hiệu của overfitting HOẶC chiến lược thua lỗ (Sharpe ≤ 0).

    - n_trials > 1  : khấu trừ ngưỡng Sharpe kỳ vọng tối đa do thử nhiều lần (deflation).
    - n_trials ≤ 1  : rút gọn về Probabilistic Sharpe Ratio (PSR) với chuẩn so sánh 0
                      → xác suất Sharpe THẬT > 0. (KHÔNG mặc định trả 1.0 — đây là lỗi cũ
                      khiến chiến lược thua lỗ trên OOS vẫn nhận DSR = 100%.)
    """

    if sharpe_observed_ann is None or sharpe_observed_ann <= _NO_DATA_SHARPE + 0.01:
        return 0.0
    if daily_returns is None or n_returns is None or n_returns < 5:
        return 0.0

    skew = daily_returns.skew()
    kurt = daily_returns.kurt() + 3.0
    if pd.isna(skew):
        skew = 0.0
    if pd.isna(kurt):
        kurt = 3.0


    sr_obs_daily = sharpe_observed_ann / _SQRT_365



    sr_star = 0.0
    if n_trials and n_trials > 1:
        try:
            z_n = (
                (1 - _EULER_GAMMA) * stats.norm.ppf(1 - 1.0 / n_trials)
                + _EULER_GAMMA    * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
            )
            sr_star = (1.0 / n_returns) ** 0.5 * z_n
        except Exception:
            sr_star = 0.0


    v_sr_obs = (
        1.0 - skew * sr_obs_daily + (kurt - 1.0) / 4.0 * (sr_obs_daily ** 2)
    ) / max(n_returns - 1, 1)

    if v_sr_obs <= 0 or pd.isna(v_sr_obs):
        return 0.0
    se_obs = v_sr_obs ** 0.5


    z_score = (sr_obs_daily - sr_star) / se_obs
    return float(stats.norm.cdf(z_score))


def tinh_da_chi_so(trades, von_ban_dau, start_date=None, end_date=None, n_trials=1):
    """
    Tính toán tập hợp các chỉ số đánh giá chiến lược chuẩn Quant.

    Returns:
        dict: Chứa các chỉ số quant bao gồm:
            - sharpe_ratio: Sharpe Ratio chuẩn hóa năm.
            - max_drawdown_pct: Mức sụt giảm tài sản lớn nhất từ đỉnh (%).
            - calmar_ratio: Tỷ lệ sinh lời trên rủi ro tối đa (CAGR / |MaxDD|).
            - win_rate: Tỷ lệ giao dịch chiến thắng (%).
            - profit_factor: Lợi nhuận gộp trên thua lỗ gộp.
            - total_trades: Tổng số giao dịch đã thực hiện.
            - avg_trade_pnl: Lợi nhuận trung bình mỗi giao dịch.
            - deflated_sharpe_ratio: Chỉ số DSR tránh overfitting.
    """
    ket_qua = {
        'sharpe_ratio':          _NO_DATA_SHARPE,
        'sortino_ratio':         _NO_DATA_SHARPE,
        'max_drawdown_pct':       0.0,
        'calmar_ratio':           0.0,
        'win_rate':               0.0,
        'profit_factor':          0.0,
        'total_trades':           0,
        'avg_trade_pnl':          0.0,
        'deflated_sharpe_ratio':  0.0,
    }

    if not trades or len(trades) < MIN_TRADES_TIN_CAY:
        ket_qua['total_trades'] = len(trades) if trades else 0
        return ket_qua

    df_trades  = pd.DataFrame(trades)
    n_trades   = len(df_trades)
    daily_pnl, equity_curve = _xay_dung_daily_pnl_va_equity(
        trades, von_ban_dau, start_date, end_date
    )


    ket_qua['sharpe_ratio'] = tinh_sharpe_ratio(
        von_ban_dau=von_ban_dau, daily_pnl=daily_pnl, equity_curve=equity_curve
    )
    ket_qua['sortino_ratio'] = tinh_sortino_ratio(
        von_ban_dau=von_ban_dau, daily_pnl=daily_pnl, equity_curve=equity_curve
    )



    running_max  = equity_curve.cummax()
    drawdown_pct = (equity_curve - running_max) / running_max * 100
    max_dd = float(np.clip(drawdown_pct.min(), -100.0, 0.0))
    ket_qua['max_drawdown_pct'] = max_dd




    if max_dd != 0:
        total_return = equity_curve.iloc[-1] / von_ban_dau - 1
        calmar = total_return / abs(max_dd / 100.0)
        ket_qua['calmar_ratio'] = round(float(np.clip(calmar, -100.0, 100.0)), 4)


    wins         = df_trades[df_trades['pnl'] > 0]
    gross_profit = float(df_trades[df_trades['pnl'] > 0]['pnl'].sum())
    gross_loss   = abs(float(df_trades[df_trades['pnl'] <= 0]['pnl'].sum()))

    ket_qua['win_rate']      = round(len(wins) / n_trades * 100, 2)
    ket_qua['profit_factor'] = round(gross_profit / gross_loss, 4) if gross_loss > 0 else 0.0
    ket_qua['avg_trade_pnl'] = round(float(df_trades['pnl'].mean()), 4)
    ket_qua['total_trades']  = n_trades



    if n_trades >= MIN_TRADES_TIN_CAY:
        daily_returns = _chuoi_loi_nhuan_ngay(daily_pnl, equity_curve, von_ban_dau)
        n_returns = len(daily_returns)
        if n_returns >= 5:
            ket_qua['deflated_sharpe_ratio'] = tinh_dsr(
                sharpe_observed_ann=ket_qua['sharpe_ratio'],
                n_trials=n_trials,
                daily_returns=daily_returns,
                n_returns=n_returns,
            )

    return ket_qua

