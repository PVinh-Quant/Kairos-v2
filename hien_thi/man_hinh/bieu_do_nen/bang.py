"""bieu_do_nen/bang.py — bảng danh sách lệnh của biểu đồ nến."""
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from hien_thi.giao_dien.theme import Theme
class TradesTableWidget(QTableWidget):
    def __init__(self, parent=None):
        """Khởi tạo bảng hiển thị danh sách lệnh với style chuyên nghiệp."""
        super().__init__(parent)
        self.cols = ["Id", "Type", "Hold", "Change"]
        self.setColumnCount(len(self.cols))
        self.setHorizontalHeaderLabels(self.cols)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)


        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.setStyleSheet(f"""
            QTableWidget {{ background-color: {Theme.CARD}; color: {Theme.TEXT_MAIN}; gridline-color: {Theme.GRID}; border: none; font-size: 12px; }}
            QHeaderView::section {{ background-color: {Theme.BG}; color: {Theme.TEXT_SUB}; font-weight: bold; padding: 8px 5px; border: 1px solid {Theme.BORDER}; border-top: none; }}
            QTableWidget::item:selected {{ background-color: {Theme.ACCENT}; color: white; }}
            QScrollBar:vertical, QScrollBar:horizontal {{ width: 0px; height: 0px; background: transparent; }}
        """)


        hdr = self.horizontalHeader()
        hdr.setMinimumSectionSize(30)
        hdr.setResizeContentsPrecision(50)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.setMinimumWidth(260)

    def load_trades(self, trades):
        """Nạp danh sách lệnh vào bảng, tô màu theo lãi/lỗ."""
        self.setRowCount(0)
        for i, t in enumerate(trades):
            if "exit_time" not in t:
                continue

            row_idx = self.rowCount()
            self.insertRow(row_idx)
            price_change_val = float(t.get("price_change", 0.0))

            row_data = [
                str(t["id"]),
                str(t["direction"]),
                str(t["hold_time"]),
                f"{price_change_val:+.2f}",
            ]
            for col, text in enumerate(row_data):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:
                    color = (
                        Theme.WIN
                        if price_change_val > 0
                        else Theme.LOSS if price_change_val < 0 else Theme.TEXT_MAIN
                    )
                    item.setForeground(QColor(color))
                self.setItem(row_idx, col, item)




