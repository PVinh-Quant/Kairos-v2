"""
toi_uu_hoa_low/dang_ky_chi_bao.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Registry trung tâm ánh xạ tên chỉ báo → hàm triển khai.

INDICATOR_REGISTRY là điểm kết nối duy nhất giữa bộ tối ưu hóa 
và tất cả các hàm chỉ báo trong chien_luoc/. Thêm chỉ báo mới chỉ cần
thêm 1 dòng vào dict này mà không cần sửa bất cứ module nào khác.

HƯỚNG DẪN THÊM CHỈ BÁO MỚI:
1. Viết hàm phân tích kỹ thuật của bạn trong thư mục `chien_luoc/logic_vectorized/Indicator/`.
2. Hàm của bạn nên nhận `df` (DataFrame) làm đối số đầu tiên, cùng các tham số cấu hình khác.
3. Import module chứa hàm đó vào file này.
4. Đăng ký một cặp key-value vào `INDICATOR_REGISTRY` dưới đây:
   - Key: tên ngắn đại diện (dùng trong CLI / CLI argument).
   - Value: tham chiếu trực tiếp đến hàm (không có dấu ngoặc tròn gọi hàm).
"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import Indicator.cau_truc_gia    as MS
    import Indicator.xu_huong        as Trend
    import Indicator.khoi_luong      as Vol
    import Indicator.bien_dong       as Volatility
    import Indicator.dong_luong_dao_chieu as Momentum
    import Indicator.vi_the          as Pos
except ImportError as e:
    print(f'[ERROR] Lỗi Import chỉ báo trong dang_ky_chi_bao.py: {e}')
    sys.exit(1)


                                                                               
                    
                                  
                                                                       
                                                                               

INDICATOR_REGISTRY = {
                                                                               
    'rsi':               Momentum.pt_rsi,
    'stochastic':        Momentum.pt_stochastic,
    'mfi':               Momentum.pt_mfi,
    'ultimate':          Momentum.pt_ultimate_oscillator,
    'stoch_rsi':         Momentum.pt_stoch_rsi,
    'stc':               Momentum.pt_stc,


                                                                               
    'bollinger':         Volatility.pt_bollinger_squeeze,
    'keltner':           Volatility.pt_keltner_channel,
    'donchian':          Volatility.pt_donchian_channel,
    'atr_bands':         Volatility.pt_atr_bands,
    'chandelier_exit':   Volatility.pt_chandelier_exit,
    'choppiness':        Volatility.pt_choppiness_index,


                                                                               
    'ema':               Trend.pt_ema_trend,
    'sma':               Trend.pt_sma,
    'adx':               Trend.pt_adx,
    'supertrend':        Trend.pt_supertrend,
    'macd':              Trend.pt_macd,
    'psar':              Trend.pt_psar,
    'aroon':             Trend.pt_aroon,
    'vortex':            Trend.pt_vortex,
    'hma':               Trend.pt_hma,
    'kama':              Trend.pt_kama,
    'alma':              Trend.pt_alma,
    'vwma':              Trend.pt_vwma,

                                                                               
    'volume':            Vol.pt_volume,
    'obv':               Vol.pt_obv,
    'vwap':              Vol.pt_vwap,
    'cmf':               Vol.pt_cmf,
    'mfi_volume':        Vol.pt_mfi_volume,
    'pvt':               Vol.pt_pvt,
    'chaikin_oscillator': Vol.pt_chaikin_oscillator,

                                                                              
    'fractals':          MS.pt_fractals,


                                                                               
    'elder_ray':         Pos.pt_elder_ray,
}


def list_indicators():
    """In danh sách chỉ báo theo nhóm và hướng dẫn cú pháp chạy ra màn hình CLI."""
    print('\n' + '=' * 80)
    print('        DANH SÁCH CHỈ BÁO HỖ TRỢ TRONG INDICATOR_REGISTRY')
    print('=' * 80)

    categories = {
        'Momentum (Dao động / Động lượng)':  ['rsi', 'stochastic', 'mfi', 'ultimate', 'stoch_rsi', 'stc'],
        'Volatility (Biến động / Dải băng)': ['bollinger', 'keltner', 'donchian', 'atr_bands', 'chandelier_exit', 'choppiness'],
        'Trend (Xu hướng / MA)':             ['ema', 'sma', 'adx', 'supertrend', 'macd', 'psar', 'aroon', 'vortex', 'hma', 'kama', 'alma', 'vwma'],
        'Volume (Khối lượng)':               ['volume', 'obv', 'vwap', 'cmf', 'mfi_volume', 'pvt', 'chaikin_oscillator'],
        'Market Structure (Cấu trúc giá)':   ['fractals'],
        'Sentiment & Positioning (Vị thế)':  ['elder_ray'],
    }

    for cat, items in categories.items():
        print(f'\n  * {cat}:')
        print('    ' + ', '.join(items))

    print('\n' + '=' * 80)
    print('  Cú pháp chạy:')
    print('    1. Tối ưu một chỉ báo cụ thể trên tất cả khung thời gian:')
    print('       python toi_uu_hoa_low/toi_uu_hoa.py [ten_chi_bao] [so_trials]')
    print('       Ví dụ: python toi_uu_hoa_low/toi_uu_hoa.py rsi 90')
    print('    2. Quét và so sánh toàn bộ chỉ báo:')
    print('       python toi_uu_hoa_low/toi_uu_hoa.py all [so_trials]')
    print('=' * 80 + '\n')

