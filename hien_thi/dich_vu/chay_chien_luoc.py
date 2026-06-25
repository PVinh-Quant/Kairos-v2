"""
hien_thi/dich_vu/chay_chien_luoc.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ChienLuocActiveMixin — cho các MÀN VẬN HÀNH (Realtime / Demo / Backtest).

Nhận "chiến lược đang nghiên cứu" từ bus phiên (PhienNghienCuu.active_strategy) và,
khi người dùng bấm chạy, GHI ĐÈ engine bar-to-bar để chạy ĐÚNG bộ tham số đó thay vì
quét theo config. Dùng khi mở màn lẻ từ thư viện "Đã lưu" (mỗi màn 1 tiến trình riêng).

Cách dùng:
    class MainDashboard_realtime(ChienLuocActiveMixin, QMainWindow): ...
    # trong handler bắt đầu, NGAY TRƯỚC worker.start():
    self._ap_dung_chien_luoc_ghi_de()

Mixin KHÔNG định nghĩa __init__ (tránh đụng vòng khởi tạo của QMainWindow); mọi thuộc
tính đọc qua getattr với mặc định an toàn.
"""

from utils.log import logger


class ChienLuocActiveMixin:
    """Trộn vào màn vận hành để nhận + áp dụng chiến lược active từ bus phiên."""

    def gan_phien(self, phien):
        """Bus phiên được tiêm: lắng nghe chiến lược active; nạp luôn nếu bus đã có."""
        self.phien = phien
        if phien is None:
            return
        try:
            phien.strategy_changed.connect(self._nhan_chien_luoc)
        except Exception:                
            pass
        if getattr(phien, "active_strategy", None):
            self._nhan_chien_luoc(phien.active_strategy)

    def _nhan_chien_luoc(self, result):
        """Lưu chiến lược active (best_params + nhãn). KHÔNG tự chạy — đợi người dùng bấm."""
        if not result:
            self._active_strategy = None
            self._active_strategy_label = ""
        else:
            self._active_strategy = result.get("best_params", result)
            self._active_strategy_label = (
                result.get("combo_label") or result.get("strategy_key") or "active"
            )
        self._cap_nhat_nhan_chien_luoc()

    def _cap_nhat_nhan_chien_luoc(self):
        """Hiện nhãn chiến lược active trên toolbar (nếu có) hoặc ô trạng thái."""
        txt = (
            f"⚙ Chiến lược: {self._active_strategy_label}"
            if getattr(self, "_active_strategy", None)
            else "⚙ Chiến lược: (theo config)"
        )
        lbl = getattr(self, "lbl_chien_luoc", None)
        tb = getattr(self, "toolbar", None)
        if lbl is None and tb is not None:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel()
            lbl.setStyleSheet(
                "color: #C8AA6E; font-weight: bold; padding: 0 12px; background: transparent;"
            )
            self.lbl_chien_luoc = lbl
            try:
                tb.addWidget(lbl)
            except Exception:                
                pass
        if lbl is not None:
            lbl.setText(txt)
        else:
            sb = getattr(self, "lbl_status", None)
            if sb is not None:
                sb.setText(txt)

    def _ap_dung_chien_luoc_ghi_de(self):
        """NGAY TRƯỚC khi chạy: nếu có chiến lược active → ép engine chỉ dùng đúng nó."""
        cfg = getattr(self, "_active_strategy", None)
        if not cfg:
            return
        try:
            from chien_luoc.quan_ly_chien_luoc_bar_to_bar import dat_chien_luoc_ghi_de
            dat_chien_luoc_ghi_de(cfg, getattr(self, "_active_strategy_label", "active"))
        except Exception as e:                
            logger.error(f"[man vận hành] Lỗi áp dụng ghi đè chiến lược: {e}")
