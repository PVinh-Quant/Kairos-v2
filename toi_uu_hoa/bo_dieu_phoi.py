"""
toi_uu_hoa_low/bo_dieu_phoi.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bộ điều phối chính cho dò tham số & Walk-Forward.

Chịu trách nhiệm:
1. Nạp và quản lý dữ liệu lịch sử đa khung thời gian trong RAM để tăng tốc tính toán.
2. Thiết lập dò tham số trên tập In-Sample (IS).
3. Thực hiện Walk-Forward Validation bằng cách chạy kiểm tra mù trên tập Out-of-Sample (OOS).
4. Tính toán các chỉ số Quant nâng cao như Deflated Sharpe Ratio (DSR) để đánh giá chiến lược.
5. Xuất kết quả chi tiết dưới dạng JSON và bảng xếp hạng so sánh hiệu suất.
"""

import sys
import os
import json
import time
import inspect
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

                                                          
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
                                                       
import random


def _sinh_mot_bo(khong_gian, rng):
    """Sinh 1 bộ tham số (dict) ngẫu nhiên từ không gian tìm kiếm."""
    bo = {}
    for ten, spec in khong_gian.items():
        loai = spec[0]
        if loai == 'int':
            bo[ten] = rng.randint(spec[1], spec[2])
        elif loai == 'float':
            lo, hi, buoc = spec[1], spec[2], spec[3]
            if buoc:
                so_buoc = int(round((hi - lo) / buoc))
                bo[ten] = round(lo + rng.randint(0, so_buoc) * buoc, 4)
            else:
                bo[ten] = round(rng.uniform(lo, hi), 6)
        elif loai == 'cat':
            bo[ten] = rng.choice(spec[1])
    return bo


def _sinh_danh_sach_bo(khong_gian, so_luong, seed=42):
    """Sinh TRƯỚC danh sách `so_luong` bộ tham số (list[dict]).

    Đây là toàn bộ 'bộ dò' của bản Lite: bốc ngẫu nhiên phẳng, KHÔNG học từ các
    kết quả trước. Seed cố định để tái lập được.
    """
    rng = random.Random(seed)
    return [_sinh_mot_bo(khong_gian, rng) for _ in range(max(1, int(so_luong)))]


def _duyet_tim_tot_nhat(danh_sach_bo, cham_diem, progress_cb=None, should_stop=None, tong=None):
    """Vòng lặp PHẲNG: chấm điểm từng bộ tham số, giữ bộ điểm cao nhất.

    cham_diem(bo, so_tt) -> float (càng cao càng tốt).
    Trả (best_bo, best_value, lich_su); lich_su = list[{number, params, value}]
    để dashboard vẽ lại tiến trình — thay cho danh sách trial cũ.
    """
    best_bo, best_value = {}, -float('inf')
    lich_su = []
    tong = tong or len(danh_sach_bo)
    for i, bo in enumerate(danh_sach_bo):
        if should_stop is not None:
            try:
                if should_stop():
                    break
            except Exception:
                pass
        try:
            diem = cham_diem(bo, i)
        except Exception:
            continue
        lich_su.append({'number': i, 'params': bo, 'value': diem})
        if diem > best_value:
            best_value, best_bo = diem, bo
        if progress_cb is not None:
            try:
                progress_cb(i + 1, tong, best_value)
            except Exception:
                pass
    return best_bo, best_value, lich_su


try:
    from utils.log import logger, banner_khoi_dong
    from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
    from lay_du_lieu.lay_ohlcv import tai_du_lieu_lich_su
    from utils.ham_tien_ich import gop_va_dong_bo_data, gop_va_dong_bo_data_polars
    from utils.kho_du_lieu import tao_run_id
    import chien_luoc.optimizer.stoploss_takeprofit as SLTP
    from chien_luoc.optimizer.don_bay import them_don_bay_dong
    from chien_luoc.optimizer.loc_tin_hieu import chuan_hoa_va_loc_tin_hieu
    from toi_uu_hoa.phan_loai_chi_bao import detect_indicator_type, generate_generic_signals, ket_hop_tin_hieu_spec, is_centered_oscillator, get_cols_by_type
    from toi_uu_hoa.dong_co_backtest import (
        run_fast_backtest, tinh_sharpe_ratio, tinh_da_chi_so, xay_dung_duong_cong,
        MIN_TRADES_TIN_CAY, MIN_DAYS_TIN_CAY,
    )
    from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY
except ImportError as e:
    print(f'[ERROR] Lỗi Import trong bo_dieu_phoi.py: {e}')
    sys.exit(1)

                                                                                         
                                                                                     
_COOLDOWN_NEN = int((lay_cau_hinh_giao_dich() or {}).get("cooldown_nen", 5))
_COOLDOWN_NEN = int((lay_cau_hinh_giao_dich() or {}).get("cooldown_nen", 5))

def _lay_khoang_sl_rr():
    """Đọc khoảng dò base_sl / rr (do chip 'SL/TP động' đặt) từ quan_ly_chien_luoc.
    Trả về ((sl_lo, sl_hi), (rr_lo, rr_hi)); fallback về mặc định cũ nếu thiếu."""
    sl, rr = (1.0, 5.0), (1.2, 4.0)
    try:
        import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        sl = tuple(getattr(Q, "SL_RANGE", sl)) or sl
        rr = tuple(getattr(Q, "RR_RANGE", rr)) or rr
    except Exception:
        pass
                                                                      
    sl_lo, sl_hi = sorted((float(sl[0]), float(sl[1])))
    rr_lo, rr_hi = sorted((float(rr[0]), float(rr[1])))
    return (sl_lo, sl_hi), (rr_lo, rr_hi)


def _tham_so_mo_dun():
    """Tham số chi tiết của các chip (khung ATR, đòn bẩy gốc/trần) để LƯU vào file
    chiến lược → bar-to-bar/live & vectorized đọc lại đồng bộ. Thiếu = mặc định cũ."""
    out = {"sl_tp_time_frame": None, "don_bay_goc": None, "max_leverage": 50, "don_bay_tf": "15m",
           "regime_cho_phep": None}
    try:
        import chien_luoc.quan_ly_chien_luoc_vectorized as Q
        out["sl_tp_time_frame"] = getattr(Q, "SL_TP_TIME_FRAME", None)
        out["don_bay_goc"] = int(getattr(Q, "DON_BAY_GOC", getattr(Q, "DON_BAY_CO_DINH", 5)))
        out["max_leverage"] = int(getattr(Q, "MAX_LEVERAGE", 50))
        out["don_bay_tf"] = getattr(Q, "DON_BAY_TF", "15m")
    except Exception:
        pass
    try:
        from chien_luoc.optimizer.trang_thai_thi_truong import lay_regime_cho_phep
        out["regime_cho_phep"] = lay_regime_cho_phep()
    except Exception:
        pass
    return out
                                                         
IS_RATIO = 0.7

def _chay_backtest_cho_params(indicator_func, indicator_params, htf, ltf, target_type,
                               suggested_thresholds, base_sl, rr, datasets, VON_BAN_DAU, PHI_GD,
                               SLIPPAGE, VON_MOI_LENH, DON_BAY, start_filter, end_filter, n_trials=1):
    """
    Chạy thử nghiệm chiến lược (backtest) cho một bộ tham số cụ thể trên khoảng thời gian định sẵn.

    Quy trình thực hiện:
    1. Tính toán giá trị chỉ báo trên khung thời gian thấp (LTF) và cao (HTF).
    2. Gộp và đồng bộ hóa dữ liệu đa khung về khung cơ sở 1m để khớp lệnh.
    3. Lọc dữ liệu theo mốc thời gian yêu cầu.
    4. Áp dụng bộ lọc xu hướng từ khung thời gian cao (HTF Filter):
       - Oscillator: Chỉ LONG khi chỉ báo HTF vượt ngưỡng, SHORT ngược lại.
       - Channel/Trend: Chỉ LONG khi giá trên midpoint/MA của HTF.
    5. Thiết lập SL/TP động, thêm đòn bẩy động, và chạy khớp lệnh candle-loop.
    6. Tính toán Sharpe Ratio và tập đa chỉ số quant.
    """
    all_trades = []
    
                                                                                   
    import polars as pl
    for symbol, data in datasets.items():
        df_1m = data['df_1m']
        tf_map = data['timeframe_map']
        df_ltf = tf_map[ltf]
        df_htf = tf_map[htf]

                                          
        df_calc_ltf = indicator_func(df_ltf.clone(), ltf, **indicator_params)
        new_cols_ltf = [c for c in df_calc_ltf.columns if c not in df_ltf.columns]
        target_col_ltf = get_cols_by_type(new_cols_ltf, target_type)
        if target_col_ltf is not None:
            if target_type == 'channel':
                target_col_ltf = (
                    target_col_ltf[0].lower() if target_col_ltf[0] else None,
                    target_col_ltf[1].lower() if target_col_ltf[1] else None
                )
            else:
                target_col_ltf = target_col_ltf.lower()

        dfs_dict = {'1m': df_1m, ltf: df_calc_ltf}
        target_col_htf = None
        
                                                                
        if htf != ltf:
            df_calc_htf = indicator_func(df_htf.clone(), htf, **indicator_params)
            dfs_dict[htf] = df_calc_htf
            new_cols_htf = [c for c in df_calc_htf.columns if c not in df_htf.columns]
            target_col_htf = get_cols_by_type(new_cols_htf, target_type)
            if target_col_htf is not None:
                if target_type == 'channel':
                    target_col_htf = (
                        target_col_htf[0].lower() if target_col_htf[0] else None,
                        target_col_htf[1].lower() if target_col_htf[1] else None
                    )
                else:
                    target_col_htf = target_col_htf.lower()

                                    
        df_merged = gop_va_dong_bo_data_polars(dfs_dict)
        if df_merged is None:
            continue
                                                                                     
        df_signal = generate_generic_signals(df_merged, target_type, target_col_ltf, suggested_thresholds)
        
                                                                                          
        if htf != ltf and target_col_htf is not None:
            if target_type == 'oscillator':
                htf_col = target_col_htf
                if htf_col in df_signal.columns:
                    htf_filter_val = suggested_thresholds.get('htf_filter_val', 50)
                    df_signal = df_signal.with_columns(
                        pl.when((pl.col("signal") == 1) & (pl.col(htf_col) > htf_filter_val)).then(1)
                        .when((pl.col("signal") == -1) & (pl.col(htf_col) <= htf_filter_val)).then(-1)
                        .otherwise(0)
                        .alias("signal")
                    )
            elif target_type == 'channel':
                col_upper_htf, col_lower_htf = target_col_htf
                if col_upper_htf in df_signal.columns and col_lower_htf in df_signal.columns:
                    htf_middle = (pl.col(col_upper_htf) + pl.col(col_lower_htf)) / 2
                    df_signal = df_signal.with_columns(
                        pl.when((pl.col("signal") == 1) & (pl.col("close") > htf_middle)).then(1)
                        .when((pl.col("signal") == -1) & (pl.col("close") <= htf_middle)).then(-1)
                        .otherwise(0)
                        .alias("signal")
                    )
            elif target_type == 'trend':
                htf_col = target_col_htf
                if htf_col in df_signal.columns:
                    df_signal = df_signal.with_columns(
                        pl.when((pl.col("signal") == 1) & (pl.col("close") > pl.col(htf_col))).then(1)
                        .when((pl.col("signal") == -1) & (pl.col("close") <= pl.col(htf_col))).then(-1)
                        .otherwise(0)
                        .alias("signal")
                    )

                                                                                     
        df_signal = df_signal.filter(
            (pl.col("timestamp") >= start_filter) & (pl.col("timestamp") <= end_filter)
        )
        if df_signal.height < 50:
            continue

                                                                               
        df_signal = df_signal.with_columns(
            pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
        )

                                                                                        
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
            dung_regime_ml = getattr(Q, "DUNG_REGIME_MAC_DINH", False)
        except ImportError:
            dung_regime_ml = False

        df_signal = chuan_hoa_va_loc_tin_hieu(df_signal, dung_regime_ml=dung_regime_ml)
                                                                                                     
        df_signal = SLTP.them_sl_tp(df_signal, base_sl=base_sl, rr=rr)
                                      
        df_signal = them_don_bay_dong(df_signal, don_bay_goc=DON_BAY)
        
                                        
        trades, _ = run_fast_backtest(df_signal, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY, cooldown_nen=_COOLDOWN_NEN)
        all_trades.extend(trades)

    start_str = start_filter.strftime('%Y-%m-%d') if isinstance(start_filter, datetime) else str(start_filter)
    end_str = end_filter.strftime('%Y-%m-%d') if isinstance(end_filter, datetime) else str(end_filter)
    
                                                                                                                     
    sharpe = tinh_sharpe_ratio(all_trades, start_date=start_str, end_date=end_str, von_ban_dau=VON_BAN_DAU)
    metrics = tinh_da_chi_so(all_trades, VON_BAN_DAU, start_date=start_str, end_date=end_str, n_trials=n_trials)
    return (all_trades, sharpe, metrics)


def run_indicator_optimization(indicator_func, n_trials=60, preloaded_datasets=None, silent=False, target_timeframe=None, so_doan_oos=4):
    """
    Hàm lõi chạy dò tham số cho một chỉ báo kỹ thuật trên các khung thời gian chính.
    Áp dụng phương pháp Walk-Forward Validation (IS 70% / OOS 30%) để hạn chế tối đa Overfitting.

    Các khung thời gian chạy tối ưu hóa: 1m, 3m, 5m, 15m, 30m, 1h, 4h.
    Nếu truyền `target_timeframe`, chỉ chạy tối ưu hóa riêng cho khung thời gian đó
    (các khung lớn hơn vẫn khả dụng để làm bộ lọc HTF).
    """
    config_trading = lay_cau_hinh_giao_dich()
    config_backtest = lay_cau_hinh_ao()

    func_name = indicator_func.__name__
    target_type, target_col_base = detect_indicator_type(indicator_func, target_timeframe or '1h')

                                                            
    VON_BAN_DAU = float(config_backtest.get('so_du_ban_dau', 10000))
    PHI_GD = float(config_backtest.get('phi_giao_dich', 0.001))
    SLIPPAGE = float(config_backtest.get('do_truot_gia', 0.001))
    START_DATE = config_backtest.get('ngay_bat_dau', '2025-01-01')
    END_DATE = config_backtest.get('ngay_ket_thuc', '2025-01-31')
    DON_BAY = int(config_trading.get('don_bay', 1))
    DS_SYMBOL = config_trading.get('cap_giao_dich', [])
    VON_MOI_LENH = float(config_trading.get('von_moi_lenh_usdt', 100))

    if not DS_SYMBOL:
        print('[ERROR] Không tìm thấy cặp giao dịch nào trong config/cau_hinh_giao_dich.yaml')
        sys.exit(1)

                                                                
    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
    total_days = (end_dt - start_dt).days
    is_end_dt = start_dt + timedelta(days=int(total_days * IS_RATIO))
    oos_start_dt = is_end_dt + timedelta(days=1)
    
    IS_START = START_DATE
    IS_END = is_end_dt.strftime('%Y-%m-%d')
    OOS_START = oos_start_dt.strftime('%Y-%m-%d')
    OOS_END = END_DATE

    run_id = tao_run_id()
    ALL_TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']

                                                                 
    if target_timeframe is None:
        raise ValueError("Bản Lite chỉ hỗ trợ tối ưu hóa đơn khung (Single Timeframe). Vui lòng chọn và truyền target_timeframe cụ thể.")
    if target_timeframe not in ALL_TIMEFRAMES:
        print(f'[ERROR] Khung thời gian "{target_timeframe}" không hợp lệ. Các khung hỗ trợ: {", ".join(ALL_TIMEFRAMES)}')
        sys.exit(1)
    TIMEFRAMES = [target_timeframe]

    n_trials_per_tf = max(5, n_trials // len(TIMEFRAMES))

    if not silent:
        banner_title = ' SINGLE-TIMEFRAME OPTIMIZER (Walk-Forward)' if target_timeframe else ' ALL-TIMEFRAMES OPTIMIZER (Walk-Forward)'
        banner_khoi_dong(banner_title, [
            ('Chỉ báo mục tiêu', f'{func_name} ({target_type.upper()})'),
            ('Cột gốc nhận diện', str(target_col_base)),
            ('In-Sample (IS - 70%)', f'{IS_START}  ->  {IS_END}  ({int(total_days * IS_RATIO)} ngày)'),
            ('Out-of-Sample (OOS - 30%)', f'{OOS_START}  ->  {OOS_END}  ({total_days - int(total_days * IS_RATIO)} ngày)'),
            ('Vốn ban đầu / Symbol', f'{VON_BAN_DAU:,.0f} USDT'),
            ('Danh sách Symbols', ', '.join(DS_SYMBOL)),
            ('Trials / Khung', f'{n_trials_per_tf} trials'),
            ('Run ID', run_id)
        ])

                                                                                  
    if preloaded_datasets is not None:
        datasets = preloaded_datasets
    else:
        if not silent:
            print('[INFO] Bước 1: Đang nạp dữ liệu đa khung vào RAM (Pre-loading)...')
        datasets = {}
        for symbol in DS_SYMBOL:
            df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)
            if df_goc is None or df_goc.is_empty():
                continue
            df_1m = df_goc
            timeframe_map = {
                '1m': df_1m, '3m': df_1m, '5m': df_1m, '15m': df_1m,
                '30m': df_1m, '1h': df_1m, '4h': df_1m, '1d': df_1m
            }
            datasets[symbol] = {'df_1m': df_1m, 'timeframe_map': timeframe_map}

    if not datasets:
        print('[ERROR] Không nạp được dữ liệu của bất kỳ symbol nào!')
        sys.exit(1)

    if not silent:
        print('[SUCCESS] Đã nạp dữ liệu vào RAM thành công.')
        print(f'[INFO] Bước 2: Bắt đầu dò tham số lần lượt cho {len(TIMEFRAMES)} khung thời gian...')

    timeframe_results = {}
    for ltf in TIMEFRAMES:
        if not silent:
            print(f'\n=======> [TỐI ƯU HÓA KHUNG THỜI GIAN: {ltf.upper()}] Chạy {n_trials_per_tf} bộ tham số (IS: {IS_START} -> {IS_END})...')

                                                                       
        allowed_htfs = ALL_TIMEFRAMES[ALL_TIMEFRAMES.index(ltf):]

                                                                                  
        khong_gian = _khong_gian_chi_bao(indicator_func, target_type, target_col_base, allowed_htfs)
        danh_sach_bo = _sinh_danh_sach_bo(khong_gian, n_trials_per_tf, seed=42)

        def _cham_diem(bo, so_tt, _ltf=ltf):
            indicator_params = {k[4:]: v for k, v in bo.items() if k.startswith('ind_')}
            thresholds = {k[5:]: v for k, v in bo.items() if k.startswith('trig_')}
            htf = bo.get('htf', _ltf)
            base_sl = bo.get('risk_base_sl', 2.0)
            rr = bo.get('risk_rr', 2.0)
            _, sharpe, _ = _chay_backtest_cho_params(
                indicator_func, indicator_params, htf, _ltf, target_type,
                thresholds, base_sl, rr, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE,
                VON_MOI_LENH, DON_BAY, start_filter=start_dt, end_filter=is_end_dt
            )
            if not silent:
                ind_log = ', '.join([f"{k.upper()}: {v}" for k, v in indicator_params.items()])
                trig_log = ', '.join([f"{k.upper()}: {v}" for k, v in thresholds.items()])
                trig_str = f' | {trig_log}' if trig_log else ''
                print(f'  [{func_name.upper()} - {_ltf} - Bộ {so_tt:03d}] IS Sharpe: {sharpe:+.4f} | HTF: {htf} | {ind_log}{trig_str} | SL: {base_sl}% | RR: {rr}')
            return sharpe

                                                             
        best_bo, _, _ = _duyet_tim_tot_nhat(danh_sach_bo, _cham_diem, tong=n_trials_per_tf)

                                                                         
        ind_p = {k[4:]: v for k, v in best_bo.items() if k.startswith('ind_')}
        thresh = {k[5:]: v for k, v in best_bo.items() if k.startswith('trig_')}
        best_htf = best_bo.get('htf', ltf)
        best_sl = best_bo.get('risk_base_sl', 2.0)
        best_rr = best_bo.get('risk_rr', 2.0)
        best_params = dict(best_bo)
        best_params['ltf'] = ltf
        best_params['htf'] = best_htf

                                       
        _, is_sharpe, is_metrics = _chay_backtest_cho_params(
            indicator_func, ind_p, best_htf, ltf, target_type, thresh,
            best_sl, best_rr, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
            start_filter=start_dt, end_filter=is_end_dt, n_trials=n_trials_per_tf
        )
        
                                                                                                  
                                                                                       
        _, oos_sharpe, oos_metrics = _chay_backtest_cho_params(
            indicator_func, ind_p, best_htf, ltf, target_type, thresh,
            best_sl, best_rr, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
            start_filter=oos_start_dt, end_filter=end_dt, n_trials=1
        )
        
                                                      
        oos_is_ratio = oos_sharpe / is_sharpe if is_sharpe > 0 else 0.0

                                                                                        
        oos_folds, wf_summary = [], {}

        if not silent:
            print(
                f"  >> [BEST {ltf.upper()}] IS Sharpe: {is_sharpe:+.4f} | OOS Sharpe: {oos_sharpe:+.4f} | "
                f"OOS/IS Ratio: {oos_is_ratio:.2f} | OOS WinRate: {oos_metrics['win_rate']:.1f}% | "
                f"OOS MaxDD: {oos_metrics['max_drawdown_pct']:.2f}% | "
                f"IS DSR: {is_metrics['deflated_sharpe_ratio'] * 100:.1f}% | "
                f"OOS DSR: {oos_metrics['deflated_sharpe_ratio'] * 100:.1f}%"
            )
            if wf_summary.get('so_doan_co_du_lieu'):
                print(
                    f"     [WALK-FORWARD] {wf_summary['so_doan_co_du_lieu']}/{wf_summary['so_doan']} đoạn có dữ liệu | "
                    f"% đoạn dương: {wf_summary['ty_le_doan_duong'] * 100:.0f}% | Sharpe TB: {wf_summary['sharpe_trung_binh']}"
                )

        timeframe_results[ltf] = {
            'is_metrics': is_metrics,
            'oos_metrics': oos_metrics,
            'oos_is_ratio': oos_is_ratio,
            'oos_folds': oos_folds,
            'wf_summary': wf_summary,
            'optimum_parameters': best_params
        }

                                        
    if not silent:
        out_path = os.path.join(PROJECT_ROOT, 'du_lieu', 'ket_qua_uu_hoa', 'ket_qua_toi_uu_don.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_id': run_id,
                'ngay_chay': time.strftime('%Y-%m-%d %H:%M:%S'),
                'target_indicator': func_name,
                'target_type': target_type,
                'symbols': DS_SYMBOL,
                'is_period': f'{IS_START} -> {IS_END}',
                'oos_period': f'{OOS_START} -> {OOS_END}',
                'timeframe_results': timeframe_results
            }, f, indent=4, ensure_ascii=False)

                                                  
        print('\n=============================================================================================================================')
        print(f'     IS: {IS_START} -> {IS_END}  |  OOS: {OOS_START} -> {OOS_END}')
        print('=============================================================================================================================')
        print(f"{'Khung':<6}{'HTF':<6}{'IS Sharpe':>11}{'IS DSR':>9}{'OOS Sharpe':>12}{'OOS DSR':>9}{'OOS/IS':>9}{'OOS MaxDD':>11}{'OOS WinR':>10}{'OOS PF':>9}{'Trades':>8}")
        for tf in TIMEFRAMES:
            res = timeframe_results.get(tf)
            if not res:
                continue
            ism = res['is_metrics']
            oom = res['oos_metrics']
            htf_val = res['optimum_parameters'].get('htf', tf)
            is_sh = ism['sharpe_ratio']
            oos_sh = oom['sharpe_ratio']
            ratio_val = res['oos_is_ratio']
            ratio_str = f'{ratio_val:>8.2f}' if is_sh > 0 else '    N/A'
            print(
                f"{tf:<6}{htf_val:<6}{is_sh:>+10.4f} {ism['deflated_sharpe_ratio'] * 100:>7.1f}% "
                f"{oos_sh:>+11.4f} {oom['deflated_sharpe_ratio'] * 100:>7.1f}% {ratio_str} "
                f"{oom['max_drawdown_pct']:>10.2f}% {oom['win_rate']:>8.1f}% "
                f"{oom['profit_factor']:>8.2f} {oom['total_trades']:>7d}"
            )
        print('=============================================================================================================================')
        print('[SUCCESS] Kết quả chi tiết đã được lưu tại: du_lieu/ket_qua_uu_hoa/ket_qua_toi_uu_don.json\n')

    return timeframe_results


def run_all_indicators_comparison(n_trials=10):
    raise NotImplementedError("Bản Lite không hỗ trợ quét so sánh toàn bộ chỉ báo (All Indicators Comparison). "
                              "Vui lòng nâng cấp lên bản Premium để sử dụng tính năng này.")


def _chay_backtest_combo(combo_specs, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE,
                          VON_MOI_LENH, DON_BAY, start_filter, end_filter,
                          base_sl, rr, n_trials=1, logic='and', persistence=1):
    """
    Backtest MỘT chiến lược kết hợp nhiều chỉ báo, mỗi chỉ báo gắn 1 khung riêng.

    Quy trình:
    1. Gom các chỉ báo theo khung thời gian (cho phép nhiều chỉ báo cùng 1 khung),
       tính giá trị từng chỉ báo trên khung của nó. Cột đầu ra được đổi tên duy
       nhất theo chỉ số `s{idx}_...` để tránh trùng tên khi gộp đa khung.
    2. Gộp & đồng bộ tất cả về khung cơ sở 1m (merge_asof backward → không lookahead).
    3. Sinh tín hiệu riêng cho từng chỉ báo rồi KẾT HỢP bằng logic AND:
       - LONG khi TẤT CẢ chỉ báo cùng cho tín hiệu LONG.
       - SHORT khi TẤT CẢ chỉ báo cùng cho tín hiệu SHORT.
    4. Gắn SL/TP động + đòn bẩy động, chạy khớp lệnh, tính Sharpe & đa chỉ số.
    """
    all_trades = []
    import polars as pl
    for symbol, data in datasets.items():
        df_1m = data['df_1m']
        tf_map = data['timeframe_map']

                                          
        specs_by_tf = {}
        for idx, spec in enumerate(combo_specs):
            specs_by_tf.setdefault(spec['tf'], []).append((idx, spec))

        dfs_dict = {'1m': df_1m}
        spec_target = {}                                            

        for tf, idx_specs in specs_by_tf.items():
            if tf not in tf_map:
                continue
            df_work = tf_map[tf].clone()
            for idx, spec in idx_specs:
                before_cols = set(df_work.columns)
                df_work = spec['func'](df_work, tf, **spec['params'])
                new_cols = [c for c in df_work.columns if c not in before_cols]
                if not new_cols:
                    spec_target[idx] = (spec['type'], None)
                    continue
                target_col = get_cols_by_type(new_cols, spec['type'])
                                                                 
                df_work = df_work.rename({c: f's{idx}_{c}' for c in new_cols})
                if spec['type'] == 'channel':
                    col_up, col_lo = target_col if isinstance(target_col, tuple) else (target_col, target_col)
                    tcol = (
                        f's{idx}_{col_up}'.lower() if col_up else None,
                        f's{idx}_{col_lo}'.lower() if col_lo else None,
                    )
                else:
                    tcol = f's{idx}_{target_col}'.lower() if target_col else None
                spec_target[idx] = (spec['type'], tcol)
            dfs_dict[tf] = df_work

                                        
        df_merged = gop_va_dong_bo_data_polars(dfs_dict)
        if df_merged is None:
            continue

                                                                                           
                                                                                          
                                                                                        
         
                                                                                                  
                                                                                                
        resolved_specs = []
        for idx, spec in enumerate(combo_specs):
            t_type, tcol = spec_target.get(idx, (spec['type'], None))
            resolved_specs.append({
                't_type': t_type,
                'tcol': tcol,
                'thresholds': spec['thresholds'],
                'role': spec.get('role', 'trigger'),
            })

        df_merged, co_trigger = ket_hop_tin_hieu_spec(
            df_merged, resolved_specs, logic=logic, persistence=persistence
        )
        if not co_trigger:
            continue                                                 

                                                                 
        df_merged = df_merged.filter(
            (pl.col("timestamp") >= start_filter) & (pl.col("timestamp") <= end_filter)
        )
        if df_merged.height < 50:
            continue

        df_merged = df_merged.with_columns(
            pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
        )

                                                                                        
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
            dung_regime_ml = getattr(Q, "DUNG_REGIME_MAC_DINH", False)
        except ImportError:
            dung_regime_ml = False

        df_merged = chuan_hoa_va_loc_tin_hieu(df_merged, dung_regime_ml=dung_regime_ml)

                                                                                         
                                                                                           
        df_merged = SLTP.them_sl_tp(df_merged, base_sl=base_sl, rr=rr)
        df_merged = them_don_bay_dong(df_merged, don_bay_goc=DON_BAY)

        trades, _ = run_fast_backtest(df_merged, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY, cooldown_nen=_COOLDOWN_NEN)
        all_trades.extend(trades)

    start_str = start_filter.strftime('%Y-%m-%d') if isinstance(start_filter, datetime) else str(start_filter)
    end_str = end_filter.strftime('%Y-%m-%d') if isinstance(end_filter, datetime) else str(end_filter)

    sharpe = tinh_sharpe_ratio(all_trades, start_date=start_str, end_date=end_str, von_ban_dau=VON_BAN_DAU)
    metrics = tinh_da_chi_so(all_trades, VON_BAN_DAU, start_date=start_str, end_date=end_str, n_trials=n_trials)
    return (all_trades, sharpe, metrics)

                                                                      
_AUTO_SKIP_PARAMS = {'df', 'time_frame', 'volume_luy_ke'}


def _contract_group_a_specs(indicator_func):
    """Tự suy danh sách spec GROUP A từ chữ ký hàm chỉ báo.

    Trả list[{name, kind, low, high}] (có thể rỗng nếu chỉ báo không có tham số số học).
    KHÔNG bao giờ trả None → optimizer luôn dùng đường auto này thay cho heuristic 5-tên cũ.
    """
    specs = []
    for name, p in inspect.signature(indicator_func).parameters.items():
        if name in _AUTO_SKIP_PARAMS:
            continue
        default = p.default
        if default is inspect.Parameter.empty:
            continue
                                                                              
        if isinstance(default, bool) or not isinstance(default, (int, float)):
            continue
        if default <= 0:
            continue

        if isinstance(default, int):
            lo = max(2, int(default * 0.5))
            hi = max(lo + 2, int(default * 2))
            specs.append({'name': name, 'kind': 'int', 'low': lo, 'high': hi})
        else:         
            if default < 1.0:
                                                                                           
                lo = max(1e-4, round(default * 0.5, 6))
                hi = min(0.999, round(default * 2.0, 6))
            else:
                lo = round(default * 0.5, 4)
                hi = round(default * 2.0, 4)
            if hi <= lo:
                hi = lo + abs(lo) * 0.5 + 1e-4
            specs.append({'name': name, 'kind': 'float', 'low': lo, 'high': hi})

    return specs


def _khong_gian_chi_bao(indicator_func, target_type, target_col_base, allowed_htfs):
    """Không gian tìm kiếm cho 1 chỉ báo đơn (dạng dữ liệu, KHÔNG Trial động).

    Gồm: tham số GROUP A (suy quanh default từ chữ ký hàm) tiền tố `ind_`, khung
    lọc HTF, ngưỡng kích hoạt `trig_` theo loại chỉ báo, và SL/RR `risk_`.
    """
    kg = {}
    for s in _contract_group_a_specs(indicator_func):
        ten = f"ind_{s['name']}"
        if s['kind'] == 'int':
            kg[ten] = ('int', int(s['low']), int(s['high']))
        else:
            kg[ten] = ('float', float(s['low']), float(s['high']), None)

    kg['htf'] = ('cat', list(allowed_htfs))

    if target_type == 'oscillator':
        if is_centered_oscillator(target_col_base if isinstance(target_col_base, str) else ''):
            kg['trig_oversold'] = ('float', -50.0, -1.0, None)
            kg['trig_overbought'] = ('float', 1.0, 50.0, None)
            kg['trig_htf_filter_val'] = ('float', -50.0, 50.0, None)
        else:
            kg['trig_oversold'] = ('int', 10, 45)
            kg['trig_overbought'] = ('int', 55, 90)
            kg['trig_htf_filter_val'] = ('int', 20, 80)
    elif target_type == 'channel':
        kg['trig_lower_mult'] = ('float', 0.95, 1.05, 0.01)
        kg['trig_upper_mult'] = ('float', 0.95, 1.05, 0.01)
    elif target_type == 'trend':
        kg['trig_dev_below'] = ('float', 0.5, 5.0, 0.1)
        kg['trig_dev_above'] = ('float', 0.5, 5.0, 0.1)
    elif target_type == 'volume':
        kg['trig_vol_enter'] = ('float', 1.0, 3.0, 0.1)
        kg['trig_vol_exit'] = ('float', 0.4, 1.0, 0.1)

    (sl_lo, sl_hi), (rr_lo, rr_hi) = _lay_khoang_sl_rr()
    kg['risk_base_sl'] = ('float', sl_lo, sl_hi, 0.1)
    kg['risk_rr'] = ('float', rr_lo, rr_hi, 0.1)
    return kg


                                                                                     
_TEN_NGUONG = {'oversold', 'overbought', 'lower_mult', 'upper_mult',
               'dev_below', 'dev_above', 'vol_enter', 'vol_exit'}


def _khong_gian_combo(combo_meta):
    """Không gian tìm kiếm cho chiến lược KẾT HỢP nhiều chỉ báo.

    Mỗi chỉ báo idx có tham số + ngưỡng gắn tiền tố `s{idx}_`; thêm SL/RR chung.
    """
    kg = {}
    for idx, (key, tf, func, t_type, col_base, role) in enumerate(combo_meta):
        for s in _contract_group_a_specs(func):
            ten = f"s{idx}_{s['name']}"
            if s['kind'] == 'int':
                kg[ten] = ('int', int(s['low']), int(s['high']))
            else:
                kg[ten] = ('float', float(s['low']), float(s['high']), None)
        if t_type == 'oscillator':
            if is_centered_oscillator(col_base):
                kg[f's{idx}_oversold'] = ('float', -50.0, -1.0, None)
                kg[f's{idx}_overbought'] = ('float', 1.0, 50.0, None)
            else:
                kg[f's{idx}_oversold'] = ('int', 10, 45)
                kg[f's{idx}_overbought'] = ('int', 55, 90)
        elif t_type == 'channel':
            kg[f's{idx}_lower_mult'] = ('float', 0.95, 1.05, 0.01)
            kg[f's{idx}_upper_mult'] = ('float', 0.95, 1.05, 0.01)
        elif t_type == 'trend':
            kg[f's{idx}_dev_below'] = ('float', 0.5, 5.0, 0.1)
            kg[f's{idx}_dev_above'] = ('float', 0.5, 5.0, 0.1)
        elif t_type == 'volume':
            kg[f's{idx}_vol_enter'] = ('float', 1.0, 3.0, 0.1)
            kg[f's{idx}_vol_exit'] = ('float', 0.4, 1.0, 0.1)

    (sl_lo, sl_hi), (rr_lo, rr_hi) = _lay_khoang_sl_rr()
    kg['risk_base_sl'] = ('float', sl_lo, sl_hi, 0.1)
    kg['risk_rr'] = ('float', rr_lo, rr_hi, 0.1)
    return kg


def _tach_bo_combo(bo, combo_meta):
    """Tách 1 bộ tham số phẳng thành (specs theo từng chỉ báo, base_sl, rr).

    specs là list dict {func, tf, type, params, thresholds, role} cho _chay_backtest_combo.
    """
    specs = []
    for idx, (key, tf, func, t_type, col_base, role) in enumerate(combo_meta):
        prefix = f's{idx}_'
        params, thresholds = {}, {}
        for k, v in bo.items():
            if not k.startswith(prefix):
                continue
            ten = k[len(prefix):]
            if ten in _TEN_NGUONG:
                thresholds[ten] = v
            else:
                params[ten] = v
        specs.append({'func': func, 'tf': tf, 'type': t_type,
                      'params': params, 'thresholds': thresholds, 'role': role})
    return specs, bo.get('risk_base_sl', 2.0), bo.get('risk_rr', 2.0)
                                                                                   
TINH_NANG_NANG_CAP = False

def _yeu_cau_nang_cap(ten_tinh_nang):
    """Chặn tính năng thuộc bản nâng cấp nếu chưa mở khóa."""
    if not TINH_NANG_NANG_CAP:
        raise RuntimeError(
            f"{ten_tinh_nang} thuộc bản nâng cấp, không mở cho cộng đồng. "
            "Vui lòng liên hệ tác giả để được cấp quyền sử dụng."
            "Nếu bạn muốn dùng, hãy đặt TINH_NANG_NANG_CAP = True trong mã nguồn để mở khóa."
            "Lưu ý: Bạn có thề dùng nhưng độ chính xác không bằng khi có licente nâng cao"
        )


def run_combo_optimization(combo, n_trials=100, preloaded_datasets=None, silent=False, progress_cb=None, objective_metric='sharpe', so_doan_oos=4, logic='and', persistence=1, should_stop=None, override_symbols=None, override_start=None, override_end=None):
    """
    Tối ưu hóa MỘT chiến lược KẾT HỢP nhiều chỉ báo đa khung thời gian.

    Tìm đồng thời bộ tham số cho tất cả chỉ báo (mỗi chỉ báo gắn 1 khung riêng)
    sao cho tín hiệu kết hợp bằng logic AND đạt Sharpe cao nhất trên In-Sample,
    sau đó kiểm định mù trên Out-of-Sample (Walk-Forward) + tính DSR.

    Args:
        combo: list các dict ``{'key': <tên_chỉ_báo>, 'tf': <khung>}``.
               Ví dụ: ``[{'key': 'rsi', 'tf': '1m'}, {'key': 'macd', 'tf': '5m'}]``
        n_trials: tổng số trial  cho toàn chiến lược (không chia theo khung).
        preloaded_datasets: dữ liệu đa khung nạp sẵn (tuỳ chọn, để tăng tốc).
        silent: True → không in log / không ghi JSON (dùng khi gọi từ GUI).
        progress_cb: callback(done, total, best_sharpe) gọi sau mỗi trial (cho thanh
                     tiến độ GUI). Lỗi trong callback được bỏ qua an toàn.

    Returns:
        dict kết quả gồm combo, hiệu suất IS/OOS, OOS/IS ratio và best_params.
    """
                                                                                       
    if len({(item.get('key'), item.get('tf')) for item in (combo or [])}) > 1:
        _yeu_cau_nang_cap("Tối ưu Tổ hợp nhiều chỉ báo (Combo)")

    config_trading = lay_cau_hinh_giao_dich()
    config_backtest = lay_cau_hinh_ao()

                                                                                                 
    objective_metric = (objective_metric or 'sharpe').lower()
    if objective_metric not in ('sharpe', 'sortino', 'calmar'):
        objective_metric = 'sharpe'

                                                                              
    logic = (logic or 'and').lower()
    if logic not in ('and', 'or'):
        logic = 'and'
    try:
        persistence = max(1, int(persistence))
    except (TypeError, ValueError):
        persistence = 1

                                                                                   
    timeframes = set(item['tf'] for item in combo)
    if len(timeframes) > 1:
        raise ValueError("Bản Lite chỉ hỗ trợ tối ưu hóa trên cùng 1 khung thời gian (Single Timeframe). "
                         "Vui lòng cấu hình tất cả chỉ báo chạy cùng khung thời gian hoặc nâng cấp lên bản Premium để sử dụng tối ưu hóa Đa Khung Thời Gian (Multi-Timeframe).")
                         
                                                                           
    combo_meta = []                                                
    for item in combo:
        key = item['key']
        tf = item['tf']
        role = (item.get('role') or 'trigger').lower()
        if role not in ('trigger', 'filter'):
            role = 'trigger'
        func = INDICATOR_REGISTRY.get(key)
        if func is None:
            raise ValueError(f"Chỉ báo '{key}' không có trong INDICATOR_REGISTRY")
        t_type, col_base = detect_indicator_type(func, tf)
        combo_meta.append((key, tf, func, t_type, col_base, role))

    if not combo_meta:
        raise ValueError('Combo rỗng — cần ít nhất 1 chỉ báo.')
                                                               
    if not any(m[5] == 'trigger' for m in combo_meta):
        raise ValueError('Cần ít nhất 1 chỉ báo vai trò Trigger (Filter chỉ để lọc).')

    VON_BAN_DAU = float(config_backtest.get('so_du_ban_dau', 10000))
    PHI_GD = float(config_backtest.get('phi_giao_dich', 0.001))
    SLIPPAGE = float(config_backtest.get('do_truot_gia', 0.001))
    START_DATE = config_backtest.get('ngay_bat_dau', '2025-01-01')
    END_DATE = config_backtest.get('ngay_ket_thuc', '2025-01-31')
    DON_BAY = int(config_trading.get('don_bay', 1))
    DS_SYMBOL = config_trading.get('cap_giao_dich', [])
    VON_MOI_LENH = float(config_trading.get('von_moi_lenh_usdt', 100))

                                                                                            
    if override_symbols:
        DS_SYMBOL = list(override_symbols)
    if override_start:
        START_DATE = override_start
    if override_end:
        END_DATE = override_end

    if not DS_SYMBOL:
        print('[ERROR] Không tìm thấy cặp giao dịch nào trong config/cau_hinh_giao_dich.yaml')
        sys.exit(1)

                               
    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
    total_days = (end_dt - start_dt).days
    is_end_dt = start_dt + timedelta(days=int(total_days * IS_RATIO))
    oos_start_dt = is_end_dt + timedelta(days=1)
    IS_START, IS_END = START_DATE, is_end_dt.strftime('%Y-%m-%d')
    OOS_START, OOS_END = oos_start_dt.strftime('%Y-%m-%d'), END_DATE

    run_id = tao_run_id()
    combo_label = ' + '.join(f'{k}@{tf}' for k, tf, *_ in combo_meta)

    if not silent:
        banner_khoi_dong(' COMBO MULTI-INDICATOR OPTIMIZER (Walk-Forward)', [
            ('Chiến lược kết hợp', combo_label),
            ('Số chỉ báo', str(len(combo_meta))),
            ('Mục tiêu (Objective)', objective_metric.upper()),
            ('In-Sample (IS - 70%)', f'{IS_START}  ->  {IS_END}'),
            ('Out-of-Sample (OOS - 30%)', f'{OOS_START}  ->  {OOS_END}'),
            ('Vốn ban đầu / Symbol', f'{VON_BAN_DAU:,.0f} USDT'),
            ('Danh sách Symbols', ', '.join(DS_SYMBOL)),
            ('Tổng trials', f'{n_trials}'),
            ('Run ID', run_id),
        ])

                          
    if preloaded_datasets is not None:
        datasets = preloaded_datasets
    else:
        if not silent:
            print('[INFO] Bước 1: Đang nạp dữ liệu đa khung vào RAM (Pre-loading)...')
        datasets = {}
        for symbol in DS_SYMBOL:
            df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)
            if df_goc is None or df_goc.is_empty():
                continue
            df_1m = df_goc
            timeframe_map = {
                '1m': df_1m, '3m': df_1m, '5m': df_1m, '15m': df_1m,
                '30m': df_1m, '1h': df_1m, '4h': df_1m, '1d': df_1m
            }
            datasets[symbol] = {'df_1m': df_1m, 'timeframe_map': timeframe_map}

    if not datasets:
        print('[ERROR] Không nạp được dữ liệu của bất kỳ symbol nào!')
        sys.exit(1)

    if not silent:
        print(f'[INFO] Bước 2: Dò tham số chiến lược kết hợp ({n_trials} bộ)...')

                                                                              
    khong_gian = _khong_gian_combo(combo_meta)
    danh_sach_bo = _sinh_danh_sach_bo(khong_gian, n_trials, seed=42)

    def _cham_diem(bo, so_tt):
        specs, base_sl, rr = _tach_bo_combo(bo, combo_meta)
        _, sharpe, m = _chay_backtest_combo(
            specs, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
            start_filter=start_dt, end_filter=is_end_dt, base_sl=base_sl, rr=rr,
            logic=logic, persistence=persistence
        )
        if objective_metric == 'sortino':
            score = m['sortino_ratio']
        elif objective_metric == 'calmar':
            score = m['calmar_ratio'] if m['sharpe_ratio'] > -9.99 else -10.0
        else:
            score = sharpe
        if not silent:
            diem_txt = "KHÔNG ĐỦ LỆNH (<30)" if score <= -9.99 else f"{score:+.4f}"
            print(f'  [COMBO - Bộ {so_tt:03d}] IS {objective_metric}: {diem_txt} | SL: {base_sl}% | RR: {rr}')
        return score

                                                                            
    best_bo, _, lich_su = _duyet_tim_tot_nhat(
        danh_sach_bo, _cham_diem, progress_cb=progress_cb, should_stop=should_stop, tong=n_trials
    )

                                                
    best_specs, best_sl, best_rr = _tach_bo_combo(best_bo, combo_meta)
    best_params_out = {}
    for idx, (key, tf, func, t_type, col_base, role) in enumerate(combo_meta):
        sp = best_specs[idx]
        best_params_out[f's{idx}'] = {
            'key': key, 'tf': tf, 'type': t_type, 'role': role,
            'params': sp['params'], 'thresholds': sp['thresholds'],
        }
        from chien_luoc.quan_ly_chien_luoc_vectorized import DUNG_SL_TP_DONG, DUNG_DON_BAY_DONG, DUNG_REGIME_MAC_DINH
    _md = _tham_so_mo_dun()
    best_params_out['risk'] = {
        'base_sl': best_sl,
        'rr': best_rr,
        'dung_sl_tp_dong': DUNG_SL_TP_DONG,
        'dung_don_bay_dong': DUNG_DON_BAY_DONG,
        'sl_tp_time_frame': _md['sl_tp_time_frame'],
        'don_bay_goc': _md['don_bay_goc'],
        'max_leverage': _md['max_leverage'],
        'don_bay_tf': _md['don_bay_tf'],
    }
    best_params_out['logic'] = {
        'mode': logic,
        'persistence': persistence,
        'dung_ml': DUNG_REGIME_MAC_DINH,
        'regime_cho_phep': _md['regime_cho_phep'],
    }

                                                                                       
    is_trades, is_sharpe, is_metrics = _chay_backtest_combo(
        best_specs, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
        start_filter=start_dt, end_filter=is_end_dt, base_sl=best_sl, rr=best_rr, n_trials=n_trials,
        logic=logic, persistence=persistence
    )
                                                                                         
    oos_trades, oos_sharpe, oos_metrics = _chay_backtest_combo(
        best_specs, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
        start_filter=oos_start_dt, end_filter=end_dt, base_sl=best_sl, rr=best_rr, n_trials=1,
        logic=logic, persistence=persistence
    )
    oos_is_ratio = oos_sharpe / is_sharpe if is_sharpe > 0 else 0.0
                                                                                                                                                                                                
    phan_tich = {
        'is': xay_dung_duong_cong(is_trades, VON_BAN_DAU, IS_START, IS_END),
        'oos': xay_dung_duong_cong(oos_trades, VON_BAN_DAU, OOS_START, OOS_END),
    }
                                                                                                
                                                                                               
    for _seg in phan_tich.values():
        _seg['so_du'] = round(float(VON_BAN_DAU), 2)

                                                                                    
    oos_folds, wf_summary = [], {}                                                                                      
                                                                                        
    canh_bao = []
    is_days = max((is_end_dt - start_dt).days, 0)
    oos_days = max((end_dt - oos_start_dt).days, 0)
    is_tr = int(is_metrics.get('total_trades', 0))
    oos_tr = int(oos_metrics.get('total_trades', 0))

                                                                                                
    ngan = [t for t, d in (("IS", is_days), ("OOS", oos_days)) if d < MIN_DAYS_TIN_CAY]
    if ngan:
        chi_tiet = ", ".join(f"{t} {d}d" for t, d in (("IS", is_days), ("OOS", oos_days)) if d < MIN_DAYS_TIN_CAY)
        canh_bao.append(f"Khoảng dữ liệu quá ngắn ({chi_tiet}; cần ≥ {MIN_DAYS_TIN_CAY}d mỗi đoạn).")
    it = [t for t, n in (("IS", is_tr), ("OOS", oos_tr)) if n < MIN_TRADES_TIN_CAY]
    if it:
        chi_tiet = ", ".join(f"{t} {n} lệnh" for t, n in (("IS", is_tr), ("OOS", oos_tr)) if n < MIN_TRADES_TIN_CAY)
        canh_bao.append(f"Quá ít lệnh ({chi_tiet}; cần ≥ {MIN_TRADES_TIN_CAY}) → Sharpe/Sortino đoạn đó bị đánh dấu KHÔNG ĐỦ DỮ LIỆU (giá trị -10).")
    if canh_bao and not silent:
        for _c in canh_bao:
            print(f"  [CẢNH BÁO DỮ LIỆU] {_c}")

    trials_data = []
    for t in lich_su:
        val = t['value']
        if val != val or val in (float('inf'), float('-inf')):
            val = -10.0
        trials_data.append({'number': t['number'], 'params': t['params'], 'value': val})

    result = {
        'combo': [{'key': k, 'tf': tf, 'type': t, 'role': role} for k, tf, _f, t, _c, role in combo_meta],
        'combo_label': combo_label,
        'objective_metric': objective_metric,
        'logic': logic,
        'persistence': persistence,
        'canh_bao': canh_bao,
        'is_metrics': is_metrics,
        'oos_metrics': oos_metrics,
        'oos_is_ratio': oos_is_ratio,
        'oos_folds': oos_folds,
        'wf_summary': wf_summary,
        'best_params': best_params_out,
        'trials_data': trials_data,
        'phan_tich': phan_tich,
    }

    if not silent:
        import re
        def _slugify(s):
            return re.sub(r"[^0-9A-Za-z._@+-]+", "_", str(s)).strip("_").lower()
        combo_slug = _slugify(combo_label.replace('@', '_').replace('+', '_'))
        ts = time.strftime('%Y%m%d_%H%M%S')
        filename = f"{combo_slug}__{logic}_p{persistence}_{objective_metric}_{n_trials}t__{ts}.json"
        out_path = os.path.join(PROJECT_ROOT, 'du_lieu', 'history_uu_hoa', filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_id': run_id,
                'ngay_chay': time.strftime('%Y-%m-%d %H:%M:%S'),
                'symbols': DS_SYMBOL,
                'is_period': f'{IS_START} -> {IS_END}',
                'oos_period': f'{OOS_START} -> {OOS_END}',
                **result,
            }, f, indent=4, ensure_ascii=False)

        print('\n' + '=' * 110)
        print(f'  CHIẾN LƯỢC KẾT HỢP: {combo_label}')
        print('=' * 110)
        print(
            f"  IS Sharpe: {is_sharpe:+.4f} (DSR {is_metrics['deflated_sharpe_ratio'] * 100:.1f}%)  |  "
            f"OOS Sharpe: {oos_sharpe:+.4f} (DSR {oos_metrics['deflated_sharpe_ratio'] * 100:.1f}%)  |  "
            f"OOS/IS: {oos_is_ratio:.2f}"
        )
        print(
            f"  OOS WinRate: {oos_metrics['win_rate']:.1f}%  |  OOS MaxDD: {oos_metrics['max_drawdown_pct']:.2f}%  |  "
            f"OOS Profit Factor: {oos_metrics['profit_factor']:.2f}  |  OOS Trades: {oos_metrics['total_trades']}"
        )
        print('=' * 110)
        print(f'[SUCCESS] Kết quả combo đã được lưu tại: du_lieu/history_uu_hoa/{filename}\n')

    return result
                                                                          

def _chay_backtest_strategy(strat, params, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE,
                            VON_MOI_LENH, DON_BAY, start_filter, end_filter,
                            base_sl, rr, n_trials=1):
    """
    Backtest 1 plugin với 1 bộ params trên [start_filter, end_filter].

    Tín hiệu sinh trên TOÀN chuỗi (đủ warmup, không phụ thuộc điểm cắt cửa sổ) rồi
    mới lọc về cửa sổ test → gắn SL/TP + đòn bẩy + khớp lệnh.
    """
    import polars as pl
    all_trades = []
    for symbol, data in datasets.items():
        df_1m = data['df_1m']
        tf_map = data['timeframe_map']
        try:
            df_sig = strat.sinh_tin_hieu(df_1m, tf_map, params)
        except Exception as e:                
                                                                                       
                                                                              
            if not getattr(strat, '_da_bao_loi', False):
                import traceback
                print(f"[LỖI PLUGIN] sinh_tin_hieu của '{getattr(strat, 'name', '?')}' ném ngoại lệ: {e}")
                print(traceback.format_exc().rstrip())
                strat._da_bao_loi = True
            continue
        if df_sig is None:
            continue
        if not hasattr(df_sig, "clone"):
            df_sig = pl.from_pandas(df_sig)
        if "signal" not in df_sig.columns or "timestamp" not in df_sig.columns:
            continue

        df_sig = df_sig.filter(
            (pl.col("timestamp") >= start_filter) & (pl.col("timestamp") <= end_filter)
        )
        if df_sig.height < 50:
            continue

        df_sig = df_sig.with_columns(
            pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
        )

                                                                                        
        try:
            import chien_luoc.quan_ly_chien_luoc_vectorized as Q
            dung_regime_ml = getattr(Q, "DUNG_REGIME_MAC_DINH", False)
        except ImportError:
            dung_regime_ml = False

        df_sig = chuan_hoa_va_loc_tin_hieu(df_sig, dung_regime_ml=dung_regime_ml)

                                                                                                              
        df_sig = SLTP.them_sl_tp(df_sig, base_sl=base_sl, rr=rr)
        df_sig = them_don_bay_dong(df_sig, don_bay_goc=DON_BAY)
        trades, _ = run_fast_backtest(df_sig, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY, cooldown_nen=_COOLDOWN_NEN)
        all_trades.extend(trades)

    start_str = start_filter.strftime('%Y-%m-%d') if isinstance(start_filter, datetime) else str(start_filter)
    end_str = end_filter.strftime('%Y-%m-%d') if isinstance(end_filter, datetime) else str(end_filter)
    sharpe = tinh_sharpe_ratio(all_trades, start_date=start_str, end_date=end_str, von_ban_dau=VON_BAN_DAU)
    metrics = tinh_da_chi_so(all_trades, VON_BAN_DAU, start_date=start_str, end_date=end_str, n_trials=n_trials)
    return (all_trades, sharpe, metrics)

def _khong_gian_plugin(khong_gian_plugin):
    """Không gian tìm kiếm cho plugin chiến lược: từ khong_gian_tham_so() + SL/RR.

    khong_gian_plugin: list dict {ten, kieu, thap, cao, buoc, lua_chon} do plugin khai báo.
    """
    kg = {}
    for p in (khong_gian_plugin or []):
        ten = p.get('ten')
        if not ten:
            continue
        kieu = p.get('kieu', 'float')
        if kieu == 'int':
            kg[ten] = ('int', int(p['thap']), int(p['cao']))
        elif kieu == 'categorical':
            kg[ten] = ('cat', list(p.get('lua_chon') or []))
        else:
            kg[ten] = ('float', float(p['thap']), float(p['cao']), p.get('buoc'))
    (sl_lo, sl_hi), (rr_lo, rr_hi) = _lay_khoang_sl_rr()
    kg['risk_base_sl'] = ('float', sl_lo, sl_hi, 0.1)
    kg['risk_rr'] = ('float', rr_lo, rr_hi, 0.1)
    return kg


def _tach_bo_plugin(bo, khong_gian_plugin):
    """Tách bộ tham số phẳng thành (params plugin, base_sl, rr)."""
    params = {}
    for p in (khong_gian_plugin or []):
        ten = p.get('ten')
        if ten and ten in bo:
            params[ten] = bo[ten]
    return params, bo.get('risk_base_sl', 2.0), bo.get('risk_rr', 2.0)


def run_strategy_optimization(strategy_key, n_trials=100, preloaded_datasets=None, silent=False,
                              progress_cb=None, objective_metric='sharpe', so_doan_oos=4, should_stop=None):
    """
    Tối ưu hóa MỘT chiến lược PLUGIN (kế thừa ChienLuocPluginCoSo) bằng  + Walk-Forward.

    Tự lấy không gian tham số từ plugin.khong_gian_tham_so(), tối ưu trên IS, kiểm định
    mù OOS + walk-forward nhiều đoạn + DSR, trả result tương thích dashboard (gồm phan_tich).
    """
    from toi_uu_hoa.dang_ky_chien_luoc import lay_plugin

    cls = lay_plugin(strategy_key)
    if cls is None:
        raise ValueError(f"Không tìm thấy plugin chiến lược '{strategy_key}' trong STRATEGY_REGISTRY")
    strat = cls()
    khong_gian = strat.khong_gian_tham_so() or []

    config_trading = lay_cau_hinh_giao_dich()
    config_backtest = lay_cau_hinh_ao()
    objective_metric = (objective_metric or 'sharpe').lower()
    if objective_metric not in ('sharpe', 'sortino', 'calmar'):
        objective_metric = 'sharpe'

    VON_BAN_DAU = float(config_backtest.get('so_du_ban_dau', 10000))
    PHI_GD = float(config_backtest.get('phi_giao_dich', 0.001))
    SLIPPAGE = float(config_backtest.get('do_truot_gia', 0.001))
    START_DATE = config_backtest.get('ngay_bat_dau', '2025-01-01')
    END_DATE = config_backtest.get('ngay_ket_thuc', '2025-01-31')
    DON_BAY = int(config_trading.get('don_bay', 1))
    DS_SYMBOL = config_trading.get('cap_giao_dich', [])
    VON_MOI_LENH = float(config_trading.get('von_moi_lenh_usdt', 100))
    if not DS_SYMBOL:
        print('[ERROR] Không tìm thấy cặp giao dịch nào trong config/cau_hinh_giao_dich.yaml')
        sys.exit(1)

    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
    total_days = (end_dt - start_dt).days
    is_end_dt = start_dt + timedelta(days=int(total_days * IS_RATIO))
    oos_start_dt = is_end_dt + timedelta(days=1)
    IS_START, IS_END = START_DATE, is_end_dt.strftime('%Y-%m-%d')
    OOS_START, OOS_END = oos_start_dt.strftime('%Y-%m-%d'), END_DATE

    run_id = tao_run_id()

    if not silent:
        banner_khoi_dong(' STRATEGY PLUGIN OPTIMIZER (Walk-Forward)', [
            ('Chiến lược plugin', strat.name),
            ('Khóa', strategy_key),
            ('Mục tiêu (Objective)', objective_metric.upper()),
            ('Số tham số tinh chỉnh', str(len(khong_gian))),
            ('In-Sample (IS - 70%)', f'{IS_START}  ->  {IS_END}'),
            ('Out-of-Sample (OOS - 30%)', f'{OOS_START}  ->  {OOS_END}'),
            ('Vốn ban đầu', f'{VON_BAN_DAU:,.0f} USDT'),
            ('Danh sách Symbols', ', '.join(DS_SYMBOL)),
            ('Tổng trials', f'{n_trials}'),
            ('Run ID', run_id),
        ])

    if preloaded_datasets is not None:
        datasets = preloaded_datasets
    else:
        datasets = {}
        for symbol in DS_SYMBOL:
            df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)
            if df_goc is None or df_goc.is_empty():
                continue
            df_1m = df_goc
            timeframe_map = {
                '1m': df_1m, '3m': df_1m, '5m': df_1m, '15m': df_1m,
                '30m': df_1m, '1h': df_1m, '4h': df_1m, '1d': df_1m
            }
            datasets[symbol] = {'df_1m': df_1m, 'timeframe_map': timeframe_map}
    if not datasets:
        print('[ERROR] Không nạp được dữ liệu của bất kỳ symbol nào!')
        sys.exit(1)

                                                                              
    khong_gian_dict = _khong_gian_plugin(khong_gian)
    danh_sach_bo = _sinh_danh_sach_bo(khong_gian_dict, n_trials, seed=42)

    def _cham_diem(bo, so_tt):
        params, base_sl, rr = _tach_bo_plugin(bo, khong_gian)
        _, sharpe, m = _chay_backtest_strategy(
            strat, params, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
            start_filter=start_dt, end_filter=is_end_dt, base_sl=base_sl, rr=rr
        )
        if objective_metric == 'sortino':
            score = m['sortino_ratio']
        elif objective_metric == 'calmar':
            score = m['calmar_ratio'] if m['sharpe_ratio'] > -9.99 else -10.0
        else:
            score = sharpe
        if not silent:
            diem_txt = "KHÔNG ĐỦ LỆNH (<30)" if score <= -9.99 else f"{score:+.4f}"
            print(f'  [PLUGIN {strat.name} - Bộ {so_tt:03d}] IS {objective_metric}: {diem_txt} | SL: {base_sl}% | RR: {rr}')
        return score

    best_bo, _, lich_su = _duyet_tim_tot_nhat(
        danh_sach_bo, _cham_diem, progress_cb=progress_cb, should_stop=should_stop, tong=n_trials
    )
    best_params_plugin, best_sl, best_rr = _tach_bo_plugin(best_bo, khong_gian)

    is_trades, is_sharpe, is_metrics = _chay_backtest_strategy(
        strat, best_params_plugin, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
        start_filter=start_dt, end_filter=is_end_dt, base_sl=best_sl, rr=best_rr, n_trials=n_trials
    )
    oos_trades, oos_sharpe, oos_metrics = _chay_backtest_strategy(
        strat, best_params_plugin, datasets, VON_BAN_DAU, PHI_GD, SLIPPAGE, VON_MOI_LENH, DON_BAY,
        start_filter=oos_start_dt, end_filter=end_dt, base_sl=best_sl, rr=best_rr, n_trials=1
    )
    oos_is_ratio = oos_sharpe / is_sharpe if is_sharpe > 0 else 0.0

                                                                                    
    oos_folds, wf_summary = [], {}

    canh_bao = []
    is_days = max((is_end_dt - start_dt).days, 0)
    oos_days = max((end_dt - oos_start_dt).days, 0)
    is_tr = int(is_metrics.get('total_trades', 0))
    oos_tr = int(oos_metrics.get('total_trades', 0))
    ngan = [t for t, d in (("IS", is_days), ("OOS", oos_days)) if d < MIN_DAYS_TIN_CAY]
    if ngan:
        chi_tiet = ", ".join(f"{t} {d}d" for t, d in (("IS", is_days), ("OOS", oos_days)) if d < MIN_DAYS_TIN_CAY)
        canh_bao.append(f"Khoảng dữ liệu quá ngắn ({chi_tiet}; cần ≥ {MIN_DAYS_TIN_CAY}d mỗi đoạn).")
    it = [t for t, n in (("IS", is_tr), ("OOS", oos_tr)) if n < MIN_TRADES_TIN_CAY]
    if it:
        chi_tiet = ", ".join(f"{t} {n} lệnh" for t, n in (("IS", is_tr), ("OOS", oos_tr)) if n < MIN_TRADES_TIN_CAY)
        canh_bao.append(f"Quá ít lệnh ({chi_tiet}; cần ≥ {MIN_TRADES_TIN_CAY}) → Sharpe/Sortino đoạn đó bị đánh dấu KHÔNG ĐỦ DỮ LIỆU (giá trị -10).")
    if canh_bao and not silent:
        for _c in canh_bao:
            print(f"  [CẢNH BÁO DỮ LIỆU] {_c}")

    phan_tich = {
        'is': xay_dung_duong_cong(is_trades, VON_BAN_DAU, IS_START, IS_END),
        'oos': xay_dung_duong_cong(oos_trades, VON_BAN_DAU, OOS_START, OOS_END),
    }
    for _seg in phan_tich.values():
        _seg['so_du'] = round(float(VON_BAN_DAU), 2)

    trials_data = []
    for t in lich_su:
        val = t['value']
        if val != val or val in (float('inf'), float('-inf')):
            val = -10.0
        trials_data.append({'number': t['number'], 'params': t['params'], 'value': val})

    from chien_luoc.quan_ly_chien_luoc_vectorized import DUNG_SL_TP_DONG, DUNG_DON_BAY_DONG, DUNG_REGIME_MAC_DINH
    _md = _tham_so_mo_dun()
                                                                    
    best_params_out = {
        's0': {'key': strat.name, 'tf': '-', 'type': 'plugin', 'params': best_params_plugin, 'thresholds': {}},
        'risk': {
            'base_sl': best_sl,
            'rr': best_rr,
            'dung_sl_tp_dong': DUNG_SL_TP_DONG,
            'dung_don_bay_dong': DUNG_DON_BAY_DONG,
            'sl_tp_time_frame': _md['sl_tp_time_frame'],
            'don_bay_goc': _md['don_bay_goc'],
            'max_leverage': _md['max_leverage'],
            'don_bay_tf': _md['don_bay_tf'],
        },
        'logic': {
            'dung_ml': DUNG_REGIME_MAC_DINH,
            'regime_cho_phep': _md['regime_cho_phep'],
        },
        'plugin_khoa': strategy_key,
    }

    result = {
        'loai': 'plugin',
        'combo': [{'key': strategy_key, 'tf': '-', 'type': 'plugin'}],
        'combo_label': strat.name,
        'objective_metric': objective_metric,
        'canh_bao': canh_bao,
        'is_metrics': is_metrics,
        'oos_metrics': oos_metrics,
        'oos_is_ratio': oos_is_ratio,
        'oos_folds': oos_folds,
        'wf_summary': wf_summary,
        'best_params': best_params_out,
        'trials_data': trials_data,
        'phan_tich': phan_tich,
    }

    if not silent:
        import re
        def _slugify(s):
            return re.sub(r"[^0-9A-Za-z._@+-]+", "_", str(s)).strip("_").lower()
        plugin_slug = _slugify(strategy_key)
        ts = time.strftime('%Y%m%d_%H%M%S')
        filename = f"plugin__{plugin_slug}__{objective_metric}_{n_trials}t__{ts}.json"
        out_path = os.path.join(PROJECT_ROOT, 'du_lieu', 'history_uu_hoa', filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_id': run_id,
                'ngay_chay': time.strftime('%Y-%m-%d %H:%M:%S'),
                'symbols': DS_SYMBOL,
                'is_period': f'{IS_START} -> {IS_END}',
                'oos_period': f'{OOS_START} -> {OOS_END}',
                **result,
            }, f, indent=4, ensure_ascii=False)

        print('\n' + '=' * 110)
        print(f'  CHIẾN LƯỢC PLUGIN: {strat.name}')
        print('=' * 110)
        print(
            f"  IS Sharpe: {is_sharpe:+.4f} (DSR {is_metrics['deflated_sharpe_ratio'] * 100:.1f}%)  |  "
            f"OOS Sharpe: {oos_sharpe:+.4f} (DSR {oos_metrics['deflated_sharpe_ratio'] * 100:.1f}%)  |  "
            f"OOS/IS: {oos_is_ratio:.2f}"
        )
        print('=' * 110)
        print(f'[SUCCESS] Kết quả plugin đã được lưu tại: du_lieu/history_uu_hoa/{filename}\n')

    return result
