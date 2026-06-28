"""
hien_thi/thanh_phan/giao_dich.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Widget GIAO DỊCH dùng chung — tách verbatim từ phần TRÙNG (byte-identical) giữa
man_hinh/demo.py và man_hinh/realtime.py. Hành vi giữ nguyên 100%.
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QFrame, QSplitter,
    QAbstractItemView, QStatusBar, QPushButton, QSizePolicy, QDockWidget,
    QToolBar, QGridLayout, QScrollArea, QStackedWidget,
)
from PyQt6.QtGui import QColor, QFont, QPicture, QPainter, QPen, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from functools import partial
from datetime import datetime, timedelta
import pyqtgraph as pg
import polars as pl
from hien_thi.giao_dien.bang_mau import (
    ACCENT_COLOR, BG_COLOR, CARD_BG, BORDER_COLOR,
    TEXT_MAIN, TEXT_SUB, COLOR_WIN, COLOR_LOSS,
)


class DraggableCard(QDockWidget):
    def __init__(self, title, widget, parent=None):
        """Khởi tạo DockWidget có thể kéo thả với tiêu đề và widget nội dung."""
        super().__init__(title, parent)
        self.setWidget(widget)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setTitleBarWidget(None)
        self.setStyleSheet(
            f"QDockWidget {{ border: 1px solid {BORDER_COLOR}; color: {TEXT_MAIN}; }} QDockWidget::title {{ background: {CARD_BG}; padding: 6px; font-weight: bold; font-size: 11px; color: {ACCENT_COLOR}; }}"
        )





class MarketHeatmap(QWidget):

    cell_clicked = pyqtSignal(str, str)

    def __init__(self):
        """Khởi tạo heatmap grid hiển thị trạng thái đa khung cho các symbol đang mở."""
        super().__init__()
        self.layout = QGridLayout(self)
        self.layout.setSpacing(4)
        self.layout.setContentsMargins(10, 10, 10, 10)



        self.tf_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }

        self.display_headers = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        self.init_header()

    def init_header(self):
        """Vẽ hàng tiêu đề gồm cột Symbol và các cột timeframe."""

        lbl_sym = QLabel("SYMBOL")
        lbl_sym.setStyleSheet(
            f"color: {ACCENT_COLOR}; font-weight: bold; font-size: 12px;"
        )
        lbl_sym.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(lbl_sym, 0, 0)


        for col, header in enumerate(self.display_headers):
            lbl = QLabel(header)
            lbl.setStyleSheet(f"color: {TEXT_SUB}; font-weight: bold; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(lbl, 0, col + 1)

    def on_btn_click(self, symbol, tf):
        """Intermediate function to handle clicks accurately."""
        self.cell_clicked.emit(symbol, tf)

    def update_data(self, data):
        """Cập nhật heatmap theo danh sách vị thế đang mở từ data dict."""

        raw_positions = data.get("lenh_dang_chay", {})

        if not raw_positions or not isinstance(raw_positions, dict):
            self.clear_content()
            return

        open_positions = raw_positions
        symbols = sorted(list(open_positions.keys()))

        if not symbols:
            self.clear_content()
            return


        self.clear_content()


        for row_idx, sym in enumerate(symbols):
            actual_row = row_idx + 1


            btn_sym = QPushButton(sym)
            btn_sym.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_sym.setFlat(True)
            btn_sym.setStyleSheet(
                f"color: {TEXT_MAIN}; font-weight: bold; text-align: left; padding-left: 5px; border: none;"
            )


            btn_sym.clicked.connect(partial(self.on_btn_click, sym, "1m"))
            self.layout.addWidget(btn_sym, actual_row, 0)


            order_info = open_positions.get(sym)
            position_side = "buy"
            if isinstance(order_info, dict):
                position_side = order_info.get("side", "buy")


            import random

            for col_idx, header in enumerate(self.display_headers):
                tf_code = self.tf_map[header]


                is_bullish = True
                if header in ["4h", "1d"]:
                    is_bullish = position_side == "buy"
                else:

                    if position_side == "buy":
                        is_bullish = random.random() > 0.2
                    else:
                        is_bullish = random.random() < 0.2

                color = COLOR_WIN if is_bullish else COLOR_LOSS


                btn_tf = QPushButton()
                btn_tf.setFixedSize(35, 25)
                btn_tf.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_tf.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        border: 1px solid #222;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{ border: 1px solid white; }}
                """)

                btn_tf.clicked.connect(partial(self.on_btn_click, sym, tf_code))

                self.layout.addWidget(btn_tf, actual_row, col_idx + 1)


        self.layout.setRowStretch(len(symbols) + 1, 1)

    def clear_content(self):
        """Xóa toàn bộ hàng dữ liệu, giữ nguyên hàng tiêu đề (row 0)."""
        for i in reversed(range(self.layout.count())):
            item = self.layout.itemAt(i)
            if item.widget():
                idx = self.layout.getItemPosition(self.layout.indexOf(item.widget()))
                if idx[0] > 0:
                    item.widget().setParent(None)





class BieuDoGiaoDich(QWidget):
    back_clicked = pyqtSignal()

    def __init__(self):
        """Khởi tạo widget biểu đồ giá với pyqtgraph và HUD hiển thị thông tin lệnh."""
        super().__init__()


        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)


        self.lbl_info = QLabel("SẴN SÀNG")
        self.lbl_info.setFixedHeight(30)
        self.lbl_info.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MAIN};
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: bold;
                padding-left: 10px;
                background-color: {BG_COLOR};
                border-bottom: 1px solid #333;
            }}
        """)
        self.layout.addWidget(self.lbl_info)


        self.plot = pg.PlotWidget()
        self.plot.setBackground(BG_COLOR)


        self.plot.showGrid(x=False, y=True, alpha=0.2)
        self.plot.getPlotItem().hideButtons()


        self.plot.getAxis("left").setPen(None)
        self.plot.getAxis("left").setTextPen(TEXT_SUB)
        self.plot.getAxis("left").setStyle(tickTextOffset=8)


        self.plot.showAxis("bottom", False)


        self.plot.enableAutoRange(axis="y", enable=False)
        self.plot.enableAutoRange(axis="x", enable=True)


        self.plot.setClipToView(False)


        self.price_line = self.plot.plot(pen=pg.mkPen("#2962FF", width=2.5))

        self.layout.addWidget(self.plot)


        self.plot.scene().sigMouseClicked.connect(self.on_chart_clicked)


        self.current_symbol = ""
        self.current_tf = "1m"
        self.current_data = {}


    def format_price(self, v):
        """Format giá thành chuỗi không có số 0 thừa ở cuối."""
        if v is None:
            return ""
        try:
            return f"{float(v):.8f}".rstrip("0").rstrip(".")
        except:
            return str(v)


    def on_chart_clicked(self, event):
        """Xử lý click trái trên biểu đồ để phát signal quay lại heatmap."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.back_clicked.emit()


    def switch_context(self, symbol, timeframe):
        """Chuyển ngữ cảnh sang symbol và timeframe mới rồi render lại."""
        self.current_symbol = symbol
        self.current_tf = timeframe
        self.re_render()

    def update_data(self, data):
        """Cập nhật toàn bộ data dict và render lại biểu đồ."""
        self.current_data = data
        if not self.current_symbol:
            syms = list(data.get("lenh_dang_chay", {}).keys())
            if syms:
                self.current_symbol = syms[0]
        self.re_render()


    def re_render(self):
        """Vẽ lại đường giá, HUD, và các đường Entry/TP/SL từ dữ liệu hiện tại."""
        try:
            sym = self.current_symbol
            tf = self.current_tf
            key_df = f"df_{tf}"

            if not sym or sym not in self.current_data.get("data_lenh_dang_chay", {}):
                return


            df = self.current_data["data_lenh_dang_chay"][sym].get(key_df)
            if df is None:
                return
            if hasattr(df, "is_empty") and df.is_empty():
                return
            if not hasattr(df, "select"):
                df = pl.from_pandas(df)

            closes = df["close"].cast(pl.Float64).to_list()
            x = list(range(len(closes)))
            current_price = closes[-1]


            self.price_line.setData(x, closes)


            self.lbl_info.setText(f"""
                <html>
                <span style='color:{ACCENT_COLOR}; font-size:14px'>{sym}</span>
                <span style='color:#555'> | </span>
                <span style='color:{TEXT_SUB}'>{tf}</span>
                <span style='color:#555'> | </span>
                <span style='color:#2962FF; font-size:14px'>${self.format_price(current_price)}</span>
                </html>
            """)


            for item in list(self.plot.items()):
                if item is not self.price_line and not isinstance(
                    item, (pg.AxisItem, pg.ViewBox, pg.GridItem)
                ):
                    self.plot.removeItem(item)


            order = self.current_data.get("lenh_dang_chay", {}).get(sym)
            view_values = [min(closes), max(closes)]

            if order:

                if order.get("entry_price"):
                    entry = order["entry_price"]
                    view_values.append(entry)
                    line_entry = pg.InfiniteLine(
                        pos=entry,
                        angle=0,
                        pen=pg.mkPen("#E0E0E0", width=1.5, style=Qt.PenStyle.DashLine),
                    )

                    line_entry.label = pg.InfLineLabel(
                        line_entry,
                        text=f"{self.format_price(entry)}",
                        position=0.1,
                        color="#E0E0E0",
                        movable=True,
                        anchor=(0, 1),
                    )
                    self.plot.addItem(line_entry)


                if order.get("tp_price"):
                    tp = order["tp_price"]
                    view_values.append(tp)
                    line_tp = pg.InfiniteLine(
                        pos=tp,
                        angle=0,
                        pen=pg.mkPen(COLOR_WIN, width=1.5, style=Qt.PenStyle.DashLine),
                    )
                    line_tp.label = pg.InfLineLabel(
                        line_tp,
                        text=f"{self.format_price(tp)}",
                        position=0.95,
                        color=COLOR_WIN,
                        movable=True,
                        anchor=(1, 1),
                    )
                    self.plot.addItem(line_tp)


                if order.get("sl_price"):
                    sl = order["sl_price"]
                    view_values.append(sl)
                    line_sl = pg.InfiniteLine(
                        pos=sl,
                        angle=0,
                        pen=pg.mkPen(COLOR_LOSS, width=1.5, style=Qt.PenStyle.DashLine),
                    )
                    line_sl.label = pg.InfLineLabel(
                        line_sl,
                        text=f"{self.format_price(sl)}",
                        position=0.95,
                        color=COLOR_LOSS,
                        movable=True,
                        anchor=(1, 0),
                    )
                    self.plot.addItem(line_sl)


            if view_values:
                min_y = min(view_values)
                max_y = max(view_values)

                diff = max_y - min_y
                if diff == 0:
                    diff = 1


                pad = diff * 0.15


                self.plot.setYRange(min_y - pad, max_y + pad, padding=0)

        except Exception as e:
            print(f"Chart Render Error: {e}")





class MarketViewContainer(QWidget):
    def __init__(self):
        """Khởi tạo container chứa cả heatmap và chart, chuyển đổi qua lại bằng QStackedWidget."""
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()

        self.heatmap_view = QWidget()
        h_layout = QVBoxLayout(self.heatmap_view)
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.heatmap = MarketHeatmap()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.heatmap)
        scroll.setStyleSheet("background: transparent; border: none;")
        h_layout.addWidget(scroll)

        self.chart_view = BieuDoGiaoDich()

        self.stack.addWidget(self.heatmap_view)
        self.stack.addWidget(self.chart_view)
        self.layout.addWidget(self.stack)

        self.heatmap.cell_clicked.connect(self.go_to_chart)
        self.chart_view.back_clicked.connect(self.go_to_heatmap)

    def go_to_chart(self, symbol, timeframe):
        """Chuyển sang màn hình biểu đồ cho symbol và timeframe được chọn."""
        self.chart_view.switch_context(symbol, timeframe)
        self.stack.setCurrentIndex(1)

    def go_to_heatmap(self):
        """Quay lại màn hình heatmap từ biểu đồ."""
        self.stack.setCurrentIndex(0)

    def update_data(self, data):
        """Cập nhật cả heatmap và chart với dữ liệu mới nhất."""
        self.heatmap.update_data(data)
        self.chart_view.update_data(data)





class SummaryBox(QWidget):
    def __init__(self):
        """Khởi tạo widget tổng quan tài khoản với các chỉ số equity, PnL, winrate."""
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)
        self.lbl_equity_title = QLabel("VỐN SỞ HỮU (EQUITY)")
        self.lbl_equity_title.setStyleSheet(
            f"color: {TEXT_SUB}; font-size: 10px; font-weight: bold;"
        )
        self.val_equity = QLabel("$0.00")
        self.val_equity.setStyleSheet(
            f"color: {ACCENT_COLOR}; font-size: 24px; font-weight: bold;"
        )
        self.main_layout.addWidget(self.lbl_equity_title)
        self.main_layout.addWidget(self.val_equity)
        grid_frame = QFrame()
        grid_frame.setStyleSheet(f"background: {BG_COLOR}; border-radius: 4px;")
        self.grid_layout = QVBoxLayout(grid_frame)
        self.lbl_pnl = self._row("PnL Ròng", "$0.00", TEXT_MAIN)
        self.lbl_winrate = self._row("Tỷ lệ thắng", "0%", TEXT_MAIN)
        self.lbl_total = self._row("Tổng lệnh", "0", TEXT_MAIN)
        self.main_layout.addWidget(grid_frame)
        self.main_layout.addStretch()

    def _row(self, title, val, color):
        """Tạo một hàng label-value nằm ngang trong grid layout."""
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 2, 0, 2)
        t = QLabel(title)
        t.setStyleSheet(f"color: {TEXT_SUB}; font-size: 11px;")
        v = QLabel(val)
        v.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        l.addWidget(t)
        l.addStretch()
        l.addWidget(v)
        self.grid_layout.addWidget(w)
        return v

    def update_data(self, data):
        """Tính toán và cập nhật equity, PnL, winrate từ lịch sử lệnh."""
        hist = data.get("lich_su", [])
        if not hist:
            return
        df = pl.DataFrame(hist)
        sum_pnl = df.select(pl.col("pnl").sum()).item()
        total = df.height
        wins = df.filter(pl.col("pnl") > 0).height
        win_rate = (wins / total * 100) if total > 0 else 0
        self.val_equity.setText(f"${sum_pnl:,.2f}")
        self.val_equity.setStyleSheet(
            f"color: {COLOR_WIN if sum_pnl >=0 else COLOR_LOSS}; font-size: 24px; font-weight: bold;"
        )
        self.lbl_pnl.setText(f"{sum_pnl:+.2f}$")
        self.lbl_winrate.setText(f"{win_rate:.1f}%")
        self.lbl_total.setText(str(total))


class TableBase(QTableWidget):
    def __init__(self, headers):
        """Khởi tạo bảng cơ sở với style chung và logic toggle chọn dòng."""
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            f"QTableWidget {{ background-color: {CARD_BG}; color: {TEXT_MAIN}; border: none; outline: 0; }} QHeaderView::section {{ background-color: {BG_COLOR}; color: {TEXT_SUB}; border: none; padding: 5px; font-weight: bold; }} QTableWidget::item {{ padding: 5px; border-bottom: 1px solid {BORDER_COLOR}; }} QTableWidget::item:selected {{ background-color: #333; }}"
        )
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.last_row_clicked = -1
        self.cellClicked.connect(self.handle_row_click)

    def handle_row_click(self, row, col):
        """Toggle bỏ chọn dòng nếu click lại dòng đang được chọn."""
        if row == self.last_row_clicked and self.selectionModel().hasSelection():
            self.clearSelection()
            self.last_row_clicked = -1
        else:
            self.last_row_clicked = row


class PositionsTable(TableBase):
    def __init__(self):
        """Khởi tạo bảng vị thế đang mở với các cột Mã, Chiều, Giá Vào, Size, Thời Gian."""
        super().__init__(["Mã", "Chiều", "Giá Vào", "Size", "Thời Gian"])

    def refresh(self, data):
        """Làm mới bảng vị thế đang mở từ data dict."""
        pos = data.get("lenh_dang_chay", {})
        self.setRowCount(len(pos))
        for i, (sym, info) in enumerate(pos.items()):
            self.setItem(i, 0, QTableWidgetItem(str(sym)))
            item_side = QTableWidgetItem(info["side"].upper())
            item_side.setForeground(
                QColor(COLOR_WIN) if info["side"] == "buy" else QColor(COLOR_LOSS)
            )
            self.setItem(i, 1, item_side)
            self.setItem(i, 2, QTableWidgetItem(f"{info['entry_price']}"))
            self.setItem(i, 3, QTableWidgetItem(f"{info['amount']}"))
            self.setItem(i, 4, QTableWidgetItem(str(info["time"])))
            for j in range(5):
                self.item(i, j).setTextAlignment(Qt.AlignmentFlag.AlignCenter)


class HistoryTable(TableBase):
    """Bảng lịch sử giao dịch (Mã/PnL/Thời lượng/Lý do) — DÙNG CHUNG demo + realtime."""

    def __init__(self):
        """Khởi tạo bảng lịch sử giao dịch với các cột Mã, PnL, Thời Lượng, Lý Do."""
        super().__init__(["Mã", "PnL ($)", "Thời Lượng", "Lý Do"])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.verticalHeader().setDefaultSectionSize(26)
        self.setAlternatingRowColors(True)

    def refresh(self, data):
        """Làm mới bảng lịch sử 30 lệnh gần nhất từ data dict (hỗ trợ list/Polars/Pandas)."""
        hist = data.get("lich_su", [])
        if not hist:
            self.setRowCount(0)
            return


        if hasattr(hist, "to_dicts"):
            hist = hist.to_dicts()
        elif hasattr(hist, "to_dict"):
            hist = hist.to_dict("records")

        recent_data = hist[-30:][::-1]
        self.setRowCount(len(recent_data))

        for i, row in enumerate(recent_data):

            item_symbol = QTableWidgetItem(str(row.get("symbol", "--")))
            item_symbol.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, 0, item_symbol)


            try:
                pnl = float(row.get("pnl", 0.0))
            except (TypeError, ValueError):
                pnl = 0.0
            item_pnl = QTableWidgetItem(f"{pnl:+.2f} ")
            item_pnl.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if pnl > 0:
                item_pnl.setForeground(QColor(COLOR_WIN))
            elif pnl < 0:
                item_pnl.setForeground(QColor(COLOR_LOSS))
            item_pnl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.setItem(i, 1, item_pnl)


            day = str(row.get("day", ""))
            t_open = str(row.get("open_time", ""))
            t_close = str(row.get("close_time", ""))
            duration_str = "--"
            if day and t_open and t_close:
                try:
                    fmt = "%Y-%m-%d %H:%M:%S"
                    t_open_clean = t_open.split(".")[0]
                    t_close_clean = t_close.split(".")[0]
                    start_dt = datetime.strptime(f"{day} {t_open_clean}", fmt)
                    end_dt = datetime.strptime(f"{day} {t_close_clean}", fmt)
                    if end_dt < start_dt:
                        end_dt += timedelta(days=1)
                    secs = max(0, int((end_dt - start_dt).total_seconds()))
                    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
                    if h > 0:
                        duration_str = f"{h}h{m}p"
                    elif m > 0:
                        duration_str = f"{m}p"
                    else:
                        duration_str = f"{s}s"
                except Exception:
                    duration_str = t_close.split(".")[0]
            item_duration = QTableWidgetItem(duration_str)
            item_duration.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, 2, item_duration)


            reason = str(row.get("reason", "--"))
            if not reason or reason.strip() == "" or reason == "None":
                reason = "--"
            item_reason = QTableWidgetItem(reason)
            item_reason.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 3, item_reason)


class TradingBridge(QThread):
    """Cầu nối luồng nền → UI cho demo/realtime. Tham số hoá `runner` (chay_demo/chay_realtime).

    Trước đây mỗi màn có 1 bản TradingBridge gần y hệt, chỉ khác hàm chạy → gộp 1.
    """

    data_signal = pyqtSignal(dict)

    def __init__(self, runner, parent=None):
        super().__init__(parent)
        self._runner = runner

    def run(self):
        """Kết nối signal data_changed, chạy runner, đẩy snapshot cuối rồi giữ event loop."""
        from thuc_thi_lenh.quan_ly_lenh import ui_signals, get_all_data
        from utils.log import logger
        try:
            ui_signals.data_changed.connect(self.data_signal.emit)
            self._runner()
            self.data_signal.emit(get_all_data())
            self.exec()
        except Exception as e:
            logger.error(f"Bridge Error: {e}")
