import sys
import os
from datetime import datetime

                     
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich import box

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

try:
    from utils.log import logger
    from utils.doc_cau_hinh import lay_cau_hinh_giao_dich, lay_cau_hinh_ao
    from lay_du_lieu.lay_ohlcv import (
        gop_nen,
        tai_du_lieu_lich_su,
        chuan_bi_du_lieu_da_khung,
    )
    from ml.tool.data_filter import tao_log_can_bang
    from ml.trang_thai_thi_truong_ml.ml_model import huan_luyen_model
    from ml.trang_thai_thi_truong_ml.ml_predict import (
        du_doan_trang_thai_ml,
        danh_gia_ml,
        STATE_MAP,
    )
    from ml.tool.trading_teacher import TradingTeacher
    from ml.tool.dashboard import hien_thi_dashboard
except ImportError as e:
    print(f"❌ Lỗi Import: {e}")
    sys.exit(1)


def tao_model_lan_dau():
    """Tải dữ liệu lịch sử, gộp nến đa khung và huấn luyện model lần đầu."""
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    START_DATE = config_backtest.get("ngay_bat_dau", "2025-01-01")
    END_DATE = config_backtest.get("ngay_ket_thuc", "2025-01-31")
    DS_SYMBOL = config_trading.get("cap_giao_dich", ["BTC/USDT"])

    symbol = DS_SYMBOL[0]

    df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)

    if df_goc is None or df_goc.is_empty():
        logger.error("Không có dữ liệu để huấn luyện!")
        return

    current_time = df_goc.get_column("timestamp").last()

    dfs = chuan_bi_du_lieu_da_khung(df_goc, current_time)

    df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d = dfs

    huan_luyen_model(df_5m, df_15m, df_1h, df_4h)


console = Console()


def chay_training_cap_toc():
    """Chạy vòng lặp training bar-to-bar dùng Trading Teacher làm nhãn, hiển thị live dashboard."""
    config_backtest = lay_cau_hinh_ao()
    config_trading = lay_cau_hinh_giao_dich()

    START_DATE = config_backtest.get("ngay_bat_dau", "2025-01-01")
    END_DATE = config_backtest.get("ngay_ket_thuc", "2025-01-31")
    DS_SYMBOL = config_trading.get("cap_giao_dich", ["BTC/USDT"])

    with Live(console=console, refresh_per_second=10) as live:

        for symbol in DS_SYMBOL:

            df_goc = tai_du_lieu_lich_su(symbol, START_DATE, END_DATE)
            if df_goc is None or df_goc.is_empty():
                continue

            idx_start = 43200
            if df_goc.height < idx_start:
                continue
            timestamps = df_goc.get_column("timestamp").slice(idx_start).to_list()

                             
            stats = {"correct": 0, "wrong": 0}
            class_stats = {k: {"correct": 0, "total": 0} for k in STATE_MAP.keys()}

            teacher = TradingTeacher()

            for current_time in timestamps:
                dfs = chuan_bi_du_lieu_da_khung(df_goc, current_time)
                if not dfs:
                    continue

                df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d = dfs

                packet = du_doan_trang_thai_ml(
                    df_5m, df_15m, df_1h, df_4h, last_state=teacher.last_state
                )

                if packet is None:
                    continue
                ai_state = packet["state_id"]
                conf = packet["confidence"]

                teacher_state, teacher_conf = teacher.detect_regime(
                    df_5m, df_15m, df_1h, df_4h
                )

                class_stats[teacher_state]["total"] += 1

                if ai_state == teacher_state:
                    stats["correct"] += 1
                    class_stats[teacher_state]["correct"] += 1
                    danh_gia_ml(packet, 1, 0, teacher_state)                 
                else:
                    stats["wrong"] += 1
                    danh_gia_ml(packet, -0.5, 0, teacher_state)                 

                layout = hien_thi_dashboard(
                    symbol,
                    current_time,
                    stats,
                    class_stats,
                    ai_state,
                    teacher_state,
                    teacher_conf,
                    conf,
                )
                live.update(layout)

        console.print(f"[bold green] HOÀN TẤT TRAINING {symbol}![/]")


def _lay_thong_tin_model():
    """Đọc thông tin model hiện tại để hiển thị trong menu."""
    try:
        import json

        info_path = os.path.join(
            os.path.dirname(__file__),
            "trang_thai_thi_truong_ml",
            "du_lieu_ml",
            "model_info.json",
        )
        model_path = os.path.join(
            os.path.dirname(__file__),
            "trang_thai_thi_truong_ml",
            "du_lieu_ml",
            "model_pytorch.pth",
        )

        last_train = "—"
        accuracy = "—"
        loss = "—"

        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
                accuracy = (
                    f"{info.get('accuracy', 0)*100:.1f}%" if "accuracy" in info else "—"
                )
                loss = f"{info.get('loss', 0):.4f}" if "loss" in info else "—"

        if os.path.exists(model_path):
            mtime = os.path.getmtime(model_path)
            last_train = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

        return {
            "last_train": last_train,
            "accuracy": accuracy,
            "loss": loss,
        }
    except Exception:
        return {"last_train": "—", "accuracy": "—", "loss": "—"}


def hien_thi_menu_ml():
    """Vẽ menu ML bằng Rich và trả về lựa chọn của người dùng."""
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

                                                                                         
    title_text = Text("KAIROS — MACHINE LEARNING ENGINE", style="bold magenta")
    title_panel = Panel(
        Align.center(title_text), border_style="magenta", width=layout_width
    )

                                                        
    menu = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    menu.add_column("key", style="bold yellow", width=6, justify="center")
    menu.add_column("name", style="white", width=28)
    menu.add_column("desc", style="dim")
    menu.add_row("")
    menu.add_row("", Text("MODEL INITIALIZATION", style="bold green"), "")
    menu.add_row("[1]", "Tạo model lần đầu", "Tải lịch sử, gộp nến, train model gốc")
    menu.add_row("")
    menu.add_row("", Text("MODEL TRAINING", style="bold blue"), "")
    menu.add_row("[2]", "Chạy training cấp tốc", "Dùng Trading Teacher để train nhanh")
    menu.add_row("[3]", "Tự động học từ log", "Học tăng cường từ kết quả giao dịch")
    menu.add_row("")
    menu.add_row("", Text("DATA PREPARATION", style="bold yellow"), "")
    menu.add_row("[4]", "Lọc dữ liệu lệnh thắng", "Cân bằng và tối ưu dữ liệu từ log")

    menu.add_row("", "", "")
    menu.add_row("[0]", Text("Thoát", style="dim red"), "Quay lại terminal launcher")
    menu.add_row("")
                    
    config_backtest = lay_cau_hinh_ao() or {}
    config_trading = lay_cau_hinh_giao_dich() or {}
    START_DATE = config_backtest.get("ngay_bat_dau", "—")
    END_DATE = config_backtest.get("ngay_ket_thuc", "—")
    DS_SYMBOL = config_trading.get("cap_giao_dich", [])
    symbol_str = (
        ", ".join(DS_SYMBOL[:3]) + ("..." if len(DS_SYMBOL) > 3 else "")
        if DS_SYMBOL
        else "—"
    )

    cfg_table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        border_style="bright_black",
        expand=True,
    )
    cfg_table.add_column("k", style="dim", width=12)
    cfg_table.add_column("v", style="cyan")
    cfg_table.add_row("Symbols", symbol_str)
    cfg_table.add_row("Đòn bẩy", str(config_trading.get("don_bay", "—")) + "x")
    cfg_table.add_row("Backtest", f"{START_DATE}  →  {END_DATE}")
    cfg_table.add_row("Vốn", f"{config_backtest.get('so_du_ban_dau', 0):,.0f} USDT")

                        
    m_info = _lay_thong_tin_model()
    model_table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    model_table.add_column("k", style="dim", width=12)
    model_table.add_column("v", style="magenta")
    model_table.add_row("Last Train", m_info["last_train"])
    model_table.add_row("Accuracy", m_info["accuracy"])
    model_table.add_row("Train Loss", m_info["loss"])

                             
    cfg_panel = Panel(
        cfg_table,
        title="[bold]Config hiện tại[/bold]",
        border_style="bright_black",
        width=right_w,
        expand=True,
    )
    model_panel = Panel(
        model_table,
        title="[bold]Trạng thái Model[/bold]",
        border_style="magenta",
        width=right_w,
        expand=True,
    )

    if is_side_by_side:
                                                              
        right_group = Group(cfg_panel, model_panel)
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
            title="[bold]Menu ML[/bold]",
            border_style="bright_black",
            width=left_w,
            expand=True,
        )

                                                                                     
        if console_width > max_layout_width:
            console.print(Align.center(title_panel))
            console.print(
                Align.center(
                    Columns([left_panel, right_group], equal=False, padding=(0, 2))
                )
            )
        else:
            console.print(title_panel)
            console.print(
                Columns([left_panel, right_group], equal=False, padding=(0, 2))
            )
    else:
                                              
        left_panel = Panel(
            menu,
            title="[bold]Menu ML[/bold]",
            border_style="bright_black",
            width=layout_width,
            expand=True,
        )

        console.print(title_panel)
        console.print(left_panel)
        console.print(cfg_panel)
        console.print(model_panel)

    console.print()
    return console.input("[bold yellow]Chọn chức năng [0-4]:[/bold yellow] ").strip()


def main():
    """Điểm vào chính: hiển thị menu và điều phối chức năng ML theo lựa chọn."""
    choice = hien_thi_menu_ml()

    if choice == "1":
        tao_model_lan_dau()

    elif choice == "2":
        chay_training_cap_toc()

    elif choice == "3":
        from ml.trang_thai_thi_truong_ml.ml_model import tu_dong_hoc_tu_log

        tu_dong_hoc_tu_log()

    elif choice == "4":
        tao_log_can_bang()

    elif choice == "0":
        console.print("[dim]Thoát chương trình.[/dim]")

    else:
        console.print("[bold red]Lựa chọn không hợp lệ![/bold red]")


if __name__ == "__main__":
    main()
