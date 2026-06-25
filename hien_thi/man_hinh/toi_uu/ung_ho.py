import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QApplication,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices, QPixmap
from .theme import Theme

class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
                                                  
        self.container = QWidget(self)
        self.container.setFixedSize(560, 320)
        self.container.setStyleSheet(f"""
            QWidget#DonationContainer {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        self.container.setObjectName("DonationContainer")
        
                                    
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(12)
        
                                                                               
        header_lay = QHBoxLayout()
        lbl_title = QLabel("Ủng hộ tác giả")
        lbl_title.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        
        btn_close = QPushButton("×")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("""
            QPushButton {
                color: #787B86;
                font-size: 18px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        btn_close.clicked.connect(self.reject)
        
        header_lay.addWidget(lbl_title)
        header_lay.addStretch()
        header_lay.addWidget(btn_close)
        layout.addLayout(header_lay)
        
                                                                                
        body_lay = QHBoxLayout()
        body_lay.setSpacing(16)
        body_lay.setContentsMargins(0, 0, 0, 0)
        
                         
        qr_container = QWidget()
        qr_container.setFixedSize(220, 220)
        qr_container.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-radius: 8px;
            }
        """)
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(4, 4, 4, 4)
        
        lbl_qr = QLabel()
        lbl_qr.setFixedSize(212, 212)
        lbl_qr.setScaledContents(True)
        lbl_qr.setStyleSheet("border: none; background: transparent; border-radius: 6px;")
        
                                
        current_dir = os.path.dirname(os.path.abspath(__file__))
        qr_path = os.path.abspath(os.path.join(current_dir, "..", "..", "assets", "QR.jpg"))
        pix = QPixmap()
        if os.path.exists(qr_path):
            pix.load(qr_path)
            lbl_qr.setPixmap(pix)
        else:
            lbl_qr.setText("Không tìm thấy\nmã QR")
            lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_qr.setStyleSheet("color: #787B86; font-size: 12px; font-weight: bold; border: none; background: transparent;")
            
        qr_layout.addWidget(lbl_qr)
        body_lay.addWidget(qr_container)
        
                                       
        right_lay = QVBoxLayout()
        right_lay.setSpacing(10)
        right_lay.setContentsMargins(0, 2, 0, 2)
        
                                                                   
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        lbl_message = QLabel(
            "Cảm ơn bạn đã đồng hành cùng Kairos v2!\n\n"
            "Kairos được phát triển với mục tiêu mang lại giá trị thực cho cộng đồng. Bên cạnh các tính năng miễn phí, dự án cũng có những nội dung nâng cao để duy trì và tiếp tục phát triển sản phẩm.\n\n"
            "Nếu Kairos đã giúp ích cho bạn, hãy ủng hộ theo mức mà bạn cảm thấy phù hợp. Mọi khoản đóng góp đều được tái đầu tư vào nghiên cứu, cải tiến và xây dựng các tính năng mới trong tương lai.\n\n"
            "Sự đồng hành của bạn chính là động lực để Kairos ngày càng hoàn thiện hơn."
        )
        lbl_message.setWordWrap(True)
        lbl_message.setStyleSheet("color: #D2D4DC; font-size: 11px; line-height: 16px; background: transparent; border: none;")
        
        scroll.setWidget(lbl_message)
        right_lay.addWidget(scroll)
        
        right_lay.addStretch()
        
                            
        link_container = QWidget()
        link_container.setStyleSheet(f"""
            QWidget {{
                background-color: #1E222D;
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
        """)
        link_lay = QHBoxLayout(link_container)
        link_lay.setContentsMargins(8, 4, 8, 4)
        link_lay.setSpacing(6)
        
        self.lbl_link = QLabel("me.momo.vn/pvinh05")
        self.lbl_link.setStyleSheet("color: #FFFFFF; font-size: 11px; border: none; background: transparent;")
        link_lay.addWidget(self.lbl_link, 1)
        
        btn_copy = QPushButton("Sao chép")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setFixedHeight(22)
        btn_copy.setStyleSheet(f"""
            QPushButton {{
                color: #FFFFFF;
                background-color: #2A2E39;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                padding: 0px 8px;
            }}
            QPushButton:hover {{
                background-color: #363A45;
            }}
        """)
        btn_copy.clicked.connect(self.copy_link)
        link_lay.addWidget(btn_copy)
        right_lay.addWidget(link_container)
        
                            
        btn_open = QPushButton("⚡ Mở link MoMo")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setFixedHeight(30)
        btn_open.setStyleSheet(f"""
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
        btn_open.clicked.connect(self.open_browser)
        right_lay.addWidget(btn_open)
        
        body_lay.addLayout(right_lay)
        layout.addLayout(body_lay)
        
                               
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container, 0, Qt.AlignmentFlag.AlignCenter)
        
    def copy_link(self):
        QApplication.clipboard().setText("https://me.momo.vn/pvinh05")
        sender = self.sender()
        if sender:
            sender.setText("Đã chép!")
            sender.setStyleSheet("color: #089981; background-color: #2A2E39; border: none; border-radius: 4px; font-size: 10px; padding: 0px 8px;")
            QTimer.singleShot(1500, lambda: sender.setText("Sao chép") or sender.setStyleSheet(f"color: #FFFFFF; background-color: #2A2E39; border: none; border-radius: 4px; font-size: 10px; padding: 0px 8px;"))

    def open_browser(self):
        QDesktopServices.openUrl(QUrl("https://me.momo.vn/pvinh05"))
