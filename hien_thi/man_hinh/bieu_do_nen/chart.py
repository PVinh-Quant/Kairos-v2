"""bieu_do_nen/chart.py — CoreCandlestickChart: vẽ nến + lệnh entry/exit (paintEvent)."""
import bisect
import polars as pl
import pandas as pd
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PyQt6.QtCore import Qt, QRectF
from hien_thi.giao_dien.theme import Theme
from .tien_ich import to_datetime
class CoreCandlestickChart(QWidget):
    def __init__(self, parent=None):
        """Khởi tạo widget biểu đồ nến với hỗ trợ zoom, pan, và vẽ lệnh."""
        super().__init__(parent)
        self.setMouseTracking(True)
        self.df_current = pl.DataFrame()
        self.current_timestamps = []
        self.trades = []

        self.candle_width = 8
        self.candle_gap = 2
        self.scroll_offset = 0
        self.mouse_pos = None
        self.last_mouse_x = 0
        self.is_panning = False
        self.current_tf = "1m"

    def wheelEvent(self, event):
        """Zoom in/out biểu đồ bằng scroll chuột."""
        delta = event.angleDelta().y()
        self.candle_width = (
            min(40, self.candle_width + 2)
            if delta > 0
            else max(3, self.candle_width - 2)
        )
        self.update()

    def mousePressEvent(self, event):
        """Bắt đầu chế độ pan khi nhấn chuột trái."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.last_mouse_x = event.position().x()

    def mouseReleaseEvent(self, event):
        """Kết thúc chế độ pan khi thả chuột trái."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False

    def mouseMoveEvent(self, event):
        """Cập nhật vị trí chuột và xử lý pan biểu đồ khi kéo."""
        self.mouse_pos = event.position()
        if self.is_panning:
            dx = event.position().x() - self.last_mouse_x
            candles_shifted = int(dx / (self.candle_width + self.candle_gap))
            if candles_shifted != 0:
                self.scroll_offset += candles_shifted
                max_offset = max(0, self.df_current.height - 5)
                self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
                self.last_mouse_x = event.position().x()
        self.update()

    def leaveEvent(self, event):
        """Xóa vị trí chuột khi con trỏ rời khỏi widget."""
        self.mouse_pos = None
        self.update()

    def get_x(
        self, timestamp, start_idx, end_idx, total_candles, chart_w, space_per_candle
    ):
        """Tính tọa độ X của một timestamp trên biểu đồ theo scale logarit."""
        if timestamp is None:
            return -1
        idx = bisect.bisect_left(self.current_timestamps, timestamp)
        if idx < len(self.current_timestamps):
            if idx < start_idx or idx > end_idx:
                return -1
            return (
                chart_w
                - (total_candles - idx - self.scroll_offset) * space_per_candle
                + self.candle_width / 2
            )
        return -1

    def paintEvent(self, event):
        """Vẽ toàn bộ biểu đồ nến, lưới, lệnh, và crosshair tooltip."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Theme.CARD))

        if self.df_current.is_empty():
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Đang chờ dữ liệu..."
            )
            return

        w, h = self.width(), self.height()
        margin_top, margin_bottom, margin_right = 25, 40, 70
        chart_w, chart_h = w - margin_right, h - margin_top - margin_bottom

        space_per_candle = self.candle_width + self.candle_gap
        max_visible_candles = int(chart_w // space_per_candle)
        total_candles = self.df_current.height
        end_idx = total_candles - self.scroll_offset
        start_idx = max(0, end_idx - max_visible_candles)

        if start_idx >= end_idx:
            return
        df_view = self.df_current[start_idx:end_idx]



        n_ts = len(self.current_timestamps)
        view_first_ts = self.current_timestamps[start_idx] if start_idx < n_ts else None
        view_last_ts = self.current_timestamps[end_idx - 1] if 0 < end_idx <= n_ts else None

        timestamps = [to_datetime(ts) for ts in df_view["timestamp"].to_list()]
        opens = df_view["open"].to_list()
        highs = df_view["high"].to_list()
        lows = df_view["low"].to_list()
        closes = df_view["close"].to_list()
        volumes = (
            df_view["volume"].to_list()
            if "volume" in df_view.columns
            else [0] * len(opens)
        )

        min_low, max_high = min(lows), max(highs)
        price_range = max_high - min_low if max_high != min_low else 1
        min_low -= price_range * 0.1
        max_high += price_range * 0.1
        price_range = max_high - min_low

        def get_y(price):
            return margin_top + chart_h - ((price - min_low) / price_range) * chart_h


        grid_pen = QPen(QColor(Theme.GRID), 1, Qt.PenStyle.SolidLine)
        painter.setPen(grid_pen)
        painter.setFont(QFont("Segoe UI", 8))

        for i in range(9):
            py = margin_top + (chart_h / 8) * i
            painter.drawLine(0, int(py), int(chart_w), int(py))
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.drawText(
                int(chart_w + 8), int(py + 4), f"{max_high - (price_range / 8) * i:.4f}"
            )
            painter.setPen(grid_pen)

        fm_time = painter.fontMetrics()
        time_step = max(
            1, int(fm_time.horizontalAdvance("00:00 00/00") * 1.5 // space_per_candle)
        )

        for i in range(len(opens)):
            if (start_idx + i) % time_step == 0:
                x = (
                    chart_w
                    - (len(opens) - i) * space_per_candle
                    + self.candle_width / 2
                )
                painter.drawLine(
                    int(x), int(margin_top), int(x), int(margin_top + chart_h)
                )

        hovered_candle_idx = -1
        max_vol = max(volumes) if volumes and max(volumes) > 0 else 1
        vol_max_height = chart_h * 0.25


        for i in range(len(opens)):
            o, hi, lo, c, vol = opens[i], highs[i], lows[i], closes[i], volumes[i]
            x = chart_w - (len(opens) - i) * space_per_candle
            center_x = x + self.candle_width / 2
            yo, yc, yh, yl = get_y(o), get_y(c), get_y(hi), get_y(lo)
            candle_color = QColor(Theme.WIN) if c >= o else QColor(Theme.LOSS)

            if self.mouse_pos and x <= self.mouse_pos.x() <= x + space_per_candle:
                hovered_candle_idx = i
                painter.fillRect(
                    QRectF(
                        x - self.candle_gap / 2, margin_top, space_per_candle, chart_h
                    ),
                    QColor(255, 255, 255, 8),
                )

            vol_h = (vol / max_vol) * vol_max_height
            vol_brush = QColor(candle_color)
            vol_brush.setAlpha(80)
            painter.fillRect(
                QRectF(x, margin_top + chart_h - vol_h, self.candle_width, vol_h),
                vol_brush,
            )

            painter.setPen(QPen(candle_color, 1.5))
            painter.drawLine(int(center_x), int(yh), int(center_x), int(yl))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(candle_color)
            painter.drawRect(
                QRectF(x, min(yo, yc), self.candle_width, max(abs(yo - yc), 1))
            )


        for i in range(len(opens)):
            if (start_idx + i) % time_step == 0:
                x = (
                    chart_w
                    - (len(opens) - i) * space_per_candle
                    + self.candle_width / 2
                )
                painter.setPen(QPen(QColor(Theme.BORDER), 1.5))
                painter.drawLine(
                    int(x),
                    int(margin_top + chart_h),
                    int(x),
                    int(margin_top + chart_h + 6),
                )

                painter.setPen(QColor(Theme.TEXT_SUB))
                ts = timestamps[i]
                if ts:
                    time_str = (
                        ts.strftime("%H:%M\n%d/%m")
                        if self.current_tf in ["1m", "3m", "5m", "15m"]
                        else ts.strftime("%d/%m\n%H:%M")
                    )
                    painter.drawText(
                        QRectF(x - 30, margin_top + chart_h + 8, 60, 30),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                        time_str,
                    )


        for t in self.trades:
            if "exit_time" not in t:
                continue


            en_time = t["entry_time"]


            if view_first_ts is not None and (en_time < view_first_ts or en_time > view_last_ts):
                continue
            en_idx = bisect.bisect_left(self.current_timestamps, en_time)


            if en_idx >= self.df_current.height:
                continue







            view_idx = en_idx - start_idx
            if not (0 <= view_idx < df_view.height):
                continue

            candle_high = highs[view_idx]
            candle_low = lows[view_idx]


            x1 = self.get_x(
                en_time, start_idx, end_idx, total_candles, chart_w, space_per_candle
            )
            x2 = self.get_x(
                t["exit_time"],
                start_idx,
                end_idx,
                total_candles,
                chart_w,
                space_per_candle,
            )
            y2 = get_y(t["exit_price"])



            direction = t["direction"]
            val = float(t.get("price_change", 0))


            if x1 == -1 and x2 == -1:
                continue



            if x1 == -1:
                x1 = (
                    chart_w
                    - (total_candles - en_idx - self.scroll_offset) * space_per_candle
                    + self.candle_width / 2
                )
            if x2 == -1:
                idx2 = bisect.bisect_left(self.current_timestamps, t["exit_time"])
                x2 = (
                    chart_w
                    - (total_candles - idx2 - self.scroll_offset) * space_per_candle
                    + self.candle_width / 2
                )


            y1_price = get_y(t["entry_price"])


            painter.setPen(QPen(QColor(Theme.TRADE_LINE), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(int(x1), int(y1_price), int(x2), int(y2))


            if 0 <= x1 <= chart_w:
                painter.setPen(Qt.PenStyle.NoPen)
                poly = QPainterPath()
                padding = 6

                if direction == "Long":

                    painter.setBrush(QColor(Theme.ENTRY))
                    y_base = get_y(candle_low)
                    top_y = y_base + padding
                    poly.moveTo(x1, top_y)
                    poly.lineTo(x1 - 6, top_y + 12)
                    poly.lineTo(x1 + 6, top_y + 12)
                    poly.closeSubpath()
                else:

                    painter.setBrush(QColor("#C517FF"))
                    y_base = get_y(candle_high)
                    padding = 6
                    top_y = (
                        y_base - padding
                    )
                    poly = QPainterPath()

                    poly.moveTo(x1, top_y)

                    poly.lineTo(x1 - 6, top_y - 12)

                    poly.lineTo(x1 + 6, top_y - 12)
                    poly.closeSubpath()

                painter.drawPath(poly)


            if 0 <= x2 <= chart_w:
                painter.setPen(QPen(QColor(Theme.EXIT), 2))
                size = 5
                painter.drawLine(
                    int(x2 - size), int(y2 - size), int(x2 + size), int(y2 + size)
                )
                painter.drawLine(
                    int(x2 - size), int(y2 + size), int(x2 + size), int(y2 - size)
                )


            if (
                self.mouse_pos
                and abs(self.mouse_pos.x() - x2) <= space_per_candle
                and 0 <= x2 <= chart_w
            ):
                pnl_str = f"{val:+.2f}"
                tw = fm_time.horizontalAdvance(pnl_str) + 16
                pnl_color = (
                    QColor(Theme.WIN)
                    if val > 0
                    else QColor(Theme.LOSS) if val < 0 else QColor(Theme.TEXT_MAIN)
                )

                bg_col = QColor(pnl_color)
                bg_col.setAlpha(220)
                painter.setBrush(bg_col)
                painter.setPen(QPen(pnl_color, 1))
                painter.drawRoundedRect(QRectF(x2 - tw / 2, y2 - 35, tw, 22), 4, 4)
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(x2 - tw / 2, y2 - 35, tw, 22),
                    Qt.AlignmentFlag.AlignCenter,
                    pnl_str,
                )

        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.drawLine(int(chart_w), 0, int(chart_w), h)
        painter.drawLine(
            0, int(margin_top + chart_h), int(chart_w), int(margin_top + chart_h)
        )




        if self.mouse_pos and hovered_candle_idx != -1:
            mx, my = self.mouse_pos.x(), self.mouse_pos.y()
            mx = max(0, min(mx, chart_w))
            my = max(margin_top, min(my, margin_top + chart_h))
            hover_x = (
                chart_w
                - (len(opens) - hovered_candle_idx) * space_per_candle
                + self.candle_width / 2
            )

            painter.setPen(QPen(QColor(Theme.TEXT_SUB), 1, Qt.PenStyle.DashLine))
            painter.drawLine(
                int(hover_x), int(margin_top), int(hover_x), int(margin_top + chart_h)
            )
            painter.drawLine(0, int(my), int(chart_w), int(my))

            ho, hh, hl, hc, hv = (
                opens[hovered_candle_idx],
                highs[hovered_candle_idx],
                lows[hovered_candle_idx],
                closes[hovered_candle_idx],
                volumes[hovered_candle_idx],
            )
            hover_time = timestamps[hovered_candle_idx]


            trades_here = []
            for t in self.trades:
                en_t = t.get("entry_time")
                ex_t = t.get("exit_time")

                if view_first_ts is not None:
                    en_out = en_t is None or en_t < view_first_ts or en_t > view_last_ts
                    ex_out = ex_t is None or ex_t < view_first_ts or ex_t > view_last_ts
                    if en_out and ex_out:
                        continue
                tx_en = self.get_x(
                    en_t,
                    start_idx,
                    end_idx,
                    total_candles,
                    chart_w,
                    space_per_candle,
                )
                tx_ex = self.get_x(
                    ex_t,
                    start_idx,
                    end_idx,
                    total_candles,
                    chart_w,
                    space_per_candle,
                )
                if abs(hover_x - tx_en) < space_per_candle:
                    trades_here.append((t, "Entry", t["entry_price"]))
                if abs(hover_x - tx_ex) < space_per_candle:
                    trades_here.append((t, "Exit", t["exit_price"]))

            hud_lines = [
                "INFO",
                f"T: {hover_time.strftime('%m-%d %H:%M') if hover_time else ''}",
                f"O: {ho:.2f} | C: {hc:.2f}",
                f"H: {hh:.2f} | L: {hl:.2f}",
            ]
            if trades_here:
                hud_lines.append("TRADE")
                for tr, action, val in trades_here:
                    hud_lines.append(f"ID {tr['id']} ({tr['direction']})")
                    hud_lines.append(f"{action}: {val:.2f}")


            font_hud = QFont("Consolas", 9)
            painter.setFont(font_hud)
            fm_hud = painter.fontMetrics()


            max_w = max([fm_hud.horizontalAdvance(line) for line in hud_lines]) + 15


            box_h = len(hud_lines) * 16 + 10


            hud_x = mx + 20
            hud_y = my + 20
            if mx > chart_w * 0.6:
                hud_x = mx - max_w - 20
            if my > chart_h * 0.6:
                hud_y = my - box_h - 20


            bg_hud = QColor(Theme.CARD)
            bg_hud.setAlpha(240)
            painter.setPen(QPen(QColor(Theme.BORDER), 1))
            painter.setBrush(bg_hud)


            painter.drawRoundedRect(
                int(hud_x), int(hud_y), int(max_w), int(box_h), 4, 4
            )

            curr_y = hud_y + 16
            for line in hud_lines:
                painter.setPen(
                    QColor(Theme.ACCENT)
                    if "INFO" in line or "TRADE" in line
                    else QColor(Theme.TEXT_MAIN)
                )
                painter.drawText(int(hud_x + 10), int(curr_y), line)
                curr_y += 16

            cross_price = max_high - ((my - margin_top) / chart_h) * price_range
            painter.setBrush(QColor(Theme.TEXT_MAIN))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(chart_w), int(my - 10), margin_right, 20)
            painter.setPen(QColor(Theme.BG))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(int(chart_w + 6), int(my + 4), f"{cross_price:.4f}")





