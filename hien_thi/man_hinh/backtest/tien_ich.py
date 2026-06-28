"""backtest/tien_ich.py — animation ASCII trạng thái + tác vụ lọc dữ liệu (luồng nền)."""
import sys, os, random, calendar, math
from datetime import datetime
import polars as pl
def funny_quant_runner():
    """Trả về frame hoạt hình ASCII tiếp theo, tạo danh sách frame lần đầu gọi."""

    if not hasattr(funny_quant_runner, "frames"):
        frames = []
        WIDTH = 120


        def add_frame(content):
            frames.append(content)

        def add_static_scene(icon_list, pos, repeat=1):
            for _ in range(repeat):
                for icon in icon_list:
                    safe_pos = max(0, min(pos, WIDTH - len(icon)))
                    add_frame(" " * safe_pos + icon)

        def add_run(icon, start, end, step=2):
            if start < end:
                rng = range(start, end, step)
            else:
                rng = range(start, end, -step) if step > 0 else range(start, end, step)
            for x in rng:
                safe_x = max(0, min(x, WIDTH - len(icon)))
                add_frame(" " * safe_x + icon)

        zombie_morning = [
            "( 🧟‍♂️ ) ... não... cần... code...",
            "( 🕸️_🕸️ ) ... cà... phê... đâu...",
            "( 😵‍💫 ) ☕ *ực ực*",
            "( 😳 ) ⚡KÍCH HOẠT⚡",
        ]
        add_static_scene(zombie_morning, 10, repeat=2)
        add_run("🏃💨( >﹏<) Đợi em!!", 0, 90, step=4)
        boring_phase = ["( •_•) 📉 ...", "( -_-) 📉 buồn ngủ...", "( o_o) 📈 Ơ?"]
        add_static_scene(boring_phase, 50, repeat=3)
        pump_phase = [
            "( 😲 ) 🚀 LÊN KÌA!!",
            "( 🤪 ) 🚀 TO THE MOON!!",
            "( 🤩 ) 💰 Tiền đè chết người!!",
        ]
        add_static_scene(pump_phase, 50, repeat=3)
        dump_phase = [
            "( 😨 ) 📉 Ủa...",
            "( 😱 ) 📉 RỚT MẠNG RỒI?!",
            "( 💀 ) 💸 Cháy tài khoản...",
        ]
        add_static_scene(dump_phase, 50, repeat=3)
        stress_icons = [
            "   ( 🤯 ) 🔥 BUG Ở ĐÂU???",
            " ( 🤯 )   🔥 TẠI SAO???",
            "   ( 🌋 ) 💣 BÙMMMM!!!!",
        ]
        for _ in range(5):
            for icon in stress_icons:
                add_frame(" " * 48 + icon)
        holy_grail = [
            "( ¬‿¬ ) He he he...",
            "( ⌐■_■ ) Đã tìm ra Bug...",
            "( ✨‿✨ ) All-in lệnh này!",
        ]
        add_static_scene(holy_grail, 50, repeat=3)

        eating = ["( 🍜 ) sụp soạp...", "( 🤤 ) ngon vãi...", "( 🤢 ) ợ..."]
        add_static_scene(eating, 80, repeat=3)

        add_run("🕺(⌐■_■)✨ Tối nay quẩy!", 100, 10, step=3)

        sleep_fail = [
            "( ◡‿◡ ) Nhà đây rồ...",
            "( x_x ) *RẦM* (Ngã sấp mặt)",
            "( 💤_💤 ) Zzzzz...",
        ]
        add_static_scene(sleep_fail, 10, repeat=4)

        funny_quant_runner.frames = frames
        funny_quant_runner.i = 0

    frame = funny_quant_runner.frames[funny_quant_runner.i]
    funny_quant_runner.i = (funny_quant_runner.i + 1) % len(funny_quant_runner.frames)

    return frame





def execute_filtering_task(
    df_main: pl.DataFrame, filters: dict, initial_capital: float
):
    """Thực thi lọc DataFrame theo bộ filters, trả về (lệnh, equity, danh sách coin)."""
    try:
        if df_main is None or df_main.is_empty():
            return [], [{"balance": initial_capital}], []


        expr = pl.lit(True)

        if filters.get("date"):
            expr &= pl.col("filter_date") == filters["date"]

        if filters.get("side"):

            expr &= pl.col("filter_side") == filters["side"]

        if filters.get("weekday") is not None:
            expr &= pl.col("filter_weekday") == filters["weekday"]

        if filters.get("hour") is not None:
            expr &= pl.col("filter_hour") == filters["hour"]


        df_step1 = df_main.filter(expr)

        df_final = df_step1
        if filters.get("symbol"):
            df_final = df_final.filter(pl.col("symbol") == filters["symbol"])


        final_trades = df_final.to_dicts()
        trades_for_coin_list = df_step1.to_dicts()


        if not df_final.is_empty():

            equity_df = df_final.sort("time_close").with_columns(
                [(pl.col("pnl_usd").cum_sum() + initial_capital).alias("balance")]
            )
            balances = [initial_capital] + equity_df["balance"].to_list()
            new_equity = [{"balance": b} for b in balances]
        else:
            new_equity = [{"balance": initial_capital}]

        return final_trades, new_equity, trades_for_coin_list
    except Exception as e:
        print(f"Lỗi logic lọc: {e}")
        return [], [{"balance": initial_capital}], []






__all__ = ["funny_quant_runner", "execute_filtering_task"]
