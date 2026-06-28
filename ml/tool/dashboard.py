from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box
from rich.live import Live


def hien_thi_dashboard(
    symbol,
    current_time,
    stats,
    class_stats,
    ai_state,
    teacher_state,
    teacher_conf,
    conf,
):
    """Xây dựng và trả về layout Rich hiển thị live feed AI vs Teacher theo từng regime."""
    SHORT_NAMES = {
        0: "Đóng_Băng",
        1: "Nén_Chặt",
        2: "Đầu_Xu_Hướng",
        3: "Xu_Hướng_Mạnh",
        4: "Cao_Trào",
        5: "Hồi_Quy",
        6: "Nhiễu_Động",
        7: "Quét_Thanh_Khoản",
    }

    total = stats["correct"] + stats["wrong"]
    global_acc = (stats["correct"] / total * 100) if total > 0 else 0.0

    ai_text = SHORT_NAMES.get(ai_state, str(ai_state))
    tc_text = SHORT_NAMES.get(teacher_state, str(teacher_state))

    is_match = ai_state == teacher_state
    status_color = "bold green" if is_match else "bold red"
    icon = "✅ MATCH" if is_match else "❌ DIFF"

    table = Table(box=box.SIMPLE, expand=True, border_style="blue")
    table.add_column("Trạng Thái", style="cyan", no_wrap=True)
    table.add_column("Tỷ Lệ (Đ/T)", justify="center")
    table.add_column("Chính Xác", justify="right")
    table.add_column("Biểu Đồ", ratio=1)

    for state_id in sorted(class_stats.keys()):
        val = class_stats[state_id]
        if val["total"] == 0:
            continue

        name = SHORT_NAMES.get(state_id, str(state_id))
        acc = val["correct"] / val["total"] * 100
        fraction = f"{val['correct']}/{val['total']}"


        bar_len = 20
        filled = int(acc / 100 * bar_len)
        bar_str = "█" * filled + "░" * (bar_len - filled)
        color_bar = "[green]" if acc > 50 else "[yellow]" if acc > 30 else "[red]"

        table.add_row(name, fraction, f"{acc:.1f}%", f"{color_bar}{bar_str}[/]")


    live_info = Text()
    live_info.append("🤖 AI Dự Đoán : ", style="bold white")
    live_info.append(f"{ai_text:<8} : {conf * 100:.2f}%", style="cyan")
    live_info.append("  vs  ", style="dim")
    live_info.append("👨‍🏫 Thầy Phán : ", style="bold white")
    live_info.append(f"{tc_text:<8} : {teacher_conf:.2f}", style="magenta")
    live_info.append(f"\n\n   KẾT QUẢ: ", style="bold white")
    live_info.append(f"{icon}", style=status_color)

    live_panel = Panel(
        Align.center(live_info, vertical="middle"),
        title="⚡ LIVE FEED",
        border_style="yellow",
        height=8,
    )

    stats_text = Text()
    stats_text.append(
        f"{global_acc:.2f}%", style="bold green" if global_acc > 50 else "bold red"
    )
    stats_text.append("\nGlobal Accuracy", style="dim")
    stats_text.append(f"\n\nSample Size: {total}", style="white")

    stats_panel = Panel(
        Align.center(stats_text, vertical="middle"),
        title="🎯 PERFORMANCE",
        border_style="green",
        height=8,
    )

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=2)
    grid.add_row(stats_panel, live_panel)

    final_layout = Layout()
    final_layout.split_column(
        Layout(name="header", size=3),
        Layout(name="upper", size=8),
        Layout(name="lower"),
    )

    final_layout["header"].update(
        Panel(
            Align.center(
                f"KAIROS QUANT SYSTEM - {symbol} - {current_time}", vertical="middle"
            ),
            style="bold white on blue",
        )
    )
    final_layout["upper"].update(grid)
    final_layout["lower"].update(
        Panel(table, title="📈 BREAKDOWN BY STATE", border_style="blue")
    )

    return final_layout
