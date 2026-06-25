import sys
import os
import time
import polars as pl
import pyqtgraph as pg
from datetime import datetime, timedelta
from pyqtgraph import QtCore, QtGui
from functools import partial
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QFrame,
    QSplitter,
    QAbstractItemView,
    QStatusBar,
    QPushButton,
    QSizePolicy,
    QDockWidget,
    QToolBar,
    QGridLayout,
    QScrollArea,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPicture, QPainter, QPen, QBrush, QLinearGradient

                            
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.log import logger
from chuc_nang.chay_realtime import chay_realtime
import thuc_thi_lenh.quan_ly_lenh as quan_ly_lenh
from thuc_thi_lenh.quan_ly_lenh import ui_signals, get_all_data

                                                                                   
                        
                                                                                   
                                                                     
from hien_thi.giao_dien.bang_mau import (
    ACCENT_COLOR, BG_COLOR, CARD_BG, BORDER_COLOR,
    TEXT_MAIN, TEXT_SUB, COLOR_WIN, COLOR_LOSS,
)
from hien_thi.thanh_phan.giao_dich import (
    DraggableCard, MarketHeatmap, BieuDoGiaoDich, MarketViewContainer,
    SummaryBox, TableBase, PositionsTable, HistoryTable, TradingBridge,
)
from hien_thi.dich_vu.chay_chien_luoc import ChienLuocActiveMixin



class MainDashboard_realtime(ChienLuocActiveMixin, QMainWindow):
    def __init__(self):
        """Khởi tạo cửa sổ dashboard realtime với layout dock và nút bắt đầu."""
        super().__init__()
        self.setWindowTitle("REALTIME")
                                                                       
        self.resize(1000, 650)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.setDockNestingEnabled(True)

                                                 
        self.toolbar = QToolBar("Realtime Controls")
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet(
            f"background: {CARD_BG}; border-bottom: 1px solid {BORDER_COLOR}; spacing: 10px; padding: 5px;"
        )
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.btn_start = QPushButton("▶ BẮT ĐẦU REALTIME")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet(
            f"background-color: {ACCENT_COLOR}; color: #FFF; font-weight: bold; padding: 6px 20px; border-radius: 4px; border: none;"
        )
        self.btn_start.clicked.connect(self.start_realtime_mode)
        self.toolbar.addWidget(self.btn_start)
                                                  

        self.market_view = MarketViewContainer()
        self.pos_table = PositionsTable()
        self.summary_widget = SummaryBox()
        self.hist_table = HistoryTable()

        self.dock_market = DraggableCard("THỊ TRƯỜNG", self.market_view)
        self.dock_pos = DraggableCard("VỊ THẾ ĐANG MỞ", self.pos_table)
        self.dock_stats = DraggableCard("TỔNG QUAN TÀI KHOẢN", self.summary_widget)
        self.dock_hist = DraggableCard("LỊCH SỬ GIAO DỊCH", self.hist_table)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_market)
        self.splitDockWidget(self.dock_market, self.dock_pos, Qt.Orientation.Vertical)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_stats)
        self.splitDockWidget(self.dock_stats, self.dock_hist, Qt.Orientation.Vertical)

                                                     
        self.resizeDocks(
            [self.dock_market, self.dock_pos], [500, 500], Qt.Orientation.Vertical
        )
        self.resizeDocks(
            [self.dock_stats, self.dock_hist], [500, 500], Qt.Orientation.Vertical
        )
        self.resizeDocks(
            [self.dock_market, self.dock_stats], [500, 500], Qt.Orientation.Horizontal
        )

        self.setStatusBar(QStatusBar())
        self.statusBar().setStyleSheet(
            f"color: {TEXT_SUB}; background: {CARD_BG}; border-top: 1px solid {BORDER_COLOR};"
        )

        self.worker = TradingBridge(chay_realtime)
        self.worker.data_signal.connect(self.sync_all)

                                              
        self.statusBar().showMessage(
            "Hệ thống đang chờ... Vui lòng bấm 'BẮT ĐẦU REALTIME'."
        )

                                          
    def start_realtime_mode(self):
        """Khóa nút và khởi động luồng realtime khi người dùng bấm bắt đầu."""
        self.btn_start.setEnabled(False)                                       
        self.btn_start.setText("ĐANG CHẠY REALTIME...")
        self.btn_start.setStyleSheet(
            f"background-color: {COLOR_WIN}; color: #FFF; font-weight: bold; padding: 6px 20px; border-radius: 4px; border: none;"
        )
        self.statusBar().showMessage("Đang khởi động luồng Realtime...")

                                                                                        
        self._ap_dung_chien_luoc_ghi_de()

                                      
        self.worker.start()

    def sync_all(self, data):
        """Cập nhật toàn bộ các widget UI khi nhận được data mới từ luồng realtime."""
        self.market_view.update_data(data)
        self.pos_table.refresh(data)
        self.summary_widget.update_data(data)
        self.hist_table.refresh(data)
        p_count = len(data.get("lenh_dang_chay", {}))
        self.statusBar().showMessage(
            f"Running Realtime | Lệnh mở: {p_count} | Update: {time.strftime('%H:%M:%S')}"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    win = MainDashboard_realtime()
    win.show()
    sys.exit(app.exec())
