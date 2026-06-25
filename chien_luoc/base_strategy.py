import abc
import pandas as pd

class BaseStrategy(abc.ABC):
    """
    Lớp chiến lược cơ sở (Base Strategy Class) định nghĩa giao thức API
    cho cả hai chế độ chạy: Vectorized (backtest/tối ưu) và Bar-to-bar (realtime).
    """

                                                                               
    mo_ta: str = ""                                                        
    nhom: str = "Chiến lược plugin"                                        

    def khong_gian_tham_so(self) -> list:
        """Khai báo KHÔNG GIAN THAM SỐ để Optuna tối ưu (mặc định: rỗng).

        Trả về list các dict, mỗi dict mô tả 1 tham số:
          - {'ten': str, 'kieu': 'int',         'thap': int,   'cao': int,   'buoc': int (tùy)}
          - {'ten': str, 'kieu': 'float',       'thap': float, 'cao': float, 'buoc': float (tùy)}
          - {'ten': str, 'kieu': 'categorical', 'lua_chon': [...]}
        Rỗng = không có tham số tinh chỉnh (tối ưu chạy với get_default_params()).
        """
        return []

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Trả về tên định danh duy nhất của chiến lược."""
        pass

    @abc.abstractmethod
    def get_default_params(self) -> dict:
        """Trả về không gian tham số mặc định và search space của chiến lược."""
        pass

    @abc.abstractmethod
    def tinh_chi_bao(self, df_1m: pd.DataFrame, timeframe_map: dict = None) -> pd.DataFrame:
        """
        Tính toán các chỉ báo kỹ thuật trên DataFrame 1m.
        Có thể sử dụng timeframe_map để truy xuất các khung thời gian lớn hơn (nếu có).
        """
        pass

    @abc.abstractmethod
    def tinh_tin_hieu_vectorized(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """
        Nhận DataFrame 1m đã có chỉ báo, tính toán và thêm các cột:
        - 'signal': Vị thế mong muốn (1: LONG, -1: SHORT, 0: OUT)
        - 'entry_signal': Tín hiệu kích hoạt lệnh tại thời điểm đảo chiều

        Lưu ý: quản lý vốn (sl_pct, tp_pct, leverage) là logic dùng chung,
        được áp dụng ở tầng ngoài (orchestrator vectorized / engine bar-to-bar),
        không phải trách nhiệm của từng chiến lược.
        """
        pass

    @abc.abstractmethod
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
        Kiểm tra tín hiệu mở vị thế mới thời gian thực (Bar-to-bar).
        Trả về: (tin_hieu, diem, ly_do)
          - tin_hieu: "buy", "sell", hoặc None
          - diem: float (trọng số tín hiệu)
          - ly_do: str hoặc list[str] (mô tả lý do)
        """
        pass

    @abc.abstractmethod
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
        Kiểm tra tín hiệu đóng vị thế sớm thời gian thực.
        Trả về: (huong_thoat, diem, ly_do)
          - huong_thoat: "buy", "sell" (hướng ngược lại để đóng vị thế), hoặc None
          - diem: float
          - ly_do: str
        """
        pass


class ChienLuocPluginCoSo(BaseStrategy):
    """
    Lớp CƠ SỞ cho plugin chiến lược tùy chỉnh (M1 Strategy Plugin Interface).

    Người viết plugin CHỈ cần:
      1. Đặt `ten` (và tùy chọn `mo_ta`, `nhom`) ở cấp class.
      2. Hiện thực 1 hàm `sinh_tin_hieu(df, tf_map, params) -> df` (thêm cột 'signal' 1/-1/0).
      3. (Tùy chọn) khai báo `khong_gian_tham_so()` để Optuna tinh chỉnh.

    Phần backtest/live (tinh_chi_bao, tinh_tin_hieu_vectorized, phan_tich_live,
    thoat_live) được lớp này tự lo dựa trên `sinh_tin_hieu` nên không phải viết lại.
    Drop file .py chứa lớp con vào `chien_luoc/user_strategies/` là tự được nạp.
    """

    ten: str = ""

    @property
    def name(self) -> str:
        return self.ten or self.__class__.__name__

    @classmethod
    def khoa(cls) -> str:
        """Khóa đăng ký (key) dùng cho registry/dashboard — lấy từ `ten` hoặc tên class.

        Bỏ dấu tiếng Việt để key gọn (vd "RSI đảo chiều" → "rsi_dao_chieu").
        """
        import re
        import unicodedata
        raw = (cls.ten or cls.__name__)
        raw = raw.replace("đ", "d").replace("Đ", "D")
        raw = unicodedata.normalize("NFKD", raw)
        raw = "".join(c for c in raw if not unicodedata.combining(c))
        return re.sub(r"[^0-9a-z]+", "_", raw.lower()).strip("_") or cls.__name__.lower()

                                                                               
    @abc.abstractmethod
    def sinh_tin_hieu(self, df, tf_map=None, params=None):
        """Nhận df 1m (Polars hoặc Pandas) + tf_map (tùy chọn) + params (dict) →
        trả df có thêm cột 'signal' (1=LONG, -1=SHORT, 0=NO POSITION).

        Lưu ý: KHÔNG đặt SL/TP/đòn bẩy ở đây — tầng tối ưu/engine lo phần đó.
        """
        raise NotImplementedError

                                                                                
    def get_default_params(self) -> dict:
        out = {}
        for p in (self.khong_gian_tham_so() or []):
            ten = p.get("ten")
            if not ten:
                continue
            if p.get("kieu") == "categorical":
                lc = p.get("lua_chon") or [None]
                out[ten] = lc[0]
            else:
                lo, hi = p.get("thap", 0), p.get("cao", 0)
                mid = (lo + hi) / 2
                out[ten] = int(round(mid)) if p.get("kieu") == "int" else mid
        return out

                                                                               
    def tinh_chi_bao(self, df_1m, timeframe_map: dict = None):
                                                                                       
        self._tf_map = timeframe_map
        return df_1m

    def tinh_tin_hieu_vectorized(self, df, params: dict = None):
        import polars as pl
        tf_map = getattr(self, "_tf_map", None)
        df_sig = self.sinh_tin_hieu(df, tf_map, params or self.get_default_params())
                                                              
        if hasattr(df_sig, "clone"):          
            if "signal" not in df_sig.columns:
                df_sig = df_sig.with_columns(pl.lit(0).cast(pl.Int64).alias("signal"))
            df_sig = df_sig.with_columns(
                pl.col("signal").diff().fill_null(0).cast(pl.Int64).alias("entry_signal")
            )
        else:          
            if "signal" not in df_sig.columns:
                df_sig["signal"] = 0
            df_sig["entry_signal"] = df_sig["signal"].diff().fillna(0).astype(int)
        return df_sig

    def _tin_hieu_bar_cuoi(self, df_1m, tf_map, params):
        df_ind = self.tinh_chi_bao(df_1m, tf_map)
        df_sig = self.tinh_tin_hieu_vectorized(df_ind, params)
        if df_sig is None:
            return 0
        try:
            if hasattr(df_sig, "clone"):
                return 0 if df_sig.is_empty() else int(df_sig["signal"].item(-1))
            return 0 if df_sig.empty else int(df_sig["signal"].iloc[-1])
        except Exception:
            return 0

    def phan_tich_live(self, symbol, df_1m, df_3m, df_5m, df_15m, df_30m,
                       df_1h, df_4h, df_1d, MarketSnapshot=None, params: dict = None):
        tf_map = {"3m": df_3m, "5m": df_5m, "15m": df_15m, "30m": df_30m,
                  "1h": df_1h, "4h": df_4h, "1d": df_1d}
        sig = self._tin_hieu_bar_cuoi(df_1m, tf_map, params)
        if sig == 1:
            return "buy", 25, f"[{self.name}] tín hiệu LONG"
        if sig == -1:
            return "sell", -25, f"[{self.name}] tín hiệu SHORT"
        return None, 0, f"[{self.name}] không có tín hiệu"

    def thoat_live(self, df_1m, df_3m, df_5m, df_15m, df_30m,
                   df_1h, df_4h, df_1d, MarketSnapshot=None, params: dict = None):
        tf_map = {"3m": df_3m, "5m": df_5m, "15m": df_15m, "30m": df_30m,
                  "1h": df_1h, "4h": df_4h, "1d": df_1d}
        sig = self._tin_hieu_bar_cuoi(df_1m, tf_map, params)
        if sig == -1:
            return "sell", 25, f"[{self.name}] đóng LONG (đảo chiều SHORT)"
        if sig == 1:
            return "buy", -25, f"[{self.name}] đóng SHORT (đảo chiều LONG)"
        return None, 0, "giữ lệnh"
