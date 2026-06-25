"""toi_uu/thong_bao.py — Popup THÔNG BÁO DÙNG CHUNG (theme tối) cho màn Tối ưu.

Thay QMessageBox mặc định (xấu, lệch tông) bằng dialog frameless dark-glass, bo
góc, có viền nhấn + icon theo loại. Dùng chung cho:
  • cảnh báo tính năng nâng cấp (loai="nang_cap"),
  • thông báo tiến độ / kết quả thử nghiệm (loai="info"/"success"),
  • thông báo lỗi khi chạy dashboard (loai="error").

Dùng:
    from .thong_bao import hien_thong_bao
    hien_thong_bao(self, "Tiêu đề", "Nội dung", loai="error")
"""
from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from hien_thi.giao_dien.theme import Theme

                                            
_KIEU = {
    "info":     (Theme.ENTRY,  "ℹ",  "Thông báo"),
    "success":  (Theme.WIN,    "✓",  "Hoàn tất"),
    "warning":  (Theme.EXIT,   "⚠",  "Cảnh báo"),
    "error":    (Theme.LOSS,   "✕",  "Lỗi"),
    "nang_cap": (Theme.ACCENT, "★",  "Tính năng nâng cấp"),
}


def _rgba(hex_color, alpha):
    """#RRGGBB + alpha(0..1) -> 'rgba(r, g, b, a)' (tránh hex 8 chữ số kén Qt)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


class ThongBao(QDialog):
    """Dialog thông báo frameless, bo góc, viền trên nhấn theo loại + nút OK."""

    def __init__(self, parent=None, tieu_de="", noi_dung="", loai="info"):
        super().__init__(parent)
        mau, icon, td_mac_dinh = _KIEU.get(loai, _KIEU["info"])
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._drag = None

                                                           
        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"#card {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER};"
            f" border-top: 3px solid {mau}; border-radius: 10px; }}"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 170))
        card.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 20)                         
        root.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(13)

                                                        
        hang = QHBoxLayout()
        hang.setSpacing(12)
        cham = QLabel(icon)
        cham.setFixedSize(34, 34)
        cham.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cham.setStyleSheet(
            f"background: {_rgba(mau, 0.16)}; color: {mau};"
            f" border-radius: 17px; font-size: 17px; font-weight: bold;"
        )
        hang.addWidget(cham)
        tieu = QLabel(tieu_de or td_mac_dinh)
        tieu.setStyleSheet(
            f"color: {Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        hang.addWidget(tieu, 1)
        lay.addLayout(hang)

                  
        noi = QLabel(noi_dung)
        noi.setWordWrap(True)
        noi.setMinimumWidth(360)
        noi.setMaximumWidth(440)
        noi.setStyleSheet(
            f"color: {Theme.TEXT_SUB}; font-size: 12px; background: transparent;"
        )
        lay.addWidget(noi)

                               
        hang_nut = QHBoxLayout()
        hang_nut.addStretch(1)
        nut = QPushButton("OK")
        nut.setCursor(Qt.CursorShape.PointingHandCursor)
        nut.setFixedHeight(32)
        nut.setMinimumWidth(100)
        nut.setStyleSheet(
            f"QPushButton {{ background: {mau}; color: {Theme.BG}; border: none;"
            f" border-radius: 6px; font-size: 12px; font-weight: bold; padding: 0 18px; }}"
            f"QPushButton:hover {{ background: {_rgba(mau, 0.82)}; }}"
        )
        nut.clicked.connect(self.accept)
        hang_nut.addWidget(nut)
        lay.addLayout(hang_nut)

                                                                              
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None


def hien_thong_bao(parent, tieu_de, noi_dung, loai="info"):
    """Mở popup thông báo dùng chung (modal), tự canh giữa theo cửa sổ cha.

    loai: 'info' | 'success' | 'warning' | 'error' | 'nang_cap'.
    """
    dlg = ThongBao(parent, tieu_de, noi_dung, loai)
    dlg.adjustSize()
    if parent is not None:
        try:
            tam = parent.window().geometry().center()
            dlg.move(tam.x() - dlg.width() // 2, tam.y() - dlg.height() // 2)
        except Exception:
            pass
    return dlg.exec()


__all__ = ["ThongBao", "hien_thong_bao"]
