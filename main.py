
"""
Kairos Quant System v2 – Entry Point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chạy từ thư mục gốc dự án:
    python main.py7"""

import sys
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich import box
from rich.style import Style

console = Console()




LOGO = r"""
 ██╗  ██╗ █████╗ ██╗██████╗  ██████╗ ███████╗
 ██║ ██╔╝██╔══██╗██║██╔══██╗██╔═══██╗██╔════╝
 █████╔╝ ███████║██║██████╔╝██║   ██║███████╗
 ██╔═██╗ ██╔══██║██║██╔══██╗██║   ██║╚════██║
 ██║  ██╗██║  ██║██║██║  ██║╚██████╔╝███████║
 ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝"""





def _doc_config_ngan():
    """Đọc config hiện tại để hiển thị trong menu."""
    try:
        from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao

        cfg_trade = lay_cau_hinh_giao_dich() or {}
        cfg_backtest = lay_cau_hinh_ao() or {}
        symbols = cfg_trade.get("cap_giao_dich", [])
        symbol_str = (
            ", ".join(symbols[:3]) + ("..." if len(symbols) > 3 else "")
            if symbols
            else "—"
        )
        return {
            "symbols": symbol_str,
            "don_bay": cfg_trade.get("don_bay", "—"),
            "tu_ngay": cfg_backtest.get("ngay_bat_dau", "—"),
            "den_ngay": cfg_backtest.get("ngay_ket_thuc", "—"),
            "von": f"{cfg_backtest.get('so_du_ban_dau', 0):,.0f} USDT",
        }
    except Exception:
        return {
            "symbols": "—",
            "don_bay": "—",
            "tu_ngay": "—",
            "den_ngay": "—",
            "von": "—",
        }





def _count_wrapped_lines(text: str, width: int) -> int:
    """Đếm số dòng thực tế khi text bị wrap theo chiều rộng width."""
    if not text:
        return 1
    lines = 0
    for part in text.split("\n"):
        words = part.split(" ")
        current_len = 0
        part_lines = 1
        for word in words:
            if not word:
                continue
            if current_len + len(word) > width:
                part_lines += 1
                current_len = len(word) + 1
            else:
                current_len += len(word) + 1
        lines += part_lines
    return lines


def hien_thi_menu():
    """Vẽ giao diện menu chính với logo, danh sách chức năng và config tóm tắt."""
    console.clear()
    from rich.rule import Rule


    console_width = console.width


    min_side_by_side_width = 110
    max_layout_width = 132

    is_side_by_side = console_width >= min_side_by_side_width

    if is_side_by_side:
        layout_width = min(console_width, max_layout_width)
        right_w = 44
        left_w = layout_width - right_w - 2
    else:
        layout_width = max(50, console_width)
        right_w = layout_width
        left_w = layout_width


    logo_text = Text(LOGO, style="bold cyan")

    logo_max_line_len = max(len(line) for line in LOGO.split("\n"))
    subtitle_text = "Analytics System v2"
    padding_len = max(0, (logo_max_line_len - len(subtitle_text)) // 2)
    subtitle = Text(" " * padding_len + subtitle_text, style="dim white")
    content = Align.center(Text.assemble(logo_text, "\n", subtitle))

    logo_panel = Panel(content, border_style="cyan", padding=(0, 2), width=layout_width)


    menu = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    menu.add_column("key", style="bold yellow", width=6, justify="center")
    menu.add_column("name", style="white", width=28)
    menu.add_column("desc", style="dim")

    menu.add_row("")
    menu.add_row("", Text("LIVE TRADING", style="bold green"), "")
    menu.add_row("[1]", "Giao dịch Realtime", "Kết nối sàn thật · CCXT")
    menu.add_row("[2]", "Demo / Paper Trading", "Pipeline đầy đủ · không rủi ro")

    menu.add_row("")
    menu.add_row("", Text("BACKTESTING", style="bold blue"), "")
    menu.add_row("[3]", "Backtest Đơn luồng", "Bar-to-bar · 1 thread")
    menu.add_row("[4]", "Backtest Đa luồng", "Bar-to-bar · song song")
    menu.add_row("[5]", "Vectorized Backtest", "Toàn bộ dataset · nhanh 100x")

    menu.add_row("")
    menu.add_row("", Text("AI / ML", style="bold magenta"), "")
    menu.add_row("[6]", "ML Training", "Huấn luyện · đánh giá · deploy")

    menu.add_row("")
    menu.add_row("", Text("ANALYTICS", style="bold yellow"), "")
    menu.add_row("[7]", "Dashboard Analytics", "PyQt6 · equity · heatmap · scatter")

    menu.add_row("")
    menu.add_row("", Text("OPTIMIZATION", style="bold cyan"), "")
    menu.add_row("[8]", "Tối ưu hóa tham số", "Bayesian · Walk-Forward")

    menu.add_row("", "", "")
    menu.add_row("[0]", Text("Thoát", style="dim red"), "")


    cfg = _doc_config_ngan()
    cfg_table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        border_style="bright_black",
        expand=True,
    )
    cfg_table.add_column("k", style="dim", width=12)
    cfg_table.add_column("v", style="cyan")
    cfg_table.add_row("Symbols", cfg["symbols"])
    cfg_table.add_row("Don bay", str(cfg["don_bay"]) + "x")
    cfg_table.add_row("Backtest", f"{cfg['tu_ngay']}  →  {cfg['den_ngay']}")
    cfg_table.add_row("Von", cfg["von"])


    author = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    author.add_column("info")
    author.add_row(Text(""))
    author.add_row(
        Text(
            "P. Vinh - Financial Data Analyst · ML Engineer · Quant Developer",
            style="bold cyan",
        )
    )
    author.add_row(Rule(style="bright_black"))
    quote = "Romain Rolland: 'There is only one heroism in the world: to see the world as it is, and to love it.'"
    author.add_row(Text(quote, style="italic dim white"))
    author.add_row(Rule(style="bright_black"))
    author.add_row(Text("Kairos  v2  ·  2026", style="dim"))
    author.add_row(Text(""))


    cfg_panel = Panel(
        cfg_table,
        title="[bold]Config hien tai[/bold]",
        border_style="bright_black",
        width=right_w,
        expand=True,
    )
    author_panel = Panel(
        author,
        title="[bold]Tac gia[/bold]",
        border_style="cyan",
        width=right_w,
        expand=True,
    )

    if is_side_by_side:

        right_group = Group(cfg_panel, author_panel)
        options = console.options.copy().update(width=right_w)
        right_height = len(console.render_lines(right_group, options))


        base_rows = len(menu.rows)
        target_rows = right_height - 2
        extra_rows = target_rows - base_rows
        if extra_rows > 0:
            for _ in range(extra_rows):
                menu.add_row("", "", "")

        left_panel = Panel(
            menu,
            title="[bold]Menu[/bold]",
            border_style="bright_black",
            width=left_w,
            expand=True,
        )


        if console_width > max_layout_width:
            console.print(Align.center(logo_panel))
            console.print(
                Align.center(
                    Columns([left_panel, right_group], equal=False, padding=(0, 2))
                )
            )
        else:
            console.print(logo_panel)
            console.print(
                Columns([left_panel, right_group], equal=False, padding=(0, 2))
            )
    else:

        left_panel = Panel(
            menu,
            title="[bold]Menu[/bold]",
            border_style="bright_black",
            width=layout_width,
            expand=True,
        )

        console.print(logo_panel)
        console.print(left_panel)
        console.print(cfg_panel)
        console.print(author_panel)

    console.print()
    return console.input("[bold yellow]Chon chuc nang [0-8]:[/bold yellow] ").strip()





def chay_realtime():
    """Khởi động bot giao dịch realtime và giữ tiến trình chờ cho đến khi Ctrl+C."""
    from chuc_nang.chay_realtime import chay_realtime as _run
    import threading, signal

    _run()
    stop = threading.Event()

    def _exit(sig, frame):
        console.print("\n[yellow]Đang tắt bot...[/yellow]")
        stop.set()

    signal.signal(signal.SIGINT, _exit)
    stop.wait()


def chay_demo():
    """Khởi động paper trading demo và giữ tiến trình chờ cho đến khi Ctrl+C."""
    from chuc_nang.chay_demo import chay_demo as _run
    import threading, signal

    _run()
    stop = threading.Event()

    def _exit(sig, frame):
        console.print("\n[yellow]Đang tắt demo...[/yellow]")
        stop.set()

    signal.signal(signal.SIGINT, _exit)
    stop.wait()


def chay_backtest_don():
    """Chạy backtest bar-to-bar đơn luồng."""
    from chuc_nang.backtest_donluong import chay_backtest

    chay_backtest()


def chay_backtest_da():
    """Chạy backtest bar-to-bar đa luồng."""
    from chuc_nang.backtest_daluong import chay_backtest

    chay_backtest()


def chay_vectorized():
    """Chạy vectorized backtest và thông báo nếu không có lệnh nào."""
    from chuc_nang.vectorized_backtest import vectorized_backtest

    lich_su, _ = vectorized_backtest()
    if not lich_su:
        console.print("[yellow]Không có lệnh nào được thực hiện.[/yellow]")


def chay_ml():
    """Khởi động quy trình ML training bằng subprocess."""
    import subprocess

    ml_main = os.path.join(PROJECT_ROOT, "ml", "main.py")
    if os.path.exists(ml_main):
        subprocess.run([sys.executable, ml_main], cwd=PROJECT_ROOT)
    else:
        console.print(f"[red]Không tìm thấy {ml_main}[/red]")


def chay_dashboard():
    """Khởi động dashboard PyQt6. Tab sinh động từ registry (hien_thi.dang_ky_man_hinh).

    KHÔNG dựng tab tại đây nữa: vỏ app duy nhất là `hien_thi.app.ung_dung` — thêm/bớt
    màn hình chỉ cần sửa registry `MAN_HINH`, không đụng main.py.
    """
    try:
        from hien_thi.app.ung_dung import chay
    except ImportError as e:
        console.print(f"[red]Lỗi import dashboard: {e}[/red]")
        return

    chay()


def chay_toi_uu_hoa():
    """Khởi động menu tối ưu hóa tham số bằng Optuna."""
    from toi_uu_hoa.giao_dien_cli import chay_menu_tuong_tac

    chay_menu_tuong_tac()


DISPATCH = {
    "1": chay_realtime,
    "2": chay_demo,
    "3": chay_backtest_don,
    "4": chay_backtest_da,
    "5": chay_vectorized,
    "6": chay_ml,
    "7": chay_dashboard,
    "8": chay_toi_uu_hoa,
}


if __name__ == "__main__":
    lua_chon = hien_thi_menu()

    if lua_chon == "0":
        console.print("[dim]Tạm biệt.[/dim]")
        sys.exit(0)

    handler = DISPATCH.get(lua_chon)
    if handler is None:
        console.print(f"[red]Lựa chọn '{lua_chon}' không hợp lệ.[/red]")
        sys.exit(1)

    console.print()
    try:
        handler()
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã dừng.[/yellow]")
    except Exception as e:
        console.print(f"[red]Lỗi: {e}[/red]")
        raise
