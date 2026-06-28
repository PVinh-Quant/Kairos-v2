"""
toi_uu_hoa_low/toi_uu_hoa.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entry point chính của hệ thống tối ưu hóa hoa.

Cách dùng:
    python toi_uu_hoa/toi_uu_hoa.py                 → Mở CLI menu tương tác
    python toi_uu_hoa/toi_uu_hoa.py rsi 90          → Tối ưu chỉ báo RSI, 90 trials (cả 7 khung)
    python toi_uu_hoa/toi_uu_hoa.py rsi 90 15m      → Tối ưu chỉ báo RSI, 90 trials, chỉ khung 15m
    python toi_uu_hoa/toi_uu_hoa.py all 12          → Quét toàn bộ, 12 trials/chỉ báo
    python toi_uu_hoa/toi_uu_hoa.py combo rsi:1m macd:5m 100
                                                    → Tối ưu chiến lược KẾT HỢP nhiều chỉ báo
                                                      đa khung (logic AND), 100 trials
    python toi_uu_hoa_low/toi_uu_hoa.py --list          → Xem danh sách chỉ báo hỗ trợ
"""

import sys
import os


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY, list_indicators
    from toi_uu_hoa.bo_dieu_phoi import (
        run_indicator_optimization,
        run_all_indicators_comparison,
        run_combo_optimization,
    )
    from toi_uu_hoa.giao_dien_cli import chay_menu_tuong_tac
except ImportError as e:
    print(f'[ERROR] Lỗi Import trong toi_uu_hoa.py: {e}')
    sys.exit(1)


if __name__ == '__main__':

    if len(sys.argv) > 1 and sys.argv[1].lower() in ['--list', '-l', 'list']:
        list_indicators()
        sys.exit(0)


    if len(sys.argv) == 1:
        chay_menu_tuong_tac()
        sys.exit(0)


    target_key    = sys.argv[1].lower()



    if target_key == 'combo':
        combo = []
        n_trials_combo = 100
        for tok in sys.argv[2:]:
            if ':' in tok:
                k, tf = tok.split(':', 1)
                combo.append({'key': k.lower(), 'tf': tf.lower()})
            elif tok.isdigit():
                n_trials_combo = int(tok)
        if not combo:
            print('[ERROR] Cú pháp: python toi_uu_hoa_low/toi_uu_hoa.py combo rsi:1m macd:5m [so_trials]')
            sys.exit(1)
        run_combo_optimization(combo, n_trials=n_trials_combo)
        sys.exit(0)

    n_trials_arg  = 90
    target_tf_arg = None


    if len(sys.argv) > 2:
        try:
            n_trials_arg = int(sys.argv[2])
        except ValueError:
            print(f'[WARN] Tham số trials không hợp lệ: "{sys.argv[2]}", sử dụng mặc định là {n_trials_arg}.')


    if len(sys.argv) > 3:
        target_tf_arg = sys.argv[3].lower()


    if target_key == 'all':
        n_all = n_trials_arg if len(sys.argv) > 2 else 12
        run_all_indicators_comparison(n_trials=n_all)


    else:
        if target_key not in INDICATOR_REGISTRY:
            print(f"[ERROR] Chỉ báo '{target_key}' không được hỗ trợ trong hệ thống.")
            list_indicators()
            sys.exit(1)


        run_indicator_optimization(INDICATOR_REGISTRY[target_key], n_trials=n_trials_arg, target_timeframe=target_tf_arg)

