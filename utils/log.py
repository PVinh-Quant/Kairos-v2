"""
utils/log.py – Logger dùng chung toàn hệ thống
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cung cấp logger ghi cả ra file và console. Điểm đặc biệt:
trong chế độ Backtest, timestamp log phản chiếu thời gian giả lập
(không phải giờ thực) nhờ TimeContext – giúp debug rất trực quan.
"""

import logging
import os
import sys
from datetime import datetime

_CONSOLE_SUPPRESS = [
    "Lỗi kết nối sàn",
]


class _SuppressFilter(logging.Filter):
    def filter(self, record):
        """Lọc bỏ các thông điệp log chứa từ khóa trong _CONSOLE_SUPPRESS."""
        return not any(kw in record.getMessage() for kw in _CONSOLE_SUPPRESS)


class TimeContext:
    """Biến class dùng làm "đồng hồ ảo" – backtest ghi đè thời gian tại đây."""

    current_sim_time = None


class DynamicTimeFormatter(logging.Formatter):
    """Formatter tùy chỉnh: nếu đang backtest thì in thời gian giả lập, ngược lại in giờ thật."""

    def formatTime(self, record, datefmt=None):
        """Trả về thời gian giả lập nếu đang backtest, ngược lại dùng thời gian thực."""
        if TimeContext.current_sim_time:
            if isinstance(TimeContext.current_sim_time, datetime):
                return TimeContext.current_sim_time.strftime(
                    datefmt or "%Y-%m-%d %H:%M:%S"
                )
            return str(TimeContext.current_sim_time)

        return super().formatTime(record, datefmt)


def thiet_lap_logger():
    """Khởi tạo và trả về logger ghi ra file và console với DynamicTimeFormatter."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "du_lieu")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("CryptoBot")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = DynamicTimeFormatter("%(asctime)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(
            os.path.join(log_dir, "nhat_ky_hoat_dong.log"), encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(_SuppressFilter())
        logger.addHandler(stream_handler)

    return logger


def set_log_time(dt):
    """Gọi hàm này đầu mỗi vòng lặp nến để set thời gian giả lập cho log."""
    TimeContext.current_sim_time = dt


def reset_log_time():
    """Gọi hàm này khi chạy Realtime hoặc kết thúc Backtest để reset về giờ thật."""
    TimeContext.current_sim_time = None


logger = thiet_lap_logger()





def banner_khoi_dong(ten: str, rows: list[tuple]):
    """
    In panel khởi động theo style main.py.
    rows: list of (label, value) tuples.
    Ví dụ: banner_khoi_dong("DEMO", [("Vốn", "10,000 USDT"), ("Sàn", "Binance")])
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich import box

        con = Console()
        tbl = Table(box=None, show_header=False, padding=(0, 1))
        tbl.add_column("k", style="dim", min_width=18)
        tbl.add_column("v", style="cyan", min_width=20)
        for label, value in rows:
            tbl.add_row(label, str(value))

        con.print(
            Panel(
                tbl,
                title=f"[bold cyan]{ten}[/bold cyan]",
                border_style="cyan",
                padding=(0, 2),
            )
        )
    except Exception:
        logger.info(f"[ {ten} ]")
        for label, value in rows:
            logger.info(f"  {label:<20}: {value}")


def banner_ket_qua(ten: str, rows: list[tuple]):
    """
    In panel kết quả theo style main.py.
    rows: list of (label, value) tuples.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        con = Console()
        tbl = Table(box=None, show_header=False, padding=(0, 1))
        tbl.add_column("k", style="dim", min_width=20)
        tbl.add_column("v", style="bold white", min_width=20)
        for label, value in rows:
            tbl.add_row(label, str(value))

        con.print(
            Panel(
                tbl,
                title=f"[bold green]{ten}[/bold green]",
                border_style="green",
                padding=(0, 2),
            )
        )
    except Exception:
        logger.info(f"[ {ten} ]")
        for label, value in rows:
            logger.info(f"  {label:<20}: {value}")
