"""toi_uu/thiet_lap_chay.py — Hộp thoại SÉT-UP DỮ LIỆU một-lần khi chạy lẻ từ thư viện.

Khi người dùng chuột phải 1 chiến lược trong thư viện "Đã lưu" → Chạy ▶ (Realtime / Demo /
Backtest / Biểu đồ nến), dialog này hiện ra để CHỌN trước bộ dữ liệu sẽ chạy:
    • Symbols  : tick chọn subset trong danh sách coin cấu hình (tránh tải HẾT coin → rất lâu).
    • Khoảng ngày: chỉ với Backtest / Biểu đồ nến (Realtime/Demo là stream live, không cần ngày).

Kết quả KHÔNG lưu vào Data Pool — chỉ dùng cho lần chạy đó (truyền cho tiến trình con qua
biến môi trường, xem DashboardToiUu._chay_man_rieng + utils.doc_cau_hinh).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QListWidget, QListWidgetItem, QDateEdit, QDialogButtonBox, QWidget,
    QAbstractItemView, QAbstractSpinBox,
)
from PyQt6.QtCore import Qt, QDate

from hien_thi.giao_dien.theme import Theme


_CO_KHOANG_NGAY = {"backtest", "vectorized"}


class _DanhSachSymbol(QListWidget):
    """Danh sách coin: click BẤT KỲ đâu trên dòng đều toggle checkbox đúng 1 lần.

    Override `mousePressEvent` thay vì dùng tín hiệu `itemClicked` để khi người dùng
    bấm TRÚNG ngay ô checkbox cũng không bị double-toggle (Qt tự đảo trạng thái +
    handler đảo lần nữa = không đổi gì). Ở đây ta tự đảo 1 lần rồi nuốt sự kiện.
    """

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            it = self.itemAt(e.position().toPoint())
            if it is not None and (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                it.setCheckState(
                    Qt.CheckState.Unchecked
                    if it.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                e.accept()
                return
        super().mousePressEvent(e)


class ThietLapChayDialog(QDialog):
    """Dialog chọn symbols (+ khoảng ngày) cho 1 lần chạy lẻ từ thư viện."""

    def __init__(self, khoa, nhan, universe, default_symbols=None,
                 default_tu=None, default_den=None, parent=None):
        super().__init__(parent)
        self._khoa = khoa
        self._co_ngay = khoa in _CO_KHOANG_NGAY
        self._universe = [str(s) for s in (universe or []) if s]
        default_set = {str(s) for s in (default_symbols or [])}

        self.setWindowTitle(f"Thiết lập dữ liệu chạy · {nhan}")
        self.setMinimumWidth(420)
        self.setStyleSheet(self._css())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        tieu_de = QLabel(f"Chọn dữ liệu để chạy <b>{nhan}</b>")
        tieu_de.setStyleSheet(f"color:{Theme.TEXT_MAIN}; font-size:14px;")
        root.addWidget(tieu_de)
        goi_y = QLabel("Chỉ chọn các coin cần thiết để khỏi tải toàn bộ dữ liệu (rất lâu).")
        goi_y.setStyleSheet(f"color:{Theme.TEXT_SUB}; font-size:11px;")
        goi_y.setWordWrap(True)
        root.addWidget(goi_y)


        hang = QHBoxLayout()
        self.o_tim = QLineEdit()
        self.o_tim.setPlaceholderText("Tìm symbol…")
        self.o_tim.textChanged.connect(self._loc_danh_sach)
        hang.addWidget(self.o_tim, 1)
        self.chk_tat_ca = QCheckBox("Chọn tất cả")
        self.chk_tat_ca.stateChanged.connect(self._toggle_tat_ca)
        hang.addWidget(self.chk_tat_ca)
        root.addLayout(hang)


        self.ds = _DanhSachSymbol()
        self.ds.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        self.ds.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.ds.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ds.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for sym in self._universe:
            it = QListWidgetItem(sym)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if sym in default_set else Qt.CheckState.Unchecked)
            self.ds.addItem(it)
        self.ds.itemChanged.connect(self._cap_nhat_dem)
        root.addWidget(self.ds, 1)

        self.lbl_dem = QLabel()
        self.lbl_dem.setStyleSheet(f"color:{Theme.ACCENT}; font-size:11px;")
        root.addWidget(self.lbl_dem)


        if self._co_ngay:
            hang_ngay = QHBoxLayout()
            hang_ngay.setSpacing(8)
            hang_ngay.addWidget(self._nhan("Từ ngày:"))
            self.ngay_tu = self._o_ngay(self._parse_ngay(default_tu, QDate.currentDate().addDays(-30)))
            hang_ngay.addWidget(self.ngay_tu)
            hang_ngay.addSpacing(14)
            hang_ngay.addWidget(self._nhan("Đến ngày:"))
            self.ngay_den = self._o_ngay(self._parse_ngay(default_den, QDate.currentDate()))
            hang_ngay.addWidget(self.ngay_den)
            hang_ngay.addStretch(1)
            root.addLayout(hang_ngay)


        nut = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        nut.button(QDialogButtonBox.StandardButton.Ok).setText("Chạy")
        nut.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        nut.accepted.connect(self._xac_nhan)
        nut.rejected.connect(self.reject)
        root.addWidget(nut)

        self._cap_nhat_dem()


    def _nhan(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{Theme.TEXT_SUB}; font-size:11px;")
        return lbl

    def _o_ngay(self, ngay):
        """Ô điền ngày gọn gàng: gõ trực tiếp / lăn chuột để chỉnh, KHÔNG mũi tên."""
        de = QDateEdit()
        de.setCalendarPopup(False)
        de.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        de.setAlignment(Qt.AlignmentFlag.AlignCenter)
        de.setDisplayFormat("yyyy-MM-dd")
        de.setFixedWidth(118)
        de.setDate(ngay)
        return de

    @staticmethod
    def _parse_ngay(s, mac_dinh):
        if s:
            d = QDate.fromString(str(s), "yyyy-MM-dd")
            if d.isValid():
                return d
        return mac_dinh

    def _loc_danh_sach(self, text):
        text = (text or "").strip().lower()
        for i in range(self.ds.count()):
            it = self.ds.item(i)
            it.setHidden(bool(text) and text not in it.text().lower())

    def _toggle_tat_ca(self, state):

        muon = Qt.CheckState.Checked if state == Qt.CheckState.Checked.value else Qt.CheckState.Unchecked
        self.ds.blockSignals(True)
        for i in range(self.ds.count()):
            it = self.ds.item(i)
            if not it.isHidden():
                it.setCheckState(muon)
        self.ds.blockSignals(False)
        self._cap_nhat_dem()

    def _cap_nhat_dem(self, *_):
        n = len(self._lay_symbols_chon())
        tong = self.ds.count()
        self.lbl_dem.setText(f"Đã chọn {n}/{tong} symbol")
        self.chk_tat_ca.blockSignals(True)
        if n == 0:
            self.chk_tat_ca.setCheckState(Qt.CheckState.Unchecked)
        elif n == tong:
            self.chk_tat_ca.setCheckState(Qt.CheckState.Checked)
        else:
            self.chk_tat_ca.setCheckState(Qt.CheckState.PartiallyChecked)
        self.chk_tat_ca.blockSignals(False)

    def _lay_symbols_chon(self):
        return [
            self.ds.item(i).text()
            for i in range(self.ds.count())
            if self.ds.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _xac_nhan(self):
        if not self._lay_symbols_chon():
            self.lbl_dem.setText("⚠ Hãy chọn ít nhất 1 symbol.")
            self.lbl_dem.setStyleSheet(f"color:{Theme.LOSS}; font-size:11px;")
            return
        self.accept()

    def lay_ket_qua(self):
        """Trả dict {symbols, tu_ngay, den_ngay}. tu/den = None nếu chức năng không có ngày."""
        kq = {"symbols": self._lay_symbols_chon(), "tu_ngay": None, "den_ngay": None}
        if self._co_ngay:
            kq["tu_ngay"] = self.ngay_tu.date().toString("yyyy-MM-dd")
            kq["den_ngay"] = self.ngay_den.date().toString("yyyy-MM-dd")
        return kq

    def _css(self):
        return f"""
            QDialog {{ background: {Theme.BG}; }}
            QLineEdit {{
                background: {Theme.CARD}; color: {Theme.TEXT_MAIN};
                border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 4px 8px;
            }}
            QDateEdit {{
                background: {Theme.CARD}; color: {Theme.TEXT_MAIN};
                border: 1px solid {Theme.BORDER}; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
            QDateEdit:hover {{ border: 1px solid rgba(200,170,110,0.45); }}
            QDateEdit:focus {{ border: 1px solid {Theme.ACCENT}; }}
            QDateEdit::drop-down, QDateEdit::up-button, QDateEdit::down-button {{
                width: 0; border: none; background: transparent;
            }}
            QDateEdit::up-arrow, QDateEdit::down-arrow {{
                image: none; width: 0; height: 0;
            }}
            QListWidget {{
                background: {Theme.CARD_ALT}; color: {Theme.TEXT_MAIN};
                border: 1px solid {Theme.BORDER}; border-radius: 6px;
            }}
            QListWidget::item {{ padding: 3px 4px; }}
            QCheckBox {{ color: {Theme.TEXT_SUB}; }}
            QPushButton {{
                background: {Theme.GRID}; color: {Theme.TEXT_MAIN};
                border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 5px 16px;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT}; }}
        """
