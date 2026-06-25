"""
toi_uu_hoa_low/giao_dien_cli.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Giao diện dòng lệnh tương tác (Interactive CLI) sử dụng Rich.

Cung cấp menu trực quan để người dùng chọn chỉ báo, số trials
hoặc thực hiện quét hàng loạt tất cả chỉ báo để so sánh hiệu suất.
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
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.prompt import Prompt, IntPrompt
except ImportError:
    print('\n[ERROR] Thư viện \'rich\' chưa được cài đặt. Vui lòng chạy: pip install rich\n')
    sys.exit(1)

try:
    from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY, list_indicators
    from toi_uu_hoa.bo_dieu_phoi import run_indicator_optimization, run_all_indicators_comparison
except ImportError as e:
    print(f'[ERROR] Lỗi Import trong giao_dien_cli.py: {e}')
    sys.exit(1)


def chay_menu_tuong_tac():
    """Hiển thị menu tương tác đẹp mắt bằng thư viện rich để người dùng lựa chọn."""
    console = Console()
    
    while True:
        console.clear()
        
                                       
        banner_text = Text(justify='center')
        banner_text.append('KAIROS-V2 INDICATOR OPTIMIZER\n', style='bold cyan')
        banner_text.append('Hệ Thống Tối Ưu Hóa & Định Cấu Hình Tham Số Tự Động', style='dim italic white')
        console.print(Panel(banner_text, title='[bold gold1]❖ MENU CHÍNH ❖[/bold gold1]', border_style='cyan', box=box.DOUBLE))
        
                                   
        menu_table = Table(box=box.ROUNDED, show_header=True, border_style='blue', expand=True)
        menu_table.add_column('Lựa chọn', style='bold yellow', justify='center', width=10)
        menu_table.add_column('Chức năng mô tả', style='white')
        
        menu_table.add_row('1', '[bold green]Tối ưu hóa MỘT CHỈ BÁO cụ thể[/bold green] (Chạy độc lập cho cả 7 khung thời gian)')
        menu_table.add_row('2', '[bold orange1]Quét & So sánh TẤT CẢ các chỉ báo[/bold orange1] (Tìm kiếm chỉ báo tối ưu toàn cục)')
        menu_table.add_row('3', '[bold magenta]Xem danh sách chỉ báo hỗ trợ[/bold magenta] (Xem danh mục phân loại chi tiết)')
        menu_table.add_row('4', '[bold red]Thoát[/bold red] (Đóng chương trình)')
        console.print(menu_table)
        
        choice = Prompt.ask('\n[bold cyan]Lựa chọn của bạn[/bold cyan]', choices=['1', '2', '3', '4'], default='1')
        
                                                                       
        if choice == '1':
            try:
                from hien_thi.man_hinh.toi_uu.dinh_nghia import CATEGORIES as dinh_nghia_categories
                categories = {
                    'Momentum (Dao động / Động lượng)': dinh_nghia_categories.get("Momentum / Dao động", []),
                    'Volatility (Biến động / Dải băng)': dinh_nghia_categories.get("Volatility / Dải băng", []),
                    'Trend (Xu hướng / MA)': dinh_nghia_categories.get("Trend / Xu hướng", []),
                    'Volume (Khối lượng)': dinh_nghia_categories.get("Volume / Khối lượng", []),
                    'Market Structure (Cấu trúc giá)': dinh_nghia_categories.get("Market Structure / Cấu trúc giá", []),
                    'Sentiment & Positioning (Vị thế)': dinh_nghia_categories.get("Sentiment & Positioning / Vị thế", []),
                }
                if "Khác / Chưa phân loại" in dinh_nghia_categories:
                    categories['Khác / Chưa phân loại'] = dinh_nghia_categories["Khác / Chưa phân loại"]
            except Exception:
                categories = {
                    'Momentum (Dao động / Động lượng)': [
                        'rsi', 'stochastic', 'mfi', 'ultimate', 'stoch_rsi', 'stc'
                    ],
                    'Volatility (Biến động / Dải băng)': [
                        'bollinger', 'keltner', 'donchian', 'atr_bands', 'chandelier_exit', 'choppiness'
                    ],
                    'Trend (Xu hướng / MA)': [
                        'ema', 'sma', 'adx', 'supertrend', 'macd', 'psar', 'aroon', 'vortex',
                        'hma', 'kama', 'alma', 'vwma'
                    ],
                    'Volume (Khối lượng)': [
                        'volume', 'obv', 'vwap', 'cmf', 'mfi_volume', 'pvt', 'chaikin_oscillator'
                    ],
                    'Market Structure (Cấu trúc giá)': [
                        'fractals'
                    ],
                    'Sentiment & Positioning (Vị thế)': [
                        'elder_ray'
                    ]
                }
            
                                                                
            flat_indicators = []
            ind_table = Table(title='\n[bold cyan]DANH SÁCH CHỈ BÁO KỸ THUẬT[/bold cyan]', box=box.ROUNDED, border_style='cyan')
            ind_table.add_column('STT', style='bold yellow', justify='center')
            ind_table.add_column('Mã chỉ báo', style='bold green')
            ind_table.add_column('Phân loại danh mục', style='dim white')
            
            idx = 1
            for cat, items in categories.items():
                for item in items:
                    flat_indicators.append(item)
                    ind_table.add_row(f'{idx:02d}', item, cat)
                    idx += 1
            
            console.print(ind_table)
            
            ind_choice = Prompt.ask(
                f'\n[bold cyan]Chọn chỉ báo[/bold cyan] (Nhập số [bold yellow]1-{len(flat_indicators)}[/bold yellow] hoặc [bold green]tên chỉ báo[/bold green], nhấn [bold red]Enter[/bold red] để quay lại)'
            ).strip().lower()
            
            if not ind_choice:
                continue                       
                
            target_key = None
            if ind_choice.isdigit():
                num = int(ind_choice)
                if 1 <= num <= len(flat_indicators):
                    target_key = flat_indicators[num - 1]
            else:
                if ind_choice in INDICATOR_REGISTRY:
                    target_key = ind_choice
            
            if target_key:
                                                                                           
                valid_tfs = ['1m', '3m', '5m', '15m', '30m', '1h', '4h']
                tf_table = Table(title='\n[bold cyan]PHẠM VI KHUNG THỜI GIAN[/bold cyan]', box=box.ROUNDED, border_style='cyan')
                tf_table.add_column('Lựa chọn', style='bold yellow', justify='center')
                tf_table.add_column('Mô tả', style='white')
                tf_table.add_row('all', 'Chạy tối ưu hóa trên toàn bộ 7 khung thời gian (1m, 3m, 5m, 15m, 30m, 1h, 4h)')
                for tf in valid_tfs:
                    tf_table.add_row(tf, f'Chỉ chạy tối ưu hóa riêng cho khung {tf}')
                console.print(tf_table)

                tf_choice = Prompt.ask(
                    '\n[bold cyan]Chọn phạm vi khung thời gian[/bold cyan]',
                    choices=['all'] + valid_tfs, default='all'
                ).strip().lower()
                target_timeframe = tf_choice if tf_choice != 'all' else None

                n_trials_default = 90 if target_timeframe is None else 30
                n_trials = IntPrompt.ask('[bold cyan]Nhập tổng số trials muốn chạy[/bold cyan]', default=n_trials_default)
                min_trials = 7 if target_timeframe is None else 5
                if n_trials < min_trials:
                    console.print(f'[yellow][Cảnh báo][/yellow] Số trials quá nhỏ, tự động tăng lên {min_trials} để chạy tối thiểu 1 trial.')
                    n_trials = min_trials

                                              
                indicator_func_to_run = INDICATOR_REGISTRY[target_key]
                run_indicator_optimization(indicator_func_to_run, n_trials=n_trials, target_timeframe=target_timeframe)
                input('\nNhấn Enter để quay lại Menu chính...')
            else:
                console.print('[bold red][Lỗi][/bold red] Lựa chọn chỉ báo không hợp lệ. Vui lòng chọn lại.')
                input('\nNhấn Enter để quay lại...')
                
                                                                             
        elif choice == '2':
            n_trials = IntPrompt.ask('[bold cyan]Nhập số trials chạy cho mỗi chỉ báo[/bold cyan]', default=12)
            if n_trials < 7:
                console.print('[yellow][Cảnh báo][/yellow] Số trials quá nhỏ, tự động tăng lên 7 để chạy tối thiểu 1 trial cho mỗi khung thời gian.')
                n_trials = 7
            
                                           
            run_all_indicators_comparison(n_trials=n_trials)
            input('\nNhấn Enter để quay lại Menu chính...')
            
                                                                              
        elif choice == '3':
            list_indicators()
            input('\nNhấn Enter để quay lại Menu chính...')
            
                                                                
        elif choice == '4':
            console.print('[bold green]Cảm ơn bạn đã sử dụng Kairos-v2 Optimizer. Tạm biệt![/bold green]')
            sys.exit(0)