"""
thong_bao/gui_email.py – Gửi email cảnh báo giao dịch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gửi email qua SMTP Gmail khi bot mở/đóng lệnh.
Tự bỏ qua nếu EMAIL_GUI chưa được cấu hình thật sự.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.log import logger


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_GUI = "your_email@gmail.com"
MAT_KHAU_APP = "your_app_password"


def gui_email_canh_bao(tieu_de, noi_dung, email_nhan):
    """Gửi email cảnh báo giao dịch qua SMTP, bỏ qua nếu chưa cấu hình email."""
    if "your_" in EMAIL_GUI:
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_GUI
    msg["To"] = email_nhan
    msg["Subject"] = f"[BOT TRADING] {tieu_de}"

    msg.attach(MIMEText(noi_dung, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_GUI, MAT_KHAU_APP)
        text = msg.as_string()
        server.sendmail(EMAIL_GUI, email_nhan, text)
        server.quit()
        logger.info(f"Đã gửi email đến {email_nhan}")
    except Exception as e:
        logger.error(f"Lỗi gửi email: {e}")


if __name__ == "__main__":
    gui_email_canh_bao("Test", "Đây là email test từ Bot", "receiver@example.com")
