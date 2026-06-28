# Version Comparison — Open (PoC) vs Closed (High)

> This document compares the **performance** and **application** of the engine versions in the KAIROS QUANT SYSTEM.
> All scale metrics (lines of code, function counts, indicator counts) are **actually measured from the source code**; performance speed metrics are presented qualitatively and based on code scale (absolute figures depend on the dataset and hardware).
> 
> 🔒 This document **does not describe the internal principles/algorithms** of the closed-source versions — it only discusses *what they achieve*, *inputs/outputs*, *performance*, and *use cases*.

---

## 0. TL;DR

| Engine | Edition | Source Code | Scale | Position |
|---|---|:---:|:---:|---|
| **Indicator** | `Indicator/` | 🔓 Open | 1.0x | Public foundation — **flat** HTF (forward-fill closed candles) |
| **Indicator** | `Indicator_high` | 🔒 Closed | ~2.5x | Production — broad scope + depth + **live MTF** |
| **Optimizer** | `toi_uu_hoa/` | 🔓 Open | 1.0x | Demonstrates parameter tuning workflows |
| **Optimizer** | `toi_uu_hoa_high` | 🔒 Closed | ~1.14x | Production — adaptive search |

**In one sentence:** The **open** edition is sufficient to run the entire pipeline end-to-end and understand the methodology; the **closed** edition adds *broader indicator coverage*, *higher signal depth*, *live HTF indicator updates* in the current candle, and a *much faster converging optimizer* with the same number of trials.

---

## 1. Version Map

```text
Indicator (Feature Engine)              Optimizer (Parameter Tuning)
├── Indicator/        🔓  base          ├── toi_uu_hoa/       🔓  open / PoC
└── Indicator_high    🔒  high          └── toi_uu_hoa_high   🔒  high / production
```

Sharing the same **function interface** (`pt_*` for indicators; `run_*_optimization` for the optimizer) → the versions are **mutually swappable** without modifying the pipeline. Upgrading only requires changing the import directory, without changing the architecture.

---

## 2. Indicator Engine — base vs high

### 2.1 Scale (Actual Measurement)

| Metric | `Indicator/` (base 🔓) | `Indicator_high` (🔒) |
|---|:---:|:---:|
| Number of `.py` files | 7 | 7 |
| **Total lines of code** | 2,847 | 7,179 |
| **Number of indicators** (`pt_*`) | **49** | **68** |
| Total functions (`def`) | 84 | 127 |
| Relative scale | 1.00x | ~2.5x |

> The `base` version is **slimmer than before** (2,847 lines) after removing the entire "live MTF" branch — it now only calculates already closed HTF candles and distributes them.

### 2.2 Detail by Module (Lines of Code)

| Module | base | high | Indicator Group Meaning |
|---|:---:|:---:|---|
| `xu_huong.py` | 640 | 1,761 | Trend (EMA/MACD/ADX/Ichimoku/SuperTrend…) |
| `cau_truc_gia.py` | 412 | 1,540 | Price Structure (Breakout/FVG/Order Block/S-R…) |
| `dong_luong_dao_chieu.py` | 366 | 1,510 | Momentum & Reversal (RSI/Stoch/CCI…) |
| `bien_dong.py` | 552 | 1,125 | Volatility (ATR/Bollinger/Keltner…) |
| `khoi_luong.py` | 667 | 922 | Volume (OBV/VWAP/CMF/Volume Profile…) |
| `vi_the.py` | 67 | 213 | Position/Sentiment (CVD/Funding/OB Imbalance) |
| `chu_ky.py` | 143 | 108 | Session & Cycle (Asian/London/NY) |

### 2.3 Functional Differences

The `high` version outperforms the `base` in **3 aspects** (feature level, without describing principles):

| Aspect | Explanation |
|---|---|
| **Scope (breadth)** | Indicator count **49 → 68** (+19): adds advanced indicator families (HMA/KAMA/TRIX/ALMA/VWMA…) → more perspectives for the same bar. |
| **Depth (features)** | ~2.5× lines of code: each indicator outputs **more normalized (dimensionless) features**, processed more finely → higher resolution signals, comparable across symbols, more precise threshold tuning. |
| **Live MTF** 🔒 | HTF indicators in `high` **update live within the current forming candle** (early response). The `base` version **distributes closed HTF candles (flat)** — this is the core difference between free and production. |

### 2.4 Regarding True Intrabar

Even though the `high` version supports HTF Live/Intrabar, the library does not attempt to implement absolute True Intrabar for every single indicator.

The reason is that some indicators have recursive formulas (recursive state) or depend on many historical states of the HTF candle currently forming. To achieve 100% True Intrabar, the system would continuously have to rebuild intermediate HTF sequences or update internal states in a much more complex manner, significantly increasing computational cost and implementation complexity.

### 2.5 Practical Implementation of Intrabar in KAIROS

To balance calculation speed and accuracy, the intrabar logic is classified into three groups:

1. **Fully Live (Intrabar):** Indicators whose current value depends only on the current price (e.g., VWAP deviation, Bollinger Band deviation of 1m price relative to HTF bands).
2. **Step Live (Hybrid):** The historical part uses closed HTF bars (locked state), while the current forming bar uses a fast approximation calculation (e.g., taking the closed HTF EMA and updating it with the current 1m price).
3. **Confirmed Only (Flat):** Indicators with recursive states that are too complex to estimate intrabar. These indicators will only update when the HTF candle closes, maintaining a constant (flat) value during the forming period.

---

## 3. Optimizer Engine — open vs high (closed)

### 3.1 Scale (Actual Measurement)

| Metric | `toi_uu_hoa/` (open 🔓) | `toi_uu_hoa_high` (🔒) |
|---|:---:|:---:|
| Number of `.py` files | 10 | 10 |
| **Total lines of code** | 3,023 | 3,435 |
| Total functions (`def`) | 56 | 66 |
| Coordinator `bo_dieu_phoi.py` | 1,277 lines | **1,609 lines** (+26%) |
| Backtest engine `dong_co_backtest.py` | 492 dòng | 492 dòng — **giống hệt** |
| Parameter Space Registry `dang_ky_chi_bao.py` | 100 dòng | 123 dòng |

### 3.2 Key Points

> **The backtest engine is identical in both editions** (`dong_co_backtest.py` shares the same lines of code, same SL/TP/fees/slippage logic).
> This means **raw calculation speed (trials/second) is identical** — the difference lies in **the search intelligence**, not in the speed of each individual trial.

| Feature | `toi_uu_hoa/` (open) | `toi_uu_hoa_high` (closed) |
|---|---|---|
| Search Method | Flat search / random sampling — **no learning** from previous trials | **Directed adaptive search** — prioritizes promising parameter spaces *(internal mechanism: closed-source)* |
| Walk-Forward IS/OOS | ✅ | ✅ (extended) |
| Deflated Sharpe Ratio + Deploy Guardrails | ✅ | ✅ |
| Convergence | Requires **more trials** to find good configurations | Reaches **the same quality with far fewer trials** |
| Source Code | 🔓 Open | 🔒 Closed |

### 3.3 Inputs / Outputs (Same for Both Editions)

- **Input:** Single indicator / multi-timeframe combination (AND logic), data range (symbols + dates), number of trials, target metric (Sharpe/Sortino…).
- **Output:** Best parameter set + entry/exit thresholds (JSON artifact) · ranking table · Walk-Forward IS/OOS report · DSR/Sharpe/Sortino metrics · equity/drawdown/PnL chart.
- **Deploy Guardrails:** DSR ≥ 90% · OOS/IS ratio ≥ 0.8 · OOS Trades ≥ 30 · Profit Factor ≥ 1.2.

### 3.4 Performance

- **Throughput per trial:** Identical (shared in-memory backtest engine, running thousands of trials without I/O bottleneck).
- **Search efficiency (quality/trial):** The `high` version is **significantly higher** — with the same "budget" of trials, the open version must rely on random luck, whereas the high version targets the sweet spot → **saving actual time to reach a deployable configuration**.
- Both editions support **early stopping** while retaining the best current result.

### 3.5 Use Cases

| Scenario | Suitable Edition |
|---|---|
| Understanding the walk-forward + DSR process, small-scale tuning, teaching/learning | `toi_uu_hoa/` 🔓 |
| Large-scale multi-timeframe optimization, requiring fast convergence, production use | `toi_uu_hoa_high` 🔒 |

---

## 4. Summary Performance Matrix

| Criterion | Indicator base 🔓 | Indicator high 🔒 | Optimizer open 🔓 | Optimizer high 🔒 |
|---|:---:|:---:|:---:|:---:|
| Indicator Scope (`pt_*`) | 49 | 68 | — | — |
| Signal Depth/Resolution | ◐ | ●● | — | — |
| Feature Generation Speed | ●● (lightest) | ◐ (heaviest) | — | — |
| Backtest Speed per Trial | — | — | ●● | ●● (identical) |
| Search Efficiency per Trial | — | — | ◐ | ●● |
| Production Readiness | ◐ | ●● | ◐ | ●● |
| Source Code | Open | Closed | Open | Closed |

> Key: ◐ basic · ◑ good · ●● strong. This is a **relative rating**, not an absolute benchmark —
> please measure on your own dataset and hardware for exact numbers.

---

## 5. Which Edition to Choose? (Decision Summary)

- **For learning / demo / PoC:** `Indicator/` + `toi_uu_hoa/` (both open) — runs the entire end-to-end pipeline.
- **For serious strategy research, requiring many indicators:** Upgrade to `Indicator_mid` (commercial).
- **For production, multi-symbol, large-scale optimization:** `Indicator_high` + `toi_uu_hoa_high`.

---

## 6. Licensing & Scope

- The **open** edition (`Indicator/`, `toi_uu_hoa/`) is included in this repository, sufficient to demonstrate the entire methodology.
- The **closed** edition (`Indicator_mid`, `Indicator_high`, `toi_uu_hoa_high`): internal algorithms, mathematical formulas, and advanced performance optimizations are kept proprietary. Contact the author for licensing details.

*See also:* [README → Editions](README.md#editions)
