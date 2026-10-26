# Crypto Arbitrage Toolkit

A crypto arbitrage research toolkit, organized by strategy family. It runs
entirely on **free, key-less exchange APIs** (Coinbase, Kraken, Bitstamp, Gemini,
Bitfinex) — crypto is used deliberately because its market data is free and deep,
unlike equities where good history costs hundreds to thousands of dollars.

Two arbitrage families, one shared foundation:

| Subpackage | Strategy | Idea |
| --- | --- | --- |
| `statarb/` | **Statistical arbitrage** | trade the mean-reverting spread of a cointegrated coin pair — with a hand-written z-score rule **or a learned ML / neural-net signal** |
| `crossvenue/` | **Cross-venue & triangular arbitrage** | exploit price gaps of one asset across exchanges, and cyclic (triangular) loops |

> A third crypto strategy, **funding-rate carry** (perpetual-futures), is a
> separate sibling project on the `crypto-funding-carry` branch.

> **Scope.** The plumbing — data, statistics, backtesting, walk-forward
> validation, metrics — is built and tested. The *trading edge* (signal design)
> is left as open research in `statarb/signals.py`. See **Research tasks**.

## Layout

```
cryptostat/
  common/       data.py  stats.py  metrics.py                  # shared foundation
  statarb/      pairs.py  signals.py  ml.py  backtest.py  walkforward.py
  crossvenue/   exchanges.py  crossexchange.py  arbgraph.py
scripts/        01..08  (fetch → screen → backtest → walk-forward → batch →
                         cross-exchange → triangular → ML pairs)
tests/          run_all.py + one suite per module   (37 tests, no pytest needed)
quantconnect/   main.py + spread_ml.py — event-driven port of the ML strategy
                for QuantConnect/LEAN (Binance perps; see quantconnect/README.md)
results/        committed example outputs
```

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests (+ optional matplotlib)

python scripts/01_fetch_universe.py                          # cache ~2y daily prices
python scripts/02_screen_pairs.py                            # rank cointegrated pairs
python scripts/04_walk_forward.py  --a MATIC-USD --b ADA-USD # honest out-of-sample stat-arb
python scripts/08_ml_pairs.py --a LINK-USD --b LTC-USD --both # ML/NN signal vs z-score baseline
python scripts/07_triangular.py                              # cross-venue triangular scan

python tests/run_all.py                # 37 tests
```

```python
import cryptostat as cs                # everything re-exported at top level
panel = cs.price_panel(["BTC-USD", "ETH-USD", "LTC-USD"], days=730)
cs.screen_pairs(panel)                 # statistical arbitrage
wf = cs.walk_forward_ml(panel["LINK-USD"], panel["LTC-USD"], kind="lstm")
print(wf.summary())                    # ML/neural-net pairs signal, out-of-sample
cs.scan_triangular()                   # cross-venue triangular arbitrage
```

---

## 1. Statistical arbitrage (`statarb/`)

Two assets are **cointegrated** if a linear combination of their prices is
stationary even though each wanders. That combination is the **spread**. Screen a
universe (Engle-Granger), estimate the hedge ratio β so `spread = A − β·B` mean
-reverts, then trade its z-score — dollar-neutral, so only the *relationship*
matters, not market direction.

**Walk-forward validation (`walkforward.py`) is the judge.** A plain backtest
fits parameters on the same data it trades — it has seen the future. Walk-forward
re-estimates on a rolling *training* window and trades only the next *unseen*
window; the gap between in-sample and out-of-sample Sharpe is the overfitting
tax. `scripts/05_batch_results.py` runs the top pairs and writes `results/`.

### 1a. The learned signal — ML & neural networks (`statarb/ml.py`)

The z-score band encodes *one* belief: distance from the mean predicts reversion.
`ml.py` lets the data decide instead. It engineers features from the spread's
recent history — current and lagged z-scores, multi-horizon momentum, local
volatility, an RSI of the spread — and **learns** the position:

- **`SpreadNet`** — a compact **PyTorch LSTM** that reads a window of the spread
  sequence and predicts its forward move. This is the neural net the strategy is
  built around; small on purpose, because daily pairs data is short.
- **`GBMSignal`** — a scikit-learn gradient-boosting regressor on the same
  features. A strong classical-ML baseline for the net to beat.
- **`RidgeSignal`** — an L2 linear model, the maximally regularized reference.
  If ridge ties the fancier models OOS, their extra capacity bought only overfit.

All wear the same `MLSignal.fit(train) → predict(test)` contract. The label is
the **forward return of the long-spread trade** (n-step spread change in σ units),
so the model *generalizes* the z-score rule rather than replacing it blindly —
the current z-score is one of its inputs, so it can recover the baseline when
that is all the data supports. A prediction only becomes a trade when it clears a
conviction gate, which controls turnover and cost.

```bash
python scripts/08_ml_pairs.py --a LINK-USD --b LTC-USD --both   # base vs ridge vs gbm vs lstm, OOS
```

**Same judge, no leakage.** `walk_forward_ml` re-trains the model on each rolling
*training* window and trades only the next unseen window; β and the spread
mean/std are frozen from train, and features/labels never touch the future. It
returns the same `WalkForwardResult`, so the in-sample→OOS Sharpe gap still tells
you when a model overfit.

**Overfitting defences** (on by default, each measurable via that gap):

| Lever | What it does | Why it's principled |
| --- | --- | --- |
| `n_ensemble=3` | average predictions of differently-seeded models per fold | pure variance reduction — the seed lottery washes out |
| `z_gate=1.0` | a trade also needs the frozen z-score to agree with its direction as mean reversion (long only a cheap spread, short only a rich one) | the model ranks and times entries but cannot invent trades the cointegration doesn't support |
| capacity control | LSTM: dropout + weight decay + early stopping; GBM: shallow subsampled trees + internal early stopping | fewer effective parameters on a few hundred bars |
| `tune_entry` (opt-in) | picks the conviction gate per fold on a validation tail of the *training* window | the only honest way to tune a hyperparameter — but off by default, since on short windows the tuning itself can overfit the tail |

> **Honest finding.** Measured on five cointegrated Coinbase pairs (~900 daily
> bars, walk-forward, 10 bps costs): ensembling + the z-gate cut the LSTM's
> in-sample→OOS Sharpe gap from ~2.3 to ~0.9 and lifted its mean OOS Sharpe from
> ~0.6 to ~1.1 — and the defended LSTM was the only strategy with a **positive
> OOS Sharpe on every pair** (min +0.32; the z-score baseline went negative on
> one). The plain z-score still has the best *mean* (~1.24 vs ~1.1): on short
> daily data the net buys consistency, not outperformance. Per-fold gate tuning
> was mixed (rescued one pair, hurt another) — hence opt-in. Deliberately *not*
> done: sweeping horizon/feature choices against these same five pairs, which
> would just be overfitting one level up (see multiple-testing caveat below).

> **Honest finding II — walk-forward pair selection (the final judge).** The
> five-pair numbers above have honest *parameters* but biased *selection*: the
> pairs were screened on the same sample they were tested on. A full portfolio
> replay on real data (17 coins, 2023-02→2026-07, pairs re-screened monthly on
> trailing data only, 10 bps costs — `quantconnect/backtest_local.py`) shows
> the edge does not survive honest selection: baseline gross return 0.0%, all
> configs net-negative, and selected pairs persist month-to-month only 16% of
> the time — they are mostly the ~7 false positives per fold that testing 136
> pairs at α=0.05 statistically guarantees. Stricter α, longer windows, and
> persistence filters don't fix it. **Daily crypto pairs stat-arb, honestly
> selected and honestly costed, had no edge on this period.** The caveat below
> predicted exactly this; now it's measured.

## 2. Cross-venue & triangular arbitrage (`crossvenue/`)

`exchanges.py` pulls the *same* asset from five USD venues. Two lenses:

- **Cross-exchange** (`crossexchange.py`, `scripts/06`): buy on the cheapest
  venue, sell on the dearest — live scan net of taker fees + historical
  dislocation stats.
- **Triangular / cyclic** (`arbgraph.py`, `scripts/07`): model every conversion
  `X → Y` at a venue as a graph edge and find profitable loops `USD → … → USD`,
  each leg on its best exchange (the Bellman-Ford negative-cycle view). A 2-leg
  loop is cross-exchange; a 3-leg loop is a triangle.

**Honest finding (`results/`):** between major USD venues, gross gaps (single
-digit to low-tens of bps) rarely beat ~50–100 bps round-trip taker fees. Using
more venues *does* widen the best loop and surface a positive gross edge, but
each extra leg adds a fee (so longer loops net *worse*), and cross-venue legs need
slow transfers — **0 executable loops after fees.** Markets are efficient; the
value is measuring exactly why.

> **Funding-rate carry** — the third crypto strategy (perpetual-futures) — lives
> on the separate `crypto-funding-carry` branch, since it's a risk-premium
> strategy rather than arbitrage.

---

## Research tasks (the open, meaty part)

Each is a self-contained experiment — implement, backtest, keep only what survives
**out-of-sample**:

1. **Walk-forward everything.** Built for stat-arb (`walkforward.py`); use OOS
   Sharpe as the only judge. Extend it to walk-forward *pair selection* (choosing
   pairs on the training window only) to kill selection bias.
2. **Dynamic hedge ratio (Kalman filter)** for the stat-arb spread.
3. **Half-life-aware signals & time-stops.**
4. **Portfolio of pairs** with a risk budget, instead of one pair at a time.
5. **Cross-venue execution simulator** with latency and transfer times.

## Honest caveats

- Stat-arb screening tests cointegration on log-prices while the backtester forms
  the raw spread — reconcile these (log-spread trading).
- Multiple-testing bias: screening hundreds of pairs surfaces some cointegrated
  by luck. Out-of-sample validation is not optional.
- This is a **research/backtest toolkit, not a live trader** — no broker hookup.

## Tests

`tests/run_all.py` validates each module on synthetic data with known truth:
cointegration stats, the pairs backtester, the walk-forward harness (no leakage),
the ML/neural-net signal (features are leak-free, the models learn a genuine OU
spread out-of-sample, the driver is deterministic and never peeks at the test
window), and the cross-exchange / triangular arbitrage math. **All 37 pass**, no
pytest required.
