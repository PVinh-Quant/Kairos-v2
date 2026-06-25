"""bieu_do_nen/tien_ich.py — helper thời gian dùng chung trong màn Biểu đồ nến."""
import pandas as pd
from datetime import datetime
def to_datetime(val):
    """Chuyển đổi giá trị datetime từ nhiều định dạng về Python datetime không timezone."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        return pd.to_datetime(val).replace(tzinfo=None)
    except:
        return None


                                            
                               
