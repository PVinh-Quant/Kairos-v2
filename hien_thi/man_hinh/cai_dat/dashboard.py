"""
hien_thi/man_hinh/cai_dat/dashboard.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Màn CÀI ĐẶT — chỉnh các tham số trong thư mục config/ ngay trên UI.

• Mỗi field tương ứng 1 tham số trong file config (loại widget suy ra theo kiểu dữ
  liệu thực tế: int → SpinBox, float → DoubleSpinBox, list → ô phân cách dấu phẩy…).
• "Lưu thay đổi" ghi thẳng vào file (YAML giữ nguyên comment, JSON giữ Unicode).
• "Mở file" mở file gốc bằng trình soạn thảo mặc định để chỉnh chi tiết hơn.

Màn này được đăng ký trong `hien_thi.dang_ky_man_hinh.MAN_HINH` → tự thành 1 tab.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont

from hien_thi.giao_dien.theme import Theme
from utils.doc_cau_hinh import (
    lay_cau_hinh_giao_dich,
    lay_cau_hinh_ao,
    lay_thong_tin_san,
    luu_cau_hinh_giao_dich,
    luu_cau_hinh_ao,
    duong_dan_config,
)


NHAN = {
    "ten_nguoi_dung": "Tên người dùng",
    "san_giao_dich_chinh": "Sàn giao dịch chính",
    "cap_giao_dich": "Cặp giao dịch (phân cách bằng dấu phẩy)",
    "von_moi_lenh_usdt": "Vốn mỗi lệnh (USDT)",
    "don_bay": "Đòn bẩy",
    "max_lenh_cho_phep": "Số lệnh tối đa cho phép",
    "cooldown_nen": "Cooldown sau khi đóng vị thế (số nến)",
    "so_du_ban_dau": "Số dư ban đầu (USDT)",
    "so_luong_luong": "Số luồng (backtest đa luồng)",
    "ngay_bat_dau": "Ngày bắt đầu (YYYY-MM-DD)",
    "ngay_ket_thuc": "Ngày kết thúc (YYYY-MM-DD)",
    "phi_giao_dich": "Phí giao dịch",
    "do_truot_gia": "Độ trượt giá (slippage)",
}


class ManHinhCaiDat(QWidget):
    """Tab Cài đặt: form chỉnh tham số config + ghi thẳng vào file."""

    def __init__(self):
        super().__init__()
        self.phien = None
        self.setStyleSheet(f"background: {Theme.BG};")
        self._fields = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {Theme.BG}; }}")
        body = QWidget()
        body.setStyleSheet(f"background-color: {Theme.BG};")
        self._body_lay = QVBoxLayout(body)
        self._body_lay.setContentsMargins(28, 22, 28, 24)
        self._body_lay.setSpacing(18)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self.lbl_status = QLabel("Sẵn sàng.")
        self._status_css(Theme.TEXT_SUB)
        root.addWidget(self.lbl_status)

        self._tai_lai()

    def gan_phien(self, phien):
        """Hook bus phiên (shell gọi khi gắn màn). Màn Cài đặt không dùng bus."""
        self.phien = phien


    def _build_header(self):
        bar = QFrame()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(58)
        bar.setStyleSheet(f"QFrame#header_bar {{ background: {Theme.BG}; border: none; border-bottom: 1px solid {Theme.BORDER}; }}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(28, 0, 28, 0)

        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel("Cài đặt hệ thống")
        title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Chỉnh tham số trong config — lưu thẳng vào file")
        sub.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 12px;")
        col.addWidget(title)
        col.addWidget(sub)
        lay.addLayout(col)
        lay.addStretch()

        btn_reload = self._btn("↻ Tải lại", Theme.BORDER, Theme.TEXT_MAIN)
        btn_reload.clicked.connect(self._tai_lai)
        btn_save = self._btn("💾 Lưu thay đổi", Theme.ACCENT, "#1A1A1A")
        btn_save.clicked.connect(self._luu)
        lay.addWidget(btn_reload)
        lay.addWidget(btn_save)
        return bar


    def _tai_lai(self):
        """Đọc lại config từ đĩa và dựng lại toàn bộ form."""
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._fields = []

        gd = lay_cau_hinh_giao_dich() or {}
        ao = lay_cau_hinh_ao() or {}
        san = lay_thong_tin_san() or {}

        self._body_lay.addWidget(
            self._section_edit("Giao dịch", "cau_hinh_giao_dich.yaml", "giao_dich", gd)
        )
        self._body_lay.addWidget(
            self._section_edit("Backtest / Paper Trading", "cau_hinh_ao_config.json", "ao", ao)
        )
        self._body_lay.addWidget(
            self._section_readonly("Thông tin sàn", "thong_tin_san.yaml", san)
        )
        self._body_lay.addStretch()
        self._bao("Đã tải cấu hình từ thư mục config/.", loi=False, neutral=True)

    def _section_edit(self, tieu_de, ten_file, cfg_id, data):
        card, grid = self._card(tieu_de, ten_file)
        for r, (key, val) in enumerate(data.items()):
            lbl = QLabel(NHAN.get(key, key))
            lbl.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 13px;")
            w = self._editor_for(val)
            self._fields.append((cfg_id, key, w, val))
            grid.addWidget(lbl, r, 0)
            grid.addWidget(w, r, 1)
        return card

    def _section_readonly(self, tieu_de, ten_file, data):
        card, grid = self._card(
            tieu_de, ten_file, mota="Chỉ xem — bấm 'Mở file' để chỉnh chi tiết."
        )
        txt = QLabel(self._format_nested(data) or "(trống)")
        txt.setFont(QFont("Consolas", 10))
        txt.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 12px;")
        txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(txt, 0, 0, 1, 2)
        return card


    def _card(self, tieu_de, ten_file, mota=None):
        """Dựng 1 thẻ section, trả về (card, grid) để đổ field vào grid."""
        card = QFrame()
        card.setObjectName("cfg_card")
        card.setStyleSheet(
            f"QFrame#cfg_card {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; border-radius: 8px; }}"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(14)

        hrow = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(tieu_de)
        t.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold;")
        col.addWidget(t)
        cap = QLabel(mota or ten_file)
        cap.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px;")
        col.addWidget(cap)
        hrow.addLayout(col)
        hrow.addStretch()
        btn_open = self._btn("📂 Mở file", Theme.BORDER, Theme.TEXT_MAIN)
        btn_open.clicked.connect(lambda _=False, f=ten_file: self._mo_file(f))
        hrow.addWidget(btn_open)
        outer.addLayout(hrow)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {Theme.BORDER}; border: none;")
        outer.addWidget(line)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)
        return card, grid

    def _editor_for(self, val):
        """Tạo widget chỉnh sửa phù hợp với kiểu của giá trị config."""
        if isinstance(val, bool):
            w = QCheckBox()
            w.setChecked(val)
            w.setStyleSheet(f"QCheckBox {{ color: {Theme.TEXT_MAIN}; }}")
            return w
        if isinstance(val, int):
            w = QSpinBox()
            w.setRange(-2_000_000_000, 2_000_000_000)
            w.setValue(val)
            w.setStyleSheet(self._spin_css())
            return w
        if isinstance(val, float):
            w = QDoubleSpinBox()
            w.setDecimals(6)
            w.setRange(-1e12, 1e12)
            w.setSingleStep(0.0001)
            w.setValue(val)
            w.setStyleSheet(self._spin_css())
            return w
        if isinstance(val, (list, tuple)):
            w = QLineEdit(", ".join(str(x) for x in val))
            w.setStyleSheet(self._edit_css())
            return w
        w = QLineEdit("" if val is None else str(val))
        w.setStyleSheet(self._edit_css())
        return w

    def _doc_widget(self, w, orig):
        """Đọc giá trị widget, ép về đúng kiểu của giá trị gốc."""
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, QSpinBox):
            return int(w.value())
        if isinstance(w, QDoubleSpinBox):
            return float(w.value())
        text = w.text().strip()
        if isinstance(orig, (list, tuple)):
            return [s.strip() for s in text.split(",") if s.strip()]
        if isinstance(orig, bool):
            return text.lower() in ("true", "1", "yes", "on")
        if isinstance(orig, int):
            return int(text)
        if isinstance(orig, float):
            return float(text)
        return text


    def _luu(self):
        """Gom giá trị từ form và ghi vào từng file config."""
        gd, ao = {}, {}
        try:
            for cfg_id, key, w, orig in self._fields:
                val = self._doc_widget(w, orig)
                (gd if cfg_id == "giao_dich" else ao)[key] = val
        except ValueError as e:
            self._bao(f"⚠ Giá trị không hợp lệ: {e}", loi=True)
            return
        try:
            if gd:
                luu_cau_hinh_giao_dich(gd)
            if ao:
                luu_cau_hinh_ao(ao)
        except Exception as e:
            self._bao(f"⚠ Lỗi khi lưu: {e}", loi=True)
            return
        self._bao("✓ Đã lưu cấu hình vào thư mục config/.", loi=False)

    def _mo_file(self, ten_file):
        """Mở file config gốc bằng trình soạn thảo mặc định của hệ điều hành."""
        path = duong_dan_config(ten_file)
        if not os.path.exists(path):
            self._bao(f"⚠ Không tìm thấy {ten_file}", loi=True)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self._bao(f"Đã mở {ten_file} bằng trình soạn thảo mặc định.", loi=False, neutral=True)


    def _format_nested(self, data, indent=0):
        pad = "    " * indent
        out = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    out.append(f"{pad}{k}:")
                    out.append(self._format_nested(v, indent + 1))
                else:
                    out.append(f"{pad}{k}: {v}")
        else:
            out.append(f"{pad}{data}")
        return "\n".join(s for s in out if s)

    def _btn(self, text, bg, fg):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {Theme.BORDER}; "
            f"border-radius: 5px; padding: 7px 16px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {Theme.ACCENT}; }}"
        )
        return b

    def _spin_css(self):


        return (
            f"QAbstractSpinBox {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 22px 4px 8px; "
            f"font-size: 13px; min-width: 220px; }}"
            f"QAbstractSpinBox:hover, QAbstractSpinBox:focus {{ border: 1px solid {Theme.ACCENT}; }}"
            f"QAbstractSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; "
            f"width: 18px; border-left: 1px solid {Theme.BORDER}; border-bottom: none; background: transparent; "
            f"border-top-right-radius: 4px; }}"
            f"QAbstractSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; "
            f"width: 18px; border-left: 1px solid {Theme.BORDER}; border-top: none; background: transparent; "
            f"border-bottom-right-radius: 4px; }}"
            f"QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {Theme.BORDER}; }}"
            f"QAbstractSpinBox::up-arrow {{ image: none; border-left: 3px solid transparent; "
            f"border-right: 3px solid transparent; border-bottom: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QAbstractSpinBox::down-arrow {{ image: none; border-left: 3px solid transparent; "
            f"border-right: 3px solid transparent; border-top: 4px solid {Theme.TEXT_SUB}; width: 0; height: 0; }}"
            f"QAbstractSpinBox::up-arrow:hover {{ border-bottom-color: {Theme.TEXT_MAIN}; }}"
            f"QAbstractSpinBox::down-arrow:hover {{ border-top-color: {Theme.TEXT_MAIN}; }}"
        )

    def _edit_css(self):
        return (
            f"QLineEdit {{ background: {Theme.BG}; color: {Theme.TEXT_MAIN}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 5px 8px; "
            f"font-size: 13px; min-width: 300px; }}"
            f"QLineEdit:hover, QLineEdit:focus {{ border-color: {Theme.ACCENT}; }}"
        )

    def _status_css(self, color):
        self.lbl_status.setStyleSheet(
            f"color: {color}; background: {Theme.BG}; border-top: 1px solid {Theme.BORDER}; "
            f"padding: 7px 18px; font-size: 12px;"
        )

    def _bao(self, msg, loi=False, neutral=False):
        color = Theme.TEXT_SUB if neutral else (Theme.LOSS if loi else Theme.WIN)
        self._status_css(color)
        self.lbl_status.setText(msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    win = ManHinhCaiDat()
    win.resize(960, 760)
    win.show()
    sys.exit(app.exec())
