"""
hien_thi.thanh_phan — THÀNH PHẦN UI dùng chung (components/widgets).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Widget tái sử dụng giữa nhiều màn hình. Mỗi thành phần một file:

    from hien_thi.thanh_phan.the_keo import DraggableCard
    from hien_thi.thanh_phan.bang import TableBase, PositionsTable

Hiện rỗng (scaffold). Đích di trú Phase sau cho các bản đang TRÙNG trong
`man_hinh/`: DraggableCard (demo/realtime/backtest), TableBase/PositionsTable/
HistoryTable (demo↔realtime), SummaryBox, MarketHeatmap... Xem README.md.
"""
