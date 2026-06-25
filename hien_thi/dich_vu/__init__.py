"""
hien_thi.dich_vu — DỊCH VỤ nền cho UI (workers / data access).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QThread/worker và lớp truy xuất dữ liệu mà UI gọi để tách tác vụ nặng khỏi
luồng giao diện:

    from hien_thi.dich_vu.worker import BacktestWorker, DataProcessorWorker

Hiện rỗng (scaffold). Đích di trú Phase sau cho các worker đang TRÙNG/rải rác:
BacktestWorker (bieu_do_nen/backtest), DataProcessorWorker, TradingBridge,
ComboWorker, StrategyWorker, ProcessWorkerThread. Cần gốc dự án thì dùng
`from hien_thi.duong_dan import PROJECT_ROOT, DU_LIEU`.
"""
