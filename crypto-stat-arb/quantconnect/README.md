# QuantConnect port — ML statistical-arbitrage portfolio

Full event-driven port of `cryptostat`'s ML/neural-net pairs strategy for
QuantConnect (LEAN), extended with the research repo's own task list: walk-forward
pair screening, a multi-pair book with risk budgeting, Kalman dynamic hedging,
half-life time stops, volatility targeting, and a drawdown kill-switch.

| file | role |
| --- | --- |
| `main_standalone.py` | **the one-paste deploy** (~2,000 lines, spread_ml embedded) |
| `main.py` | the `QCAlgorithm` (two-file layout source) |
| `spread_ml.py` | QC-agnostic quant library + embedded self-test suite |
| `build_standalone.py` | regenerates `main_standalone.py` after edits |

## Deploy

**Easiest — single file:** create a Python project on
[quantconnect.com](https://www.quantconnect.com), paste **`main_standalone.py`**
over the project's `main.py`, hit **Backtest**.

**Two-file layout:** replace `main.py`, then **Add File** → exactly
`spread_ml.py` → paste it in.

> `No module named 'spread_ml'` at Initialize = the second file is missing —
> add it, or use the standalone build.

**Before deploying, run the self-test locally** (seconds, numpy-only, torch/
sklearn tests self-skip): `python quantconnect/spread_ml.py` → expect `ALL OK`.

## What it does

- **Monthly rebuild** (`self.Train`, off the data thread): screens all ~90 pairs
  of a 14-perp universe for cointegration **on the training window only**
  (walk-forward pair selection — no selection bias), picks the top `MAX_PAIRS`
  candidates, re-fits hedge + ML ensemble per pair, freezes parameters.
- **Daily trading**: each `PairEngine` consumes its bars → {-1, 0, +1}
  (Kalman/OLS/TLS hedge, LSTM→GBM→ridge model with the z-agreement gate,
  half-life time stop + cooldown); inverse-risk budgets across pairs;
  vol-targeted gross with a drawdown kill-switch; tolerance-band rebalancing.
- **Telemetry**: weekly book-state log, per-pair paper P&L attribution,
  fee tracking, margin-call handlers, risk charts, end-of-run report.

## Key knobs (top of the algorithm; all overridable as QC Parameters)

`MODEL_KIND` — `lstm` / `gbm` / `ridge` / **`zscore`** (the research baseline —
run it first, it's the control group) · `HEDGE_METHOD` — `ols`/`tls`/`kalman` ·
`MAX_PAIRS=4` · `TRAIN_DAYS=250` · `ENTRY_SIGMA` · `N_ENSEMBLE=3` · `Z_GATE=1.0`
· `TUNE_ENTRY` (opt-in) · `GROSS_TARGET=0.9` · `TARGET_VOL=0.15` ·
`MAX_DRAWDOWN=0.20` · `TIME_STOP_HL=3`.

## Workarounds (per the "make it work on QC" rule)

| research repo | QC reality | workaround |
| --- | --- | --- |
| short one leg | Coinbase on QC = cash, no shorting | Binance USDT **perps** default; `USE_PERPS=False` → Bitfinex margin spot |
| `walk_forward_ml` folds | no vectorized harness | monthly `Train()` rebuild, frozen β/μ/σ — same no-leakage protocol |
| torch / sklearn | may be absent locally | auto-fallback `lstm → gbm → numpy ridge`, logged (`resolved_kind`) |
| statsmodels / scipy | not guaranteed | never used; full auto-lag ADF + Engle-Granger hand-rolled in numpy |
| `cost_bps` proxy | QC prices trades for real | removed — brokerage fee/margin models apply |

## Fidelity & verification

- Statistics port (`adf_test`, `engle_granger`, `hedge_ratio`, `half_life`) is
  numerically identical to `cryptostat`'s.
- Event-driven trailing-buffer prediction == the vectorized research backtest,
  0 mismatches (asserted in the self-test, all model kinds).
- 29-check embedded self-test covers stats, Kalman adaptation after a
  structural break, signals, gates, screening, the engine state machine
  (stand-down, time stop, attribution), the risk manager, and budgets.

## Backtest results on real data (read this before deploying)

`backtest_local.py` replays the exact strategy components over real Coinbase
daily closes — 17 symbols, 2022-06 → 2026-07, 250-day warm-up, monthly
walk-forward rebuilds, 10 bps/side:

| config | total | Sharpe | maxDD |
| --- | --- | --- | --- |
| zscore baseline | −8.3% | −0.14 | −19.6% |
| ridge | −48.5% | −1.09 | −52.0% |
| gbm | −53.9% | −1.29 | −56.8% |
| lstm | −35.9% | −0.91 | −39.8% |

**Verdict: no edge.** At zero fees the baseline's gross return is exactly 0.0%
— honest **walk-forward pair selection** is what kills it. The monthly screen
tests ~136 pairs at α=0.05 (~7 false positives per fold expected under pure
noise); selected pairs show only 16% month-to-month persistence, i.e. they are
mostly multiple-testing luck, and luck has no out-of-sample edge. The ML models
do *worse* than the baseline because they trade spurious "cointegration"
aggressively. Mitigations tested (α=0.01, 500-day windows, 2-fold persistence
requirement, all combinations): every variant still loses.

The earlier per-pair research numbers (OOS Sharpe ~1.2 on 5 pairs) had honest
*parameters* but biased *selection* — those pairs were screened on the same
sample they were then tested on. The harness itself is validated: on synthetic
panels with planted cointegrated pairs it is profitable end-to-end.

**Practical implication:** don't deploy this expecting profits on daily crypto
pairs. Its value is the framework — honest selection, honest validation, real
cost accounting — and the negative result it surfaced, which the research
repo's own README predicted ("multiple-testing bias: screening hundreds of
pairs surfaces some cointegrated by luck").

## Caveats

- **Perps carry funding** the local research backtest never saw; treat funding
  as an extra cost when comparing numbers.
- **Data start varies by perp** (~2020+); the algorithm stays flat and logs it
  until 200+ aligned daily bars exist. If nothing trades, read the rebuild logs
  first — preferring flat over a broken relationship is by design.
- **The local repo remains the research judge.** QC gives realistic execution
  on one path; the walk-forward harness gives the in-sample→OOS overfitting
  gap. Iterate locally, confirm on QC.
