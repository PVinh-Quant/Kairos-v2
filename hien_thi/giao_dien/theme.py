"""
hien_thi/giao_dien/theme.py — THEME DÙNG CHUNG (1 nguồn màu duy nhất).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hợp nhất từ các bản Theme rải rác (toi_uu, bieu_do_nen). Mọi màn hình import
TỪ ĐÂY để giao diện đồng nhất:

    from hien_thi.giao_dien.theme import Theme

`bang_mau.py` (hằng số màu cho demo/realtime) cũng nên quy về Theme này.
"""


class Theme:
    """Bảng màu dark-glass dùng chung cho toàn lớp hiển thị."""

    BG = "#0e0e0e"
    CARD = "#141414"
    CARD_ALT = "#101317"
    BORDER = "#2A2E39"
    GRID = "#1E222D"
    TEXT_MAIN = "#D1D4DC"
    TEXT_SUB = "#787B86"
    WIN = "#089981"
    LOSS = "#F23645"
    ACCENT = "#C8AA6E"
    ENTRY = "#2962FF"
    EXIT = "#FF9800"
    PURPLE = "#9C5BFF"
    NEUTRAL = "#3A3F4B"
    TRADE_LINE = "#4c525e"


__all__ = ["Theme"]
