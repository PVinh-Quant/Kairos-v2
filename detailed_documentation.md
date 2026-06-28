# KAIROS QUANT SYSTEM — Detailed Technical Reference Manual

This document provides a comprehensive technical overview of the architecture, modules, algorithms, database schema, and operational workflows of **KAIROS QUANT SYSTEM v2**.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [System Configuration](#configuration)
3. [Data Pipeline & ETL](#data-pipeline)
4. [Technical Indicator Engine](#indicator-engine)
5. [Strategy & Gating Engine](#strategy-engine)
6. [Machine Learning & Regime Classification](#ml-regime)
7. [Order Execution Layer](#execution-layer)
8. [PyQt6 Analytics Dashboard](#ui-dashboard)
9. [DuckDB Analytical Data Warehouse](#duckdb-warehouse)
10. [Editions Comparison (Base vs. High)](#editions-comparison)

---

<a name="system-overview"></a>

## 1. System Overview

KAIROS is a modular, event-driven quantitative trading and analytics system designed for research and live trading in cryptocurrency markets.

* **`lay_du_lieu/` (Data Ingestion)**: Ingests market data, order books, and macro indicators via REST and WebSocket.
* **`Indicator/` (Technical Indicators)**: Vectorized and bar-by-bar multi-timeframe feature calculations.
* **`chien_luoc/` (Strategy Logic)**: Signal evaluation, portfolio sizing, dynamic leverage, and risk gating.
* **`thuc_thi_lenh/` (Execution Layer)**: Connects to exchange APIs to manage orders, accounts, and positions.
* **`chuc_nang/` (Orchestration)**: Runners for Backtest, Demo, and Realtime modes.
* **`ml/` (Machine Learning)**: Market regime classification models (PyTorch).
* **`hien_thi/` (Visualization)**: PyQt6 terminal and charting workbench.
* **`toi_uu_hoa/` (Optimization)**: Walk-Forward optimizer using Deflated Sharpe Ratio (DSR) guardrails.
* **`utils/` (Utilities)**: Config parser, DuckDB database manager, and logger.

---

<a name="configuration"></a>

## 2. System Configuration

The system uses three primary configuration files located in the `config/` directory:

1. **`cau_hinh_giao_dich.yaml` (Trading Parameters)**:
   * Defines traded asset lists, timeframes, risk management parameters, maximum leverage, ATR-scaled stop loss/take profit multipliers, and capital allocation percentages.
2. **`thong_tin_san.yaml` (Exchange Constraints)**:
   * Caches minimum trade size, tick size, lot step size, and fee rates for target symbols (derived dynamically but cached for offline modes).
3. **`tai_khoan_api.json` (Credentials)**:
   * Holds encrypted API keys, secrets, and subaccount designations. (Excluded from Git control).

---

<a name="data-pipeline"></a>

## 3. Data Pipeline & ETL

The data layer cleanses raw input to ensure zero look-ahead bias and consistent timestamp alignment across different timeframes.

* **Missing Candle Recovery**: Automatically scans time-series data for timestamp gaps. Gaps are forward-filled for OHLCV using the previous `Close` price and zero volume.
* **Multiframe Alignment**: Uses a specialized resampler that groups 1m raw candles into higher timeframes (5m, 15m, 1h, 4h, 1d).
* ** WebSocket Streaming**: Collects CVD (Cumulative Volume Delta), liquidations, book ticker bids/asks, and funding rates at sub-second frequencies.

---

<a name="indicator-engine"></a>

## 4. Technical Indicator Engine

### 4.1 Module Structure (Base Edition)

The open-source `Indicator/` directory consists of 7 functional modules containing **49 indicators (`pt_*`)** in **2,847 lines of code**:

| Module | Lines | Description |
|---|---:|---|
| `xu_huong.py` | 640 | Trend indicators (EMA, SMA, ADX, DMI, Ichimoku, SuperTrend, Aroon, Vortex) |
| `cau_truc_gia.py` | 412 | Price structure (Breakouts, Fractals, Pivot Points, Fair Value Gaps, Heikin Ashi) |
| `dong_luong_dao_chieu.py` | 366 | Momentum & Oscillators (RSI, Stochastic, CCI, Williams %R, Ultimate Oscillator) |
| `bien_dong.py` | 552 | Volatility indicators (ATR, Bollinger Bands, Squeeze, Keltner Channel, Donchian Channel) |
| `khoi_luong.py` | 667 | Volume metrics (OBV, VWAP, Volume Profile POC/VAH/VAL, CMF, A/D, MFI Volume, EoM) |
| `vi_the.py` | 67 | Sentiment & Orderflow (CVD, Funding Rate, Order Book Imbalance, Liquidations) |
| `chu_ky.py` | 143 | Session & Cycle ranges (Asian, London, New York session times) |
| **Total** | **2,847** | **49 indicators** |

### 4.2 Look-ahead Bias Prevention Algorithm

To prevent indicators on higher timeframes (HTF) from leaking future information to lower timeframes (LTF) during backtesting, KAIROS implements a **4-step vectorized alignment**:

1. **Resample**: Aggregate 1m candles to the HTF (e.g., 1h).
2. **Shift**: Shift the HTF index forward by exactly 1 period. A 1h candle starting at 10:00 closes at 11:00. The calculated indicator at 11:00 is assigned to the 11:00 timestamp.
3. **Forward-Fill**: Propagate the shifted HTF value down to the 1m timeline using `ffill()`.
4. **Intrabar Hybrid (for High version)**: Estimates the forming HTF indicator by merging the locked shifted state with current live LTF prices.

---

<a name="strategy-engine"></a>

## 5. Strategy & Gating Engine

KAIROS evaluates market conditions using an ensemble scoring system across 5 core trading strategies:

1. **Breakout (Volatility Expansion)**: Trades volatility breakouts when prices cross range extremes.
2. **Squeeze (Volatility Compression)**: Enters positions when Bollinger Bands contract inside Keltner Channels, anticipating explosive expansion.
3. **Trend Following**: Enters trades in the direction of multi-timeframe EMA and ADX alignments.
4. **Mean Reversion**: Capitalizes on overextended prices returning to the VWAP or EMA means.
5. **Scalping**: Fast-in, fast-out trades targeting minor range boundaries.

### Ensemble Scoring Logic

Each strategy generates a raw score between `-1.0` (strong sell) and `+1.0` (strong buy). The final entry score is aggregated using a weighted matrix:

$$\text{Final Score} = \sum_{i=1}^5 \left( \text{Score}_i \times \text{Weight}_i \times \text{Timeframe Multiplier} \right)$$

This final score is gated by the current ML Market Regime. If the regime indicates high risk or low-volatility consolidation (Regime 0 or 7), the final score is forced to `0` (Hold).

---

<a name="ml-regime"></a>

## 6. Machine Learning & Regime Classification

The ML pipeline identifies the overarching market environment to dictate active strategy weights.

* **Architecture (`TradingMLP`)**: PyTorch-based Multilayer Perceptron with residual blocks, batch normalization, and dropout to prevent overfitting on noisy financial data.
* **Input Layer (80 Dimensions)**: 18 features calculated across 4 timeframes (5m, 15m, 1h, 4h) plus 8 historical memory features.
* **Regime Outputs (0-7)**:
  * `0`: Frozen / Low Volume (No trade)
  * `1`: Squeeze / Compression (Activate Squeeze strategy)
  * `2`: Early Trend / Breakout (Activate Breakout strategy)
  * `3`: Strong Trend (Activate Trend Following strategy)
  * `4`: Climax / Exhaustion (Activate Mean Reversion strategy)
  * `5`: Retracement / Mean Reversion (Activate Mean Reversion strategy)
  * `6`: Turbulent Ranging (Activate Scalping strategy)
  * `7`: Liquidation Sweep / High Risk (No trade)

---

<a name="execution-layer"></a>

## 7. Order Execution Layer

The execution engine translates model outputs into API requests while managing risk real-time.

* **Stop Loss (SL) & Take Profit (TP)**: Set dynamically using the Average True Range (ATR).
  * $\text{SL Price} = \text{Entry Price} \pm (\text{ATR} \times \text{SL Multiplier})$
  * $\text{TP Price} = \text{Entry Price} \mp (\text{ATR} \times \text{TP Multiplier})$
* **Dynamic Leverage**: Calculated based on the market regime volatility, ADX trend strength, and capital drawdowns. Stays clamped between 1x and `max_leverage`.
* **Execution Connector**: Leverages CCXT to handle market, limit, and trailing stop orders with built-in retry mechanisms for rate limits and slippage protection.

---

<a name="ui-dashboard"></a>

## 8. PyQt6 Analytics Dashboard

The system features a multi-tab desktop dashboard built with PyQt6 and PyQtGraph:

1. **Backtest Tab**: Visualizes equity curves, maximum drawdowns, session heatmap grids (Win Rate by hour × day), and trade scatter plots (hold duration vs. PnL).
2. **Realtime Tab**: Monitor active live strategies, open positions, order book depth, and live CVD delta.
3. **Indicator Live Workbench**: Interactive playground to change parameters on the fly and view trading markers overlaid on a candlestick chart.
4. **Optimizer Tab**: Drag-and-drop parameter tuning with Walk-Forward results.

---

<a name="duckdb-warehouse"></a>

## 9. DuckDB Analytical Data Warehouse

KAIROS stores all backtest runs, trade executions, and signal logs in a local analytical warehouse: `du_lieu/kairos_warehouse.duckdb`.

### Warehouse Schema

```sql
-- Schema Definition
CREATE TABLE backtest_run (
    run_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    symbol VARCHAR,
    timeframe VARCHAR,
    start_date DATE,
    end_date DATE,
    initial_capital DOUBLE,
    final_capital DOUBLE,
    sharpe_ratio DOUBLE,
    max_drawdown DOUBLE
);

CREATE TABLE lenh (
    trade_id VARCHAR PRIMARY KEY,
    run_id VARCHAR REFERENCES backtest_run(run_id),
    timestamp TIMESTAMP,
    symbol VARCHAR,
    side VARCHAR, -- 'BUY' or 'SELL'
    entry_price DOUBLE,
    exit_price DOUBLE,
    qty DOUBLE,
    pnl DOUBLE,
    exit_reason VARCHAR -- 'TP', 'SL', 'REVERSAL'
);
```

---

<a name="editions-comparison"></a>

## 10. Editions Comparison (Base vs. High)

### 10.1 Definitions

* **Base / Open** 🔓: The open-source code included in this repository, suitable for learning, testing, and standard backtesting.
* **High / Closed** 🔒: Premium production modules with advanced search capabilities and live intrabar calculations.

### 10.2 Feature Matrix

| Feature | Base / Open (Public) | High / Closed (Proprietary) |
|---|---|---|
| **Indicator Engine** | **49 `pt_*`**, 2.8K lines, HTF confirmed/flat | **68 `pt_*`**, 7.2K lines, live MTF intrabar |
| **Optimizer Engine** | Walk-forward + DSR, 3.0K lines | Directed adaptive search |
| **Machine Learning** | 8 regime, 80 feature, trainer included | Custom architectural layers |
| **Backtesting Speed** | Vectorized & Bar-to-Bar, In-Memory | Same as Base |
| **Code Availability** | ✅ Open source in repo | ❌ Closed source |
