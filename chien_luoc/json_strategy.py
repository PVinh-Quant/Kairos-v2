import os
import json
import copy
import pandas as pd
import numpy as np
from chien_luoc.base_strategy import BaseStrategy
from toi_uu_hoa.dang_ky_chi_bao import INDICATOR_REGISTRY
from utils.ham_tien_ich import gop_va_dong_bo_data
from toi_uu_hoa.phan_loai_chi_bao import generate_generic_signals, ket_hop_tin_hieu_spec, get_cols_by_type
from utils.log import logger


class JSONStrategy(BaseStrategy):
    """
    Lớp chiến lược thông dịch cấu hình từ file JSON.
    Hỗ trợ cả Vectorized (Backtest) và Bar-to-bar (Realtime).
    """
    def __init__(self, json_path: str):
        self._json_path = json_path
        self._name = os.path.splitext(os.path.basename(json_path))[0]
        
                             
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
                                                                                           
        if isinstance(data, dict):
            if "result" in data and isinstance(data["result"], dict):
                inner = data["result"]
                if "best_params" in inner and isinstance(inner["best_params"], dict):
                    self.config = inner["best_params"]
                else:
                    self.config = inner
            elif "best_params" in data and isinstance(data["best_params"], dict):
                self.config = data["best_params"]
            else:
                self.config = data
        else:
            self.config = {}

        self.specs = {}
        self.risk = {"base_sl": 2.5, "rr": 2.0}
        self.logic = {"mode": "and", "persistence": 1}

                                                   
        for k, v in self.config.items():
            if k == "risk":
                self.risk.update(v)
            elif k == "logic":
                self.logic.update(v)
            elif k.startswith("s") and k[1:].isdigit():
                self.specs[k] = v

                                                                          
        self._is_plugin = False
        self._plugin_instance = None
        self._plugin_params = {}
        
        plugin_key = None
        for source in [data, data.get("result", {}), data.get("best_params", {})]:
            if isinstance(source, dict):
                if source.get("loai") == "plugin" or "plugin_khoa" in source:
                    plugin_key = source.get("plugin_khoa")
                    break
        
                                                                               
        if isinstance(self.config, dict):
            if not plugin_key:
                s0 = self.config.get("s0", {})
                if isinstance(s0, dict) and (s0.get("type") == "plugin" or s0.get("key") == "plugin"):
                    plugin_key = s0.get("key")
            if not plugin_key and "plugin_khoa" in self.config:
                plugin_key = self.config.get("plugin_khoa")

        if plugin_key:
            try:
                from toi_uu_hoa.dang_ky_chien_luoc import lay_plugin, nap_plugins
                nap_plugins(im_lang=True)
                cls = lay_plugin(plugin_key)
                if cls:
                    self._is_plugin = True
                    self._plugin_instance = cls()
                    if isinstance(self.config, dict):
                        s0 = self.config.get("s0", {})
                        if isinstance(s0, dict) and s0.get("type") == "plugin":
                            self._plugin_params = s0.get("params", {})
                        else:
                            self._plugin_params = {k: v for k, v in self.config.items() if k not in ("risk", "logic", "combo", "loai", "plugin_khoa")}
                    logger.info(f"Loaded Plugin Strategy '{plugin_key}' dynamically inside JSONStrategy wrapper.")
            except Exception as e:
                logger.error(f"Error loading plugin '{plugin_key}' for JSONStrategy: {e}")

    @property
    def name(self) -> str:
        if self._is_plugin:
            return self._plugin_instance.name
        return self._name

    def get_default_params(self) -> dict:
        if self._is_plugin:
            return self._plugin_instance.get_default_params()
        return {
            "specs": self.specs,
            "risk": self.risk
        }

    def tinh_chi_bao(self, df_1m, timeframe_map: dict = None):
        if self._is_plugin:
            return self._plugin_instance.tinh_chi_bao(df_1m, timeframe_map)

        """
        Tính toán các chỉ báo kỹ thuật trên DataFrame của các khung thời gian tương ứng
        và đồng bộ dữ liệu về timeline 1m bằng Polars.
        Hỗ trợ cả Pandas và Polars DataFrame đầu vào.
        """
        import polars as pl
        from utils.ham_tien_ich import gop_va_dong_bo_data_polars

        is_pandas = not hasattr(df_1m, "clone")
        if is_pandas:
            df_work_1m = pl.from_pandas(df_1m)
        else:
            df_work_1m = df_1m.clone()

        if not timeframe_map:
            df_work = df_work_1m
            self._spec_target = {}
            for idx_str, spec in self.specs.items():
                key = spec['key']
                tf = spec.get('tf', '1m')
                if key not in INDICATOR_REGISTRY:
                    logger.error(f"Indicator '{key}' not found in INDICATOR_REGISTRY!")
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                func = INDICATOR_REGISTRY[key]
                params = spec.get('params', {})
                before_cols = set(df_work.columns)
                try:
                    df_work = func(df_work, tf, **params)
                except Exception as e:
                    logger.error(f"Error calculating indicator '{key}' on {tf} for {self.name}: {e}")
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                new_cols = [c for c in df_work.columns if c not in before_cols]
                if not new_cols:
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                target_col = get_cols_by_type(new_cols, spec['type'])
                rename_dict = {c: f'{idx_str}_{c}' for c in new_cols}
                df_work = df_work.rename(rename_dict)
                
                if spec['type'] == 'channel':
                    col_up, col_lo = target_col if isinstance(target_col, tuple) else (target_col, target_col)
                    tcol = (
                        f'{idx_str}_{col_up}'.lower() if col_up else None,
                        f'{idx_str}_{col_lo}'.lower() if col_lo else None,
                    )
                else:
                    tcol = f'{idx_str}_{target_col}'.lower() if target_col else None
                
                self._spec_target[idx_str] = (spec['type'], tcol)
            return df_work.to_pandas() if is_pandas else df_work

                                                                                              
        specs_by_tf = {}
        for idx_str, spec in self.specs.items():
            tf = spec.get('tf', '1m')
            specs_by_tf.setdefault(tf, []).append((idx_str, spec))

        tf_map_pl = {}
        if timeframe_map:
            for tf, df_tf in timeframe_map.items():
                if df_tf is not None:
                    tf_map_pl[tf] = pl.from_pandas(df_tf) if not hasattr(df_tf, "clone") else df_tf.clone()

        dfs_dict = {'1m': df_work_1m}
        self._spec_target = {}

        for tf, idx_specs in specs_by_tf.items():
            if tf == '1m':
                df_work = df_work_1m.clone()
            elif tf in tf_map_pl:
                df_work = tf_map_pl[tf].clone()
            else:
                df_work = df_work_1m.clone()

            for idx_str, spec in idx_specs:
                key = spec['key']
                if key not in INDICATOR_REGISTRY:
                    logger.error(f"Indicator '{key}' not found in INDICATOR_REGISTRY!")
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                func = INDICATOR_REGISTRY[key]
                params = spec.get('params', {})
                before_cols = set(df_work.columns)
                try:
                    df_work = func(df_work, tf, **params)
                except Exception as e:
                    logger.error(f"Error calculating indicator '{key}' on {tf} for {self.name}: {e}")
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                new_cols = [c for c in df_work.columns if c not in before_cols]
                if not new_cols:
                    self._spec_target[idx_str] = (spec['type'], None)
                    continue

                target_col = get_cols_by_type(new_cols, spec['type'])
                rename_dict = {c: f'{idx_str}_{c}' for c in new_cols}
                df_work = df_work.rename(rename_dict)
                
                if spec['type'] == 'channel':
                    col_up, col_lo = target_col if isinstance(target_col, tuple) else (target_col, target_col)
                    tcol = (
                        f'{idx_str}_{col_up}'.lower() if col_up else None,
                        f'{idx_str}_{col_lo}'.lower() if col_lo else None,
                    )
                else:
                    tcol = f'{idx_str}_{target_col}'.lower() if target_col else None
                
                self._spec_target[idx_str] = (spec['type'], tcol)

            dfs_dict[tf] = df_work

        df_merged = gop_va_dong_bo_data_polars(dfs_dict)
        return df_merged.to_pandas() if is_pandas else df_merged

    def tinh_tin_hieu_vectorized(self, df, params: dict = None):
        if self._is_plugin:
            p = params if params is not None else self._plugin_params
            return self._plugin_instance.tinh_tin_hieu_vectorized(df, p)

        """
        Tính toán tín hiệu giao dịch từ các chỉ báo đã có sẵn trong df bằng Polars.
        Hỗ trợ cả Pandas và Polars DataFrame đầu vào.
        """
        import polars as pl
        import numpy as np

        is_pandas = not hasattr(df, "clone")
        if is_pandas:
            df_pl = pl.from_pandas(df)
        else:
            df_pl = df.clone()

                                                     
        local_specs = copy.deepcopy(self.specs)

        if params:
            for k, v in params.items():
                if k.startswith("s"):
                    parts = k.split("_", 1)
                    if len(parts) == 2:
                        s_idx_str, param_name = parts
                        if s_idx_str in local_specs:
                            spec = local_specs[s_idx_str]
                            if param_name in ["oversold", "overbought", "lower_mult", "upper_mult", "dev_above", "dev_below", "vol_enter", "vol_exit"]:
                                spec.setdefault("thresholds", {})[param_name] = v
                            else:
                                spec.setdefault("params", {})[param_name] = v

                                                                                          
                                                                                                  
        logic_mode = self.logic.get("mode", "and").lower()
        persistence = int(self.logic.get("persistence", 1))

        resolved_specs = []
        for idx_str, spec in sorted(local_specs.items(), key=lambda x: int(x[0][1:])):
            t_type, tcol = self._spec_target.get(idx_str, (spec['type'], None))
            resolved_specs.append({
                't_type': t_type,
                'tcol': tcol,
                'thresholds': spec.get('thresholds', {}),
                'role': spec.get('role', 'trigger'),
            })

        df_pl, _ = ket_hop_tin_hieu_spec(
            df_pl, resolved_specs, logic=logic_mode, persistence=persistence
        )

        df_pl = df_pl.with_columns(
            pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
        )

        return df_pl.to_pandas() if is_pandas else df_pl


    def phan_tich_live(
        self,
        symbol,
        df_1m,
        df_3m,
        df_5m,
        df_15m,
        df_30m,
        df_1h,
        df_4h,
        df_1d,
        MarketSnapshot=None,
        params: dict = None
    ):
        """
        Live entry analysis (Bar-to-bar).
        """
                                                     
        timeframe_map = {
            "3m": df_3m,
            "5m": df_5m,
            "15m": df_15m,
            "30m": df_30m,
            "1h": df_1h,
            "4h": df_4h,
            "1d": df_1d
        }
        
                                                                                
        df_merged = self.tinh_chi_bao(df_1m, timeframe_map)
        df_sig = self.tinh_tin_hieu_vectorized(df_merged, params)

        if df_sig is None or (hasattr(df_sig, "is_empty") and df_sig.is_empty()) or (hasattr(df_sig, "empty") and df_sig.empty):
            return None, 0, f"[{self.name}] Không có dữ liệu sau tính toán chỉ báo"

                                                     
        if hasattr(df_sig, "clone"):
            sig_val = df_sig['signal'].item(-1)
        else:
            sig_val = df_sig['signal'].iloc[-1]
        
                                                          
        if sig_val == 1:
            return "buy", 25, f"[{self.name}] Đồng thuận chỉ báo LONG"
        elif sig_val == -1:
            return "sell", -25, f"[{self.name}] Đồng thuận chỉ báo SHORT"
            
        return None, 0, f"[{self.name}] Không có tín hiệu đồng thuận"

    def thoat_live(
        self,
        df_1m,
        df_3m,
        df_5m,
        df_15m,
        df_30m,
        df_1h,
        df_4h,
        df_1d,
        MarketSnapshot=None,
        params: dict = None
    ):
        """
        Live exit analysis (Bar-to-bar).
        """
                                                     
        timeframe_map = {
            "3m": df_3m,
            "5m": df_5m,
            "15m": df_15m,
            "30m": df_30m,
            "1h": df_1h,
            "4h": df_4h,
            "1d": df_1d
        }
        
        df_merged = self.tinh_chi_bao(df_1m, timeframe_map)
        df_sig = self.tinh_tin_hieu_vectorized(df_merged, params)

        if df_sig is None or (hasattr(df_sig, "is_empty") and df_sig.is_empty()) or (hasattr(df_sig, "empty") and df_sig.empty):
            return None, 0, f"[{self.name}] Không có dữ liệu thoát"

        if hasattr(df_sig, "clone"):
            sig_val = df_sig['signal'].item(-1)
        else:
            sig_val = df_sig['signal'].iloc[-1]
        
                                                   
        if sig_val == -1:
            return "sell", 25, f"[{self.name}] Đóng vị thế BUY do xuất hiện tín hiệu SHORT"
        elif sig_val == 1:
            return "buy", -25, f"[{self.name}] Đóng vị thế SELL do xuất hiện tín hiệu LONG"
            
        return None, 0, "Giữ lệnh"
