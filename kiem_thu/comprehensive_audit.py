import sys, os, re, importlib
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import polars as pl
import numpy as np
import pandas as pd

np.random.seed(42)
n = 500
close = 50000.0 + np.cumsum(np.random.randn(n) * 100)
close = np.maximum(close, 100.0)
high = close * (1 + np.abs(np.random.randn(n) * 0.005))
low = close * (1 - np.abs(np.random.randn(n) * 0.005))
open_ = close + np.random.randn(n) * 50
vol = np.abs(np.random.randn(n) * 1000) + 500
ts = pd.date_range(start='2024-01-01', periods=n, freq='1min')

test_df = pl.DataFrame({
    'timestamp': ts,
    'open': open_,
    'high': high,
    'low': low,
    'close': close,
    'volume': vol,
    'volume_luy_ke': np.cumsum(vol),
    'buy_volume': vol * 0.6,
    'sell_volume': vol * 0.4,
})

test_df = test_df.with_columns([
    (pl.col("volume") * 0.1).alias("buy_vol"),
    (pl.col("volume") * 0.1).alias("sell_vol"),
])

base_cols = set(test_df.columns)

indicator_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Indicator')
py_files = [f for f in os.listdir(indicator_dir) if f.endswith('.py') and f != '__init__.py']

all_funcs = []
for file in py_files:
    module_name = file[:-3]
    file_path = os.path.join(indicator_dir, file)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    funcs = re.findall(r'def\s+(pt_\w+)\s*\(', content)
    for func in funcs:
        all_funcs.append((module_name, func))

print("=" * 110)
print("  CHI TIẾT TOÀN BỘ CỘT ĐẦU RA CỦA 64 HÀM CHỈ BÁO KỸ THUẬT (XÁC MINH SẠCH SẼ)")
print("=" * 110)

for mod in sorted(list(set([m for m, f in all_funcs]))):
    print(f"\n📂 Module: Indicator.{mod}")
    print("-" * 110)
    mod_funcs = [f for m, f in all_funcs if m == mod]
    
    for func_name in sorted(mod_funcs):
        try:
            module = importlib.import_module(f"Indicator.{mod}")
            func = getattr(module, func_name)
            
            df_in = test_df.clone()
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            kwargs = {}
            if 'time_frame' in params:
                kwargs['time_frame'] = '5m'
            elif 'polars_time_frame' in params:
                kwargs['polars_time_frame'] = '5m'
                
            if len(params) == 1 and params[0] == 'df':
                res = func(df_in)
            else:
                res = func(df_in, **kwargs)
                
            new_cols = [c for c in res.columns if c not in base_cols]
            
            print(f"  • {func_name:<30} -> {new_cols}")
            
        except Exception as e:
            print(f"  • {func_name:<30} -> ⚠️ LỖI: {e}")
print("=" * 110)
