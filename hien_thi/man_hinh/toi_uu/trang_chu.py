"""toi_uu/trang_chu.py — Mixin UI trang chủ (home page) cho DashboardToiUu.

Được tách ra để giảm độ dài dashboard.py. Import bởi dashboard.py qua đa kế thừa:
    class DashboardToiUu(TrangChuMixin, QWidget): ...

Lưu ý: ActionRow, PipelineProgressWidget, SparklineWidget được lazy-import trong method
để tránh circular import với dashboard.py nơi chúa các class đó.
"""
import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath

from hien_thi.duong_dan import PROJECT_ROOT, ASSETS_DIR
from utils.doc_cau_hinh import lay_cau_hinh_giao_dich
from .theme import Theme


def _get_widgets():
    """Lazy import widgets để tránh circular import."""
    from hien_thi.man_hinh.toi_uu import dashboard as _dash
    return _dash.ActionRow, _dash.PipelineProgressWidget, _dash.SparklineWidget, _dash.CustomIconWidget



def _safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


                                                                                                     
_RECENT_COL_TITLES = ["Tên chiến lược", "Trạng thái", "Giai đoạn", "Hiệu suất (30D)", "Cập nhật"]
_RECENT_COL_STRETCH = [4, 2, 3, 3, 3]
_RECENT_ROW_MARGINS = (12, 7, 12, 7)
_RECENT_COL_SPACING = 14


class TrangChuMixin:
    """Mixin cung cấp toàn bộ phương thức UI trang chủ cho DashboardToiUu."""

                                                                                
    def _ten_nguoi_dung(self):
        """Tên hiển thị lấy từ config giao dịch (mặc định 'P. Vinh' nếu thiếu)."""
        try:
            ten = (lay_cau_hinh_giao_dich() or {}).get("ten_nguoi_dung", "")
        except Exception:
            ten = ""
        return (ten or "").strip() or "P. Vinh"

                                                                                
    def _build_home_page(self):
        """Trang chủ mới thiết kế lại theo phong cách chuyên nghiệp."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {Theme.BG}; }}")

        container = QWidget()
        container.setStyleSheet(f"background-color: {Theme.BG};")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(30, 24, 30, 24)
        outer.setSpacing(20)

                                                
        outer.addLayout(self._create_header_section())

                                                                                        
        stats_lay = QHBoxLayout()
        stats_lay.setSpacing(12)
        stats_lay.addWidget(self._create_stat_card("Chiến lược", "—", "", "📊", "#9C5BFF"))
        stats_lay.addWidget(self._create_stat_card("Backtest", "—", "", "⚙", "#2196F3"))
        stats_lay.addWidget(self._create_stat_card("Realtime Bots", "—", "", "🤖", "#089981"))
        stats_lay.addWidget(self._create_stat_card("Winrate cao nhất", "—", "", "🏆", "#C8AA6E"))
        stats_lay.addWidget(self._create_stat_card("Lợi nhuận (30D)", "—", "", "💰", "#089981"))
        outer.addLayout(stats_lay)

                                                          
        mid_lay = QHBoxLayout()
        mid_lay.setSpacing(16)
        mid_lay.addWidget(self._create_pipeline_card(), 2)
        mid_lay.addWidget(self._create_author_card(), 1)
        outer.addLayout(mid_lay)

                                                                
        outer.addWidget(self._create_recent_strategies_card())

        outer.addStretch()
        
                                                          
        from PyQt6.QtCore import QTimer
        self.home_refresh_timer = QTimer(self)
        self.home_refresh_timer.setInterval(5000)
        self.home_refresh_timer.timeout.connect(self._lam_moi_trang_chu)
        self.home_refresh_timer.start()
        
        scroll.setWidget(container)
        return scroll

                                                                                
    def _create_header_section(self):
        lay = QHBoxLayout()
        lay.setSpacing(24)

                                     
        left = QVBoxLayout()
        left.setSpacing(10)
        left.setContentsMargins(0, 4, 0, 4)

        lbl_welcome = QLabel(f"Xin chào, {self._ten_nguoi_dung()}! 👋")
        lbl_welcome.setStyleSheet("color: #787B86; font-size: 22px; font-weight: bold; background: transparent;")
        self.lbl_welcome = lbl_welcome                                                      

        lbl_plat = QLabel("Kairos Quant Platform")
        lbl_plat.setStyleSheet("color: #FFFFFF; font-size: 43px; font-weight: bold; background: transparent;")

        lbl_sub = QLabel("Thiết kế – Tối ưu – Backtest – Triển khai chiến lược")
        lbl_sub.setStyleSheet("color: #787B86; font-size: 22px; background: transparent;")

                                                                         
                                                                                        
        ac = Qt.AlignmentFlag.AlignLeft
        left.addStretch()
        left.addWidget(lbl_welcome, 0, ac)
        left.addWidget(lbl_plat, 0, ac)
        left.addWidget(lbl_sub, 0, ac)
        left.addSpacing(24)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)

        btn_new = QPushButton("+ Tạo chiến lược mới")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setFixedHeight(42)
        btn_new.setStyleSheet(f"""
            QPushButton {{
                color: #131722;
                background-color: {Theme.ACCENT};
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                padding: 0px 18px;
            }}
            QPushButton:hover {{
                background-color: #E2C085;
            }}
        """)
        btn_new.clicked.connect(lambda: self.di_toi_man("toi_uu"))

        btn_import = QPushButton("📥 Nhập dữ liệu")
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.setFixedHeight(42)
        btn_import.setStyleSheet(f"""
            QPushButton {{
                color: #D1D4DC;
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
                padding: 0px 18px;
            }}
            QPushButton:hover {{
                background-color: {Theme.GRID};
            }}
        """)
        btn_import.clicked.connect(lambda: self._switch_left_tab(3))
        btn_import.clicked.connect(lambda: self.di_toi_man("toi_uu"))

        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_import)
        btn_row.addStretch()
        left.addLayout(btn_row)
        left.addStretch()

        left_w = QWidget()
        left_w.setStyleSheet("background: transparent;")
        left_w.setLayout(left)

                                                                          
        right_box = QFrame()
        right_box.setMinimumHeight(150)
                                                                                          
        right_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_box.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        right_lay = QVBoxLayout(right_box)
        right_lay.setContentsMargins(20, 14, 20, 14)
        right_lay.setSpacing(10)

        cfg_title = QLabel("Cấu hình phiên hiện tại")
        cfg_title.setStyleSheet("color: #787B86; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        right_lay.addWidget(cfg_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(0)

        items = self._lay_cau_hinh_header()
        for idx, (label, val, val_color) in enumerate(items):
            cell = QVBoxLayout()
            cell.setSpacing(2)
            lbl_title = QLabel(label)
            lbl_title.setStyleSheet("color: #787B86; font-size: 10px; background: transparent; border: none;")
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet(f"color: {val_color}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            cell.addWidget(lbl_title)
            cell.addWidget(lbl_val)
            cell_w = QWidget()
            cell_w.setStyleSheet("background: transparent;")
            cell_w.setLayout(cell)
            grid.addWidget(cell_w, 0, idx)                              
            grid.setColumnStretch(idx, 1)
        right_lay.addLayout(grid)
        right_lay.addSpacing(10)

                                               
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background-color: {Theme.BORDER}; max-height: 1px; border: none;")
        right_lay.addWidget(div)

        eq_lbl = QLabel("Đường vốn · 30 ngày")
        eq_lbl.setStyleSheet("color: #787B86; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        right_lay.addWidget(eq_lbl)

        _, _, SparklineWidget, _ = _get_widgets()
        self.config_sparkline = SparklineWidget()
        self.config_sparkline.setMinimumHeight(72)
        self.config_sparkline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.config_sparkline.points = []                                    
        right_lay.addWidget(self.config_sparkline, 1)                                      

        lay.addWidget(left_w, 1)                                                  
        lay.addWidget(right_box, 1)                                          
        return lay

    def _lay_cau_hinh_header(self):
        """Đọc cấu hình giao dịch/ảo cho thẻ header. Thiếu trường nào → '—'."""
        try:
            from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
            cfg_t = lay_cau_hinh_giao_dich() or {}
            cfg_b = lay_cau_hinh_ao() or {}
            syms = cfg_t.get("cap_giao_dich", []) or []
            sym_txt = ", ".join(syms[:3]) + ("…" if len(syms) > 3 else "") if syms else "—"
            von = cfg_b.get("so_du_ban_dau", None)
            von_txt = f"{_safe_float(von):,.0f} USDT" if von not in (None, "", 0) else "—"
            don_bay = cfg_t.get("don_bay", None)
            don_bay_txt = f"{don_bay}x" if don_bay not in (None, "") else "—"
            nbd, nkt = cfg_b.get("ngay_bat_dau"), cfg_b.get("ngay_ket_thuc")
            period_txt = f"{nbd} → {nkt}" if nbd and nkt else "—"
            return [
                ("Symbols", sym_txt, Theme.TEXT_MAIN),
                ("Vốn ban đầu", von_txt, "#089981"),
                ("Đòn bẩy", don_bay_txt, "#2196F3"),
                ("Khoảng Backtest", period_txt, Theme.TEXT_MAIN),
            ]
        except Exception:
            return [
                ("Symbols", "—", Theme.TEXT_MAIN),
                ("Vốn ban đầu", "—", "#089981"),
                ("Đòn bẩy", "—", "#2196F3"),
                ("Khoảng Backtest", "—", Theme.TEXT_MAIN),
            ]

                                                                                
    def _create_stat_card(self, title, value, comp_text, icon_char, icon_color):
        card = QFrame()
        card.setMinimumHeight(96)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon = QLabel(icon_char)
        icon.setFixedSize(22, 22)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                background-color: {icon_color};
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 11px; font-weight: bold; background: transparent; border: none;")

        header.addWidget(icon)
        header.addWidget(lbl_title)
        header.addStretch()
        lay.addLayout(header)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 20px; font-weight: bold; background: transparent; border: none;")
        lay.addWidget(lbl_val)

        lbl_comp = QLabel(comp_text)
        if comp_text.startswith("↑") or comp_text.startswith("+"):
            lbl_comp.setStyleSheet("color: #089981; font-size: 10px; background: transparent; border: none;")
        elif comp_text.startswith("↓") or comp_text.startswith("-") or comp_text.startswith("⚠"):
            lbl_comp.setStyleSheet("color: #F23645; font-size: 10px; background: transparent; border: none;")
        else:
            lbl_comp.setStyleSheet("color: #787B86; font-size: 10px; background: transparent; border: none;")
        lay.addWidget(lbl_comp)

        if not hasattr(self, "stat_labels"):
            self.stat_labels = {}
        self.stat_labels[title] = (lbl_val, lbl_comp)

        return card

                                                                                
    def _create_pipeline_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Pipeline chiến lược")
        title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold; background: transparent; border: none;")

        header.addWidget(title)
        header.addStretch()
        lay.addLayout(header)

        steps_layout = QHBoxLayout()
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(0)                                                                     

        steps = [
            ("Dữ liệu", "Thị trường\nDữ liệu lịch sử", "database", "#9C5BFF"),
            ("Features", "Kỹ thuật\nChỉ báo", "features", "#2196F3"),
            ("Tối ưu", "Tối ưu tham số\nWalk-Forward", "toi_uu", Theme.ACCENT),
            ("Backtest", "Đánh giá hiệu suất\nKiểm định", "backtest", "#089981"),
            ("Demo", "Giả lập giao dịch\nKiểm tra thực tế", "demo", "#FF9800"),
            ("Realtime", "Giao dịch thật\nGiám sát 24/7", "realtime", "#4CAF50"),
        ]

        _, PipelineProgressWidget, _, CustomIconWidget = _get_widgets()

        for name, desc, icon_type, color in steps:
            step_box = QVBoxLayout()
            step_box.setSpacing(6)
            step_box.setContentsMargins(6, 0, 6, 0)                                             
            step_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            is_active = (name == "Tối ưu")
            border_style = "active" if is_active else None
            icon_w = CustomIconWidget(
                icon_type=icon_type,
                bg_color=color,
                is_circle=True,
                size=36,
                border_style=border_style,
                parent=None
            )

            name_lbl = QLabel(name)
            name_lbl.setWordWrap(True)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_color = Theme.TEXT_MAIN if is_active else Theme.TEXT_SUB
            font_weight = "bold" if is_active else "normal"
            name_lbl.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: {font_weight}; background: transparent; border: none;")

            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)                                                                 
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setStyleSheet("color: #787B86; font-size: 9px; background: transparent; border: none;")

            step_box.addWidget(icon_w, 0, Qt.AlignmentFlag.AlignCenter)
            step_box.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignCenter)
            step_box.addWidget(desc_lbl, 0, Qt.AlignmentFlag.AlignCenter)

            step_w = QWidget()
            step_w.setLayout(step_box)
            steps_layout.addWidget(step_w, 1)

        lay.addStretch(1)
        lay.addLayout(steps_layout)
        lay.addSpacing(6)

        progress = PipelineProgressWidget()
        lay.addWidget(progress)
        lay.addStretch(1)

        info_lay = QHBoxLayout()
        info_lay.setSpacing(6)
        info_icon = QLabel("ⓘ")
        info_icon.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 12px; background: transparent; border: none;")
        info_txt = QLabel("Bắt đầu từ Tối ưu để tìm ra tham số tốt nhất, sau đó Backtest để đánh giá và triển khai.")
        info_txt.setStyleSheet("color: #787B86; font-size: 10px; background: transparent; border: none;")
        info_lay.addWidget(info_icon)
        info_lay.addWidget(info_txt)
        info_lay.addStretch()
        lay.addLayout(info_lay)

        return card

                                                                                
    def _create_author_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

                      
        title = QLabel("Tác giả")
        title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold; background: transparent; border: none; padding-bottom: 2px;")
        lay.addWidget(title)

                                
        profile_lay = QHBoxLayout()
        profile_lay.setSpacing(12)
        
                             
        img_path = os.path.join(ASSETS_DIR, "avatar.jpg")
        avatar_lbl = QLabel()
        avatar_lbl.setFixedSize(48, 48)
        if os.path.exists(img_path):
            pix = self._create_circular_pixmap(img_path, 48)
            if pix is not None:
                avatar_lbl.setPixmap(pix)
                avatar_lbl.setStyleSheet("background: transparent; border: none;")
        if avatar_lbl.pixmap() is None:
            avatar_lbl.setText("PV")
            avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar_lbl.setStyleSheet(f"""
                QLabel {{
                    color: #FFFFFF;
                    background-color: {Theme.ACCENT};
                    border-radius: 24px;
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                }}
            """)
        profile_lay.addWidget(avatar_lbl)

                      
        name_roles = QVBoxLayout()
        name_roles.setSpacing(2)
        
        lbl_name = QLabel(self._ten_nguoi_dung())
        lbl_name.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        
        lbl_roles = QLabel("Financial Data Analyst\nML Engineer\nQuant Developer")
        lbl_roles.setWordWrap(True)
        lbl_roles.setStyleSheet("color: #FFFFFF; font-size: 10px; line-height: 14px; background: transparent; border: none;")
        
        name_roles.addWidget(lbl_name)
        name_roles.addWidget(lbl_roles)
        profile_lay.addLayout(name_roles, 1)
        lay.addLayout(profile_lay)

                              
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background-color: {Theme.BORDER}; max-height: 1px; border: none; margin: 4px 0px;")
        lay.addWidget(divider)

               
        lbl_quote = QLabel("“There is only one heroism in the world: to see the world as it is, and to love it.”")
        lbl_quote.setWordWrap(True)
        lbl_quote.setStyleSheet("color: #D2D4DC; font-size: 10px; font-style: italic; background: transparent; border: none;")
        lay.addWidget(lbl_quote)

        lbl_author_quote = QLabel("— Romain Rolland")
        lbl_author_quote.setStyleSheet("color: #787B86; font-size: 9px; font-style: italic; background: transparent; border: none;")
        lay.addWidget(lbl_author_quote)

                                                     
        lay.addStretch()
        
        btn_donate = QPushButton("⚡ Đồng hành cùng dự án")
        btn_donate.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_donate.setFixedHeight(28)
        btn_donate.setStyleSheet(f"""
            QPushButton {{
                color: #131722;
                background-color: {Theme.ACCENT};
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E2C085;
            }}
        """)
        
        def show_donation_dialog():
            from hien_thi.man_hinh.toi_uu.ung_ho import DonationDialog
            dlg = DonationDialog(self.recent_strat_container if hasattr(self, 'recent_strat_container') else None)
            dlg.exec()
            
        btn_donate.clicked.connect(show_donation_dialog)
        lay.addWidget(btn_donate)
        
        lbl_version = QLabel("Kairos v2  ·  2026")
        lbl_version.setStyleSheet("color: #555861; font-size: 9px; background: transparent; border: none; margin-top: 4px;")
        lay.addWidget(lbl_version, 0, Qt.AlignmentFlag.AlignRight)

        return card

                                                                                
    def _create_recent_strategies_card(self):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Chiến lược gần đây")
        title.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        header.addWidget(title)
        header.addStretch()
        lay.addLayout(header)

        cols = QHBoxLayout()
        cols.setContentsMargins(_RECENT_ROW_MARGINS[0], 0, _RECENT_ROW_MARGINS[2], 4)
        cols.setSpacing(_RECENT_COL_SPACING)
        hdr_style = "color: #787B86; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        for title, st in zip(_RECENT_COL_TITLES, _RECENT_COL_STRETCH):
            lbl = QLabel(title)
            lbl.setStyleSheet(hdr_style)
            cols.addWidget(lbl, st)
        lay.addLayout(cols)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background-color: {Theme.BORDER}; max-height: 1px; border: none;")
        lay.addWidget(divider)

        self.recent_strat_container = QWidget()
        self.recent_strat_container.setStyleSheet("background: transparent;")
        self.recent_strat_layout = QVBoxLayout(self.recent_strat_container)
        self.recent_strat_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_strat_layout.setSpacing(4)
        self._render_recent_strategies([])                                                   

        lay.addWidget(self.recent_strat_container)

        lay.addSpacing(6)
        btn_all = QPushButton("Xem tất cả chiến lược ➔")
        btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_all.setStyleSheet(f"""
            QPushButton {{
                color: {Theme.ACCENT};
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: bold;
                text-align: left;
                padding-left: 10px;
            }}
            QPushButton:hover {{ color: #FFFFFF; }}
        """)
        btn_all.clicked.connect(lambda: self.di_toi_man("da_luu"))
        lay.addWidget(btn_all)

        return card

    def _make_strategy_row(self, run):
        """Dựng 1 hàng chiến lược gần đây từ dict {name, mode, status, perf, time, color}."""
        row = QHBoxLayout()
        row.setContentsMargins(*_RECENT_ROW_MARGINS)
        row.setSpacing(_RECENT_COL_SPACING)

        full_name = str(run["name"])
        disp_name = full_name if len(full_name) <= 30 else full_name[:29].rstrip() + "…"
        lbl_name = QLabel(disp_name)
        if disp_name != full_name:
            lbl_name.setToolTip(full_name)                                       
        lbl_name.setStyleSheet(f"color: {Theme.TEXT_MAIN}; font-size: 12px; font-weight: bold; background: transparent; border: none;")

        lbl_mode = QLabel(run["mode"])
        lbl_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_mode.setFixedSize(76, 20)
        lbl_mode.setStyleSheet(f"QLabel {{ color: #FFFFFF; background-color: {run['color']}; border-radius: 4px; font-size: 10px; font-weight: bold; border: none; }}")

        lbl_status = QLabel(run["status"])
        lbl_status.setStyleSheet(f"color: {Theme.TEXT_SUB}; font-size: 12px; background: transparent; border: none;")

        lbl_perf = QLabel(run["perf"])
        cp = "#089981" if run["perf"].startswith("+") or "SR" in run["perf"] else "#F23645"
        lbl_perf.setStyleSheet(f"color: {cp}; font-size: 12px; font-weight: bold; background: transparent; border: none;")

        lbl_time = QLabel(run["time"])
        lbl_time.setStyleSheet("color: #787B86; font-size: 11px; background: transparent; border: none;")

        st = _RECENT_COL_STRETCH
        row.addWidget(lbl_name, st[0])
        row.addWidget(lbl_mode, st[1], Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl_status, st[2])
        row.addWidget(lbl_perf, st[3])
        row.addWidget(lbl_time, st[4])

        rw = QWidget()
        rw.setObjectName("recentRow")                                                                   
        rw.setLayout(row)
        rw.setStyleSheet(
            f"QWidget#recentRow {{ background: transparent; }}"
            f"QWidget#recentRow:hover {{ background-color: {Theme.GRID}; border-radius: 6px; }}"
        )
        return rw

    def _render_recent_strategies(self, runs):
        """Xoá & vẽ lại bảng chiến lược gần đây. Rỗng → hiển thị empty-state."""
        if not hasattr(self, "recent_strat_layout"):
            return
        while self.recent_strat_layout.count():
            item = self.recent_strat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not runs:
            empty = QLabel("Chưa có chiến lược nào — bắt đầu từ Tối ưu để tạo chiến lược đầu tiên.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #555861; font-size: 12px; background: transparent; padding: 22px 0;")
            self.recent_strat_layout.addWidget(empty)
            return
        for run in runs:
            self.recent_strat_layout.addWidget(self._make_strategy_row(run))

                                                                               
    def _lay_du_lieu_he_thong(self):
        """Truy vấn tất cả dữ liệu thực tế từ hệ thống (DuckDB, config, files, system)."""
        import json as _json
        from datetime import datetime, timedelta

        data = {
            "n_strategies": 0, "strategies_growth": "+0%",
            "n_backtests": 0, "backtests_growth": "+0%",
            "n_bots": 0, "bots_active": 0,
            "highest_winrate": "—", "highest_winrate_name": "Chưa có chiến lược",
            "profit_30d": "+0.0%", "profit_30d_growth": "↑ 0.0% so với 30 ngày trước",
            "profit_30d_color": "#787B86", "recent_runs": [], "equity_curve": [],
        }

        saved_strats = []

                       
        try:
            from toi_uu_hoa.thu_vien import danh_sach_da_luu
            saved_strats = danh_sach_da_luu() or []
                                                                               
                                                                                       
            data["n_strategies"] = len(saved_strats)
            now = datetime.now()
            one_week_ago = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)
            this_w = sum(1 for s in saved_strats if _parse_dt(s.get("ngay_luu", "")) >= one_week_ago)
            last_w = sum(1 for s in saved_strats if two_weeks_ago <= _parse_dt(s.get("ngay_luu", "")) < one_week_ago)
            if last_w > 0:
                g = (this_w - last_w) / last_w * 100
                data["strategies_growth"] = f"↑ {g:.0f}% so với tuần trước" if g >= 0 else f"↓ {abs(g):.0f}% so với tuần trước"
            else:
                data["strategies_growth"] = f"↑ {this_w} mới trong tuần"
        except Exception as e:
            print(f"[Trang chu] Lỗi đếm chiến lược: {e}", flush=True)

                   
        db_path = os.path.join(PROJECT_ROOT, "du_lieu", "kairos_warehouse.duckdb")
        con = None
        try:
            import duckdb
            if os.path.exists(db_path):
                con = duckdb.connect(db_path)
                                                                       
                try:
                    from utils.kho_du_lieu import _tao_schema
                    _tao_schema(con)
                    self._db_migrated = True
                except Exception as e:
                    print(f"[Trang chu] Lỗi khởi tạo schema: {e}", flush=True)

                tables = []
                try:
                    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
                except Exception as e:
                    print(f"[Trang chu] Lỗi đọc danh sách bảng: {e}", flush=True)

                if "backtest_run" in tables and "lenh" in tables:
                    res = con.execute("SELECT COUNT(*) FROM backtest_run WHERE chuc_nang LIKE 'backtest%'").fetchone()
                    data["n_backtests"] = res[0] if res else 0

                    res_tw = con.execute("SELECT COUNT(*) FROM backtest_run WHERE chuc_nang LIKE 'backtest%' AND ngay_chay >= (CURRENT_DATE - INTERVAL '7 days')").fetchone()
                    res_lw = con.execute("SELECT COUNT(*) FROM backtest_run WHERE chuc_nang LIKE 'backtest%' AND ngay_chay >= (CURRENT_DATE - INTERVAL '14 days') AND ngay_chay < (CURRENT_DATE - INTERVAL '7 days')").fetchone()
                    bt_tw = res_tw[0] if res_tw else 0
                    bt_lw = res_lw[0] if res_lw else 0
                    if bt_lw > 0:
                        g = (bt_tw - bt_lw) / bt_lw * 100
                        data["backtests_growth"] = f"↑ {g:.0f}% so với tuần trước" if g >= 0 else f"↓ {abs(g):.0f}% so với tuần trước"
                    else:
                        data["backtests_growth"] = f"↑ {bt_tw} mới trong tuần"

                    res_wr = con.execute("""
                        SELECT r.chuc_nang, r.symbols, COUNT(l.run_id),
                               SUM(CASE WHEN l.thang THEN 1 ELSE 0 END)*100.0/COUNT(l.run_id)
                        FROM backtest_run r JOIN lenh l ON r.run_id = l.run_id
                        GROUP BY r.run_id, r.chuc_nang, r.symbols
                        HAVING COUNT(l.run_id) >= 10 ORDER BY 4 DESC LIMIT 1
                    """).fetchone()
                    hw, hn = 0.0, "Chưa có chiến lược"
                    if res_wr:
                        hw = float(res_wr[3])
                        m = "Backtest" if "backtest" in res_wr[0] else "Realtime" if "realtime" in res_wr[0] else "Demo"
                        hn = f"{res_wr[1]} ({m})"
                    for s in saved_strats:
                        try:
                            wr = float(s.get("win_rate", 0.0))
                            if wr > hw:
                                hw, hn = wr, s.get("combo_label", s["ten"])
                        except Exception:
                            pass
                    data["highest_winrate"] = f"{hw:.1f}%" if hw > 0 else "—"
                    data["highest_winrate_name"] = hn if hw > 0 else "Chưa có dữ liệu"

                    from utils.doc_cau_hinh import lay_cau_hinh_ao
                    cfg_b = lay_cau_hinh_ao() or {}
                    von = float(cfg_b.get("so_du_ban_dau", 10000.0))
                                                                                                       
                    LIVE = ("FROM lenh l JOIN backtest_run r ON l.run_id = r.run_id "
                            "WHERE (r.chuc_nang LIKE 'realtime%' OR r.chuc_nang LIKE 'demo%')")
                    res_mt = con.execute(f"SELECT MAX(l.thoi_gian) {LIVE}").fetchone()
                    mt = res_mt[0] if res_mt and res_mt[0] else datetime.now()
                    p30 = con.execute(f"SELECT SUM(l.pnl) {LIVE} AND l.thoi_gian >= CAST(? AS TIMESTAMP) - INTERVAL '30 days' AND l.thoi_gian <= CAST(? AS TIMESTAMP)", [mt, mt]).fetchone()
                    p30v = float(p30[0]) if p30 and p30[0] else 0.0
                    pp = (p30v / von) * 100
                    data["profit_30d"] = f"{pp:+.1f}%"
                    data["profit_30d_color"] = "#089981" if pp >= 0 else "#F23645"
                    pp30 = con.execute(f"SELECT SUM(l.pnl) {LIVE} AND l.thoi_gian >= CAST(? AS TIMESTAMP) - INTERVAL '60 days' AND l.thoi_gian < CAST(? AS TIMESTAMP) - INTERVAL '30 days'", [mt, mt]).fetchone()
                    pp30v = float(pp30[0]) if pp30 and pp30[0] else 0.0
                    diff = pp - (pp30v / von * 100)
                    data["profit_30d_growth"] = f"↑ {diff:+.1f}% so với 30 ngày trước" if diff >= 0 else f"↓ {abs(diff):.1f}% so với 30 ngày trước"

                                                                                                        
                    eq_rows = con.execute(
                        f"SELECT CAST(l.thoi_gian AS DATE) d, SUM(l.pnl) {LIVE} "
                        "AND l.thoi_gian >= CAST(? AS TIMESTAMP) - INTERVAL '30 days' AND l.thoi_gian <= CAST(? AS TIMESTAMP) "
                        "GROUP BY d ORDER BY d", [mt, mt]
                    ).fetchall()
                    cum = 0.0
                    for _d, _p in eq_rows:
                        cum += float(_p) if _p else 0.0
                        data["equity_curve"].append(cum)

                                                                                             
                                                                                            
                    rows = con.execute("""
                        SELECT r.run_id, r.chuc_nang, r.symbols, r.ngay_chay, SUM(l.pnl),
                               MAX(l.chien_luoc), r.ten_chien_luoc
                        FROM backtest_run r LEFT JOIN lenh l ON r.run_id = l.run_id
                        GROUP BY r.run_id, r.chuc_nang, r.symbols, r.ngay_chay, r.ten_chien_luoc
                        ORDER BY r.ngay_chay DESC LIMIT 5
                    """).fetchall()
                    for r in rows:
                        dt_r = r[3]; diff_t = datetime.now() - dt_r
                        if diff_t.total_seconds() < 60: tt = "Vừa xong"
                        elif diff_t.total_seconds() < 3600: tt = f"{int(diff_t.total_seconds()/60)} phút trước"
                        elif diff_t.total_seconds() < 86400: tt = f"{int(diff_t.total_seconds()/3600)} giờ trước"
                        else: tt = f"{diff_t.days} ngày trước"
                        pnl_r = float(r[4]) if r[4] else 0.0
                        ml = "Backtest" if "backtest" in r[1] else "Realtime" if "realtime" in r[1] else "Demo"
                        sl = "Đang chạy" if "realtime" in r[1] or "demo" in r[1] else "Hoàn thành"
                        cl = "#2196F3" if ml == "Backtest" else "#089981" if ml == "Realtime" else "#FF9800"
                        ten_cl = (r[6] or "").strip() or (r[5] or "").strip() or (r[2] or "—")
                        ten_cl = _ten_chien_luoc_dep(ten_cl)                                                    
                        data["recent_runs"].append({"name": ten_cl, "mode": ml, "status": sl, "perf": f"{(pnl_r/von)*100:+.1f}%", "time": tt, "color": cl})
                else:
                    hw, hn = 0.0, "Chưa có chiến lược"
                    for s in saved_strats:
                        try:
                            wr = float(s.get("win_rate", 0.0))
                            if wr > hw:
                                hw, hn = wr, s.get("combo_label", s["ten"])
                        except Exception:
                            pass
                    data["highest_winrate"] = f"{hw:.1f}%" if hw > 0 else "—"
                    data["highest_winrate_name"] = hn if hw > 0 else "Chưa có dữ liệu"
        except Exception as e:
            print(f"[Trang chu] Lỗi DuckDB: {e}", flush=True)
        finally:
            if con:
                try: con.close()
                except Exception: pass

                              
        try:
            from datetime import datetime as _dt
            for s in saved_strats[:5]:
                if not any(x["name"] == s.get("combo_label", s["ten"]) for x in data["recent_runs"]):
                    ds = s.get("ngay_luu", "")
                    tt = ds[:10] if ds else "Gần đây"
                    try:
                        dt2 = _dt.strptime(ds, "%Y-%m-%d %H:%M:%S")
                        diff2 = _dt.now() - dt2
                        tt = "Hôm nay" if diff2.total_seconds() < 86400 else f"{diff2.days} ngày trước"
                    except Exception:
                        pass
                    data["recent_runs"].append({"name": s.get("combo_label", s["ten"]), "mode": "Đã lưu", "status": s.get("verdict", "REJECT"), "perf": f"{s.get('oos_sharpe', 0.0):+.2f} SR", "time": tt, "color": "#9C5BFF"})
        except Exception as e:
            print(f"[Trang chu] Lỗi nạp thư viện: {e}", flush=True)

        data["recent_runs"] = data["recent_runs"][:5]                                           

                          
        try:
            from utils.doc_cau_hinh import lay_cau_hinh_giao_dich
            cfg_t = lay_cau_hinh_giao_dich() or {}
            data["n_bots"] = len(cfg_t.get("cap_giao_dich", []))
            from thuc_thi_lenh.quan_ly_lenh import lay_so_bot_dang_chay
            data["bots_active"] = lay_so_bot_dang_chay("realtime")
        except Exception as e:
            print(f"[Trang chu] Lỗi bot realtime: {e}", flush=True)
            data["n_bots"] = 0; data["bots_active"] = 0

        return data

                                                                               
    def _lam_moi_trang_chu(self):
        """Cập nhật toàn bộ các chỉ số và bảng trên Trang chủ từ dữ liệu thực tế."""
                                                          
        if hasattr(self, "outer_stack") and hasattr(self, "_home_page"):
            if self.outer_stack.currentWidget() != self._home_page:
                return

                                                                    
        if hasattr(self, "lbl_welcome"):
            self.lbl_welcome.setText(f"Xin chào, {self._ten_nguoi_dung()}! 👋")

        try:
            sys_data = self._lay_du_lieu_he_thong()
        except Exception as e:
            print(f"[Trang chu] Lỗi nạp hệ thống: {e}", flush=True)
            return

                       
        for title, key_val, key_comp in [
            ("Chiến lược", "n_strategies", "strategies_growth"),
            ("Backtest", "n_backtests", "backtests_growth"),
            ("Realtime Bots", "n_bots", "bots_active"),
            ("Winrate cao nhất", "highest_winrate", "highest_winrate_name"),
            ("Lợi nhuận (30D)", "profit_30d", "profit_30d_growth"),
        ]:
            labels = self.stat_labels.get(title)
            if not labels:
                continue
            lbl_val, lbl_comp = labels
            if title == "Realtime Bots":
                                                                                                 
                running = sys_data["bots_active"]
                configured = sys_data["n_bots"]
                lbl_val.setText(str(running))
                lbl_comp.setText(f"● {configured} cặp đã cấu hình")
                color = "#089981" if running > 0 else "#787B86"
                lbl_comp.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent; border: none;")
            elif title == "Lợi nhuận (30D)":
                lbl_val.setText(sys_data[key_val])
                lbl_val.setStyleSheet(f"color: {sys_data['profit_30d_color']}; font-size: 20px; font-weight: bold; background: transparent; border: none;")
                lbl_comp.setText(sys_data[key_comp])
                color = "#089981" if "↑" in sys_data[key_comp] else "#F23645"
                lbl_comp.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent; border: none;")
            else:
                lbl_val.setText(str(sys_data[key_val]))
                lbl_comp.setText(str(sys_data[key_comp]))
                v = str(sys_data[key_comp])
                if "↓" in v or ("-" in v and "↑" not in v) or "✗" in v:
                    lbl_comp.setStyleSheet("color: #F23645; font-size: 10px; background: transparent; border: none;")
                elif "↑" in v or "+" in v or "✓" in v:
                    lbl_comp.setStyleSheet("color: #089981; font-size: 10px; background: transparent; border: none;")
                else:
                    lbl_comp.setStyleSheet("color: #787B86; font-size: 10px; background: transparent; border: none;")

                                                                          
        self._render_recent_strategies(sys_data.get("recent_runs", []))

                                                                         
        if hasattr(self, "config_sparkline"):
            self.config_sparkline.points = sys_data.get("equity_curve", []) or []
            self.config_sparkline.update()



    def _create_circular_pixmap(self, file_path, size=24):
        try:
            original_pixmap = QPixmap(file_path)
            if original_pixmap.isNull():
                return None
            target = QPixmap(size, size)
            target.fill(Qt.GlobalColor.transparent)
            painter = QPainter(target)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            scaled = original_pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (size - scaled.width()) / 2
            y = (size - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.end()
            return target
        except Exception:
            return None

                                                                                
    def _open_doc(self):
        """Mở tài liệu hướng dẫn kỹ thuật chi tiết."""
        doc_path = os.path.join(PROJECT_ROOT, "tai_lieu_chi_tiet.md")
        if not os.path.exists(doc_path):
            doc_path = os.path.join(PROJECT_ROOT, "README.md")
        try:
            os.startfile(doc_path)
        except Exception as e:
            self.lbl_status.setText(f"Không thể mở tài liệu: {e}")

    def _open_support(self):
        """Hiển thị thông tin hỗ trợ."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Hỗ trợ - Support",
            "Kairos Quant System v2\n\nTác giả: P. Vinh\nEmail liên hệ: ppvinh1513@gmail.com\nTelegram: @pvinh_quant")

    def _open_forum(self):
        """Mở link forum/repository."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://github.com/PVinh-Quant/Kairos-v2"))

    def _open_api_keys(self):
        """Mở file cấu hình API keys hoặc config."""
        cfg_path = os.path.join(PROJECT_ROOT, "config", "tai_khoan_api.json")
        if os.path.exists(cfg_path):
            try:
                os.startfile(cfg_path)
            except Exception as e:
                self.lbl_status.setText(f"Không thể mở API keys: {e}")
        else:
            self.lbl_status.setText("Không tìm thấy file cấu hình API keys.")


def _parse_dt(date_str):
    """Parse datetime string, trả về datetime.min nếu lỗi."""
    from datetime import datetime
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        from datetime import datetime as _dt
        return _dt.min


import re as _re

_TF_TOKEN = _re.compile(r"^\d+[smhdwSMHDW]$")                                            


def _ten_chien_luoc_dep(raw):
    """Đổi slug kỹ thuật (vd 'rsi_5m__and_p1__sh_1.084__rt_..') sang nhãn 'RSI@5m + MACD@15m'.

    Tái dựng đúng định dạng combo_label để các hàng đồng bộ với hàng từ thư viện.
    Tên không nhận diện được (symbol, plugin lạ) thì giữ nguyên/viết hoa nhẹ.
    """
    raw = str(raw or "").strip()
    if not raw or raw == "—":
        return raw or "—"
                                                                            
    try:
        from toi_uu_hoa.thu_vien import parse_filename_metadata
        base = parse_filename_metadata(raw)["name"] or raw
    except Exception:
        base = raw
                                                                 
    base = _re.sub(r"^plugin__", "", base)
    base = _re.sub(r"__(and|or)_p\d+$", "", base)
                                                                                     
    tokens = [t for t in _re.split(r"_+", base) if t]
    if not tokens:
        return raw
    parts, cur = [], []
    for tok in tokens:
        if _TF_TOKEN.match(tok) and cur:
            parts.append(f"{'_'.join(cur).upper()}@{tok}")
            cur = []
        else:
            cur.append(tok)
    if cur:                                                                      
        parts.append("_".join(cur).upper())
    return " + ".join(parts) if parts else raw
