"""
hien_thi/app/ung_dung.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vỏ ứng dụng: dựng cửa sổ chính (QMainWindow) với 1 tab cho mỗi màn hình khai báo
trong registry, rồi khởi chạy vòng lặp Qt.

Cách thêm tab mới: KHÔNG sửa file này — chỉ thêm 1 entry vào
`hien_thi.dang_ky_man_hinh.MAN_HINH`. Thứ tự tab = thứ tự entry.
"""

import sys
import os

from hien_thi import danh_sach_man_hinh, lay_lop
from hien_thi.duong_dan import ASSETS_DIR

def _load_rounded_icon(file_path, size=256, radius=40):
    from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QIcon
    from PyQt6.QtCore import Qt
    try:
        original = QPixmap(file_path)
        if original.isNull():
            return QIcon()
        target = QPixmap(size, size)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(path)
        scaled = original.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
        painter.end()
        return QIcon(target)
    except Exception:
        return QIcon()


_QSS_CUA_SO = """
    QMainWindow  { background-color: #0B0E14; }
    QTabWidget::pane { border: 1px solid #2A2E39; }
    QTabBar::tab {
        background: #131722; color: #787B86;
        padding: 10px 24px; font-size: 13px;
    }
    QTabBar::tab:selected { background: #1E2230; color: #D1D4DC; }
    QTabBar::tab:hover    { color: #D1D4DC; }
"""


def _tiem_phien(widget, phien):
    """Tiêm bus `phien` vào 1 màn hình: đặt thuộc tính + gọi hook nếu màn có.

    Màn hình ĐỌC qua `self.phien` (luôn có), hoặc override `gan_phien(self, phien)`
    để subscribe ngay lúc gắn. Màn chưa quan tâm bus thì không cần làm gì.
    """
    widget.phien = phien
    gan = getattr(widget, "gan_phien", None)
    if callable(gan):
        gan(phien)


def tao_cua_so(phien=None):
    """Dựng và trả về cửa sổ chính (chưa show).

    Vỏ app = màn TỐI ƯU làm chính (`DashboardToiUu`): header của nó là nav toàn cục,
    các màn khác (Realtime/Demo/Backtest/Biểu đồ nến) + Trang chủ là trang con. KHÔNG
    còn QTabWidget — thêm/bớt màn vẫn chỉ sửa registry `MAN_HINH`.

    `phien` (PhienNghienCuu): bus trạng thái dùng chung, tiêm vào shell (shell tự tiêm
    tiếp vào các màn con khi điều hướng tới).
    """
    from PyQt6.QtWidgets import QMainWindow
    from hien_thi.dich_vu.phien_nghien_cuu import PhienNghienCuu

    cua_so = QMainWindow()
    cua_so.setWindowTitle("Kairos v2 – Analytics Dashboard")
    cua_so.resize(1440, 900)
    cua_so.setStyleSheet(_QSS_CUA_SO)


    icon_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(icon_path):
        icon = _load_rounded_icon(icon_path, 256, 40)
        from PyQt6.QtWidgets import QApplication
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.setWindowIcon(icon)
        cua_so.setWindowIcon(icon)


    if phien is None:
        phien = PhienNghienCuu(cua_so)
    cua_so.phien = phien

    shell = lay_lop("toi_uu")()
    _tiem_phien(shell, phien)
    cua_so.setCentralWidget(shell)


    phien.yeu_cau_xem_man.connect(shell.di_toi_man)

    return cua_so






_MODULE_WARMUP = [
    "chuc_nang.vectorized_backtest",
    "chuc_nang.backtest_donluong",
    "chuc_nang.chay_realtime",
    "chuc_nang.chay_demo",
]


def chay(argv=None):
    """Mở app: tạo QApplication (nếu chưa có), show cửa sổ, nạp-trước backend, chạy vòng lặp Qt."""

    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'pvinh.kairos.analytics.v2'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QThread
    import importlib

    class _WarmupBackend(QThread):
        """Nạp trước module backend nặng ở luồng nền (giảm lag lần đầu chuyển tab)."""

        def run(self):
            for ten_mod in _MODULE_WARMUP:
                try:
                    importlib.import_module(ten_mod)
                except Exception:
                    pass

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    cua_so = tao_cua_so()
    cua_so.show()

    cua_so._warmup = _WarmupBackend()
    cua_so._warmup.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(chay())
