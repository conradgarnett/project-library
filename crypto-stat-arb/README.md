# Crypto Arbitrage Toolkit

A crypto arbitrage research toolkit, organized by strategy family. It runs
entirely on **free, key-less exchange APIs** (Coinbase, Kraken, Bitstamp, Gemini,
Bitfinex) — crypto is used deliberately because its market data is free and deep,
unlike equities where good history costs hundreds to thousands of dollars.

Two arbitrage families, one shared foundation:

| Subpackage | Strategy | Idea |
| --- | --- | --- |
| `statarb/` | **Statistical arbitrage** | trade the mean-reverting spread of a cointegrated coin pair |
| `crossvenue/` | **Cross-venue & triangular arbitrage** | exploit price gaps of one asset across exchanges, and cyclic (triangular) loops |

> A third crypto strategy, **funding-rate carry** (perpetual-futures), is a
> separate sibling project on the `crypto-funding-carry` branch.

> **Scope.** The plumbing — data, statistics, backtesting, walk-forward
> validation, metrics — is built and tested. The *trading edge* (signal design)
> is left as open research in `statarb/signals.py`. See **Research tasks**.

## Layout

```
cryptostat/
  common/       data.py  stats.py  metrics.py         # shared foundation
  statarb/      pairs.py  signals.py  backtest.py  walkforward.py
  crossvenue/   exchanges.py  crossexchange.py  arbgraph.py
scripts/        01..07  (fetch → screen → backtest → walk-forward → batch →
                         cross-exchange → triangular)
tests/          run_all.py + one suite per module   (25 tests, no pytest needed)
results/        committed example outputs
```

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests (+ optional matplotlib)

python scripts/01_fetch_universe.py                          # cache ~2y daily prices
python scripts/02_screen_pairs.py                            # rank cointegrated pairs
python scripts/04_walk_forward.py  --a MATIC-USD --b ADA-USD # honest out-of-sample stat-arb
python scripts/07_triangular.py                              # cross-venue triangular scan

python tests/run_all.py                # 25 tests
```

```python
import cryptostat as cs                # everything re-exported at top level
panel = cs.price_panel(["BTC-USD", "ETH-USD", "LTC-USD"], days=730)
cs.screen_pairs(panel)                 # statistical arbitrage
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
and the cross-exchange / triangular arbitrage math. **All 25 pass**, no pytest
required.
