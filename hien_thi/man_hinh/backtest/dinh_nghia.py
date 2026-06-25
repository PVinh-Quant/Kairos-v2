"""backtest/dinh_nghia.py — màu (dùng chung bang_mau) + GRID + FONT cho màn Backtest."""
from PyQt6.QtGui import QFont
from hien_thi.giao_dien.bang_mau import (
    ACCENT_COLOR, BG_COLOR, CARD_BG, BORDER_COLOR,
    TEXT_MAIN, TEXT_SUB, COLOR_WIN, COLOR_LOSS,
)

GRID_COLOR = BORDER_COLOR             
FONT_TITLE = QFont("Segoe UI", 10, QFont.Weight.Bold)
FONT_VAL_BIG = QFont("Segoe UI", 20, QFont.Weight.Bold)
FONT_VAL_NORM = QFont("Segoe UI", 11, QFont.Weight.Bold)
FONT_LABEL = QFont("Segoe UI", 9)
FONT_SUB = QFont("Segoe UI", 8)

__all__ = ["ACCENT_COLOR", "BG_COLOR", "CARD_BG", "BORDER_COLOR", "TEXT_MAIN", "TEXT_SUB",
           "COLOR_WIN", "COLOR_LOSS", "GRID_COLOR", "FONT_TITLE", "FONT_VAL_BIG",
           "FONT_VAL_NORM", "FONT_LABEL", "FONT_SUB"]
