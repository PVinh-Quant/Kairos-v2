"""
hien_thi/app/chay_man.py — CHẠY 1 MÀN VẬN HÀNH LẺ TRONG TIẾN TRÌNH RIÊNG.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mở Realtime / Demo / Backtest / Biểu đồ nến như 1 CỬA SỔ ĐỘC LẬP, tách khỏi app
chính: đóng app chính thì cửa sổ này VẪN chạy (đây là 1 process Python riêng).

Thường được gọi từ thư viện "Đã lưu" (menu chuột phải → Chạy ▶) bằng subprocess:

    pythonw -m hien_thi.app.chay_man --man vectorized --chien-luoc <ten_file_thu_vien>

`--man`        : khoá registry (realtime/demo/backtest/vectorized…).
`--chien-luoc` : tên file trong thư viện (tùy chọn) — nạp & phát lên bus phiên để màn
                 tự đọc lúc gắn bus (vd Biểu đồ nến auto-nhận chiến lược).
"""

import sys
import os
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chạy 1 màn vận hành lẻ (tiến trình riêng).")
    parser.add_argument("--man", required=True, help="Khoá registry của màn (vd vectorized).")
    parser.add_argument("--chien-luoc", dest="chien_luoc", default=None,
                        help="Tên file chiến lược trong thư viện (tùy chọn).")
    args = parser.parse_args(argv)

                                                                  
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pvinh.kairos.analytics.v2")
        except Exception:
            pass

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from hien_thi import lay_lop
    from hien_thi.dich_vu.phien_nghien_cuu import PhienNghienCuu

    app = QApplication.instance() or QApplication(sys.argv)

                                                                                   
                                                                      
    phien = PhienNghienCuu()
    ten_cl = None
    if args.chien_luoc:
        try:
            from toi_uu_hoa.thu_vien import doc_chien_luoc
            payload = doc_chien_luoc(args.chien_luoc) or {}
            result = payload.get("result") or {}
            if result:
                ten_cl = args.chien_luoc
                phien.set_active_dataset(payload.get("dataset"), im_lang=True)
                phien.set_active_strategy(result, im_lang=True)
        except Exception as e:                
            print(f"[chay_man] Không nạp được chiến lược '{args.chien_luoc}': {e}", flush=True)

                                                                               
    try:
        w = lay_lop(args.man)()
    except Exception as e:                
        print(f"[chay_man] Lỗi tạo màn '{args.man}': {e}", flush=True)
        return 1
    w.phien = phien
    gan = getattr(w, "gan_phien", None)
    if callable(gan):
        gan(phien)

                                                                                    
                                                            
    if isinstance(w, QMainWindow):
        win = w
    else:
        win = QMainWindow()
        win.setCentralWidget(w)
        win.resize(1320, 860)

    nhan = _nhan_man(args.man)
    win.setWindowTitle(f"Kairos · {nhan}" + (f" · {ten_cl}" if ten_cl else ""))
    _gan_icon(win, app)
    win.show()
    return app.exec()


def _nhan_man(khoa):
    """Nhãn hiển thị của màn (từ registry); fallback = chính khoá."""
    try:
        from hien_thi import danh_sach_man_hinh
        for mh in danh_sach_man_hinh():
            if mh["khoa"] == khoa:
                return mh["nhan"]
    except Exception:                
        pass
    return khoa


def _gan_icon(win, app):
    """Gắn icon bo góc cho cửa sổ + app (best-effort)."""
    try:
        from hien_thi.duong_dan import ASSETS_DIR
        from hien_thi.app.ung_dung import _load_rounded_icon
        icon_path = os.path.join(ASSETS_DIR, "logo.png")
        if os.path.exists(icon_path):
            icon = _load_rounded_icon(icon_path, 256, 40)
            if app is not None:
                app.setWindowIcon(icon)
            win.setWindowIcon(icon)
    except Exception:                
        pass


if __name__ == "__main__":
    sys.exit(main())
