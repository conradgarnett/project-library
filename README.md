# Crypto Quant Toolkit

A multi-strategy crypto quant research toolkit, organized by strategy family. It
runs entirely on **free, key-less exchange APIs** (Coinbase, Kraken, Bitstamp,
Gemini, Bitfinex, OKX) — crypto is used deliberately because its market data is
free and deep, unlike equities where good history costs hundreds to thousands of
dollars.

Three strategy families, one shared foundation:

| Subpackage | Strategy | Idea |
| --- | --- | --- |
| `statarb/` | **Statistical arbitrage** | trade the mean-reverting spread of a cointegrated coin pair |
| `crossvenue/` | **Cross-venue & triangular arbitrage** | exploit price gaps of one asset across exchanges, and cyclic (triangular) loops |
| `funding/` | **Funding-rate carry** | harvest perpetual-swap funding with a delta-neutral position |

> **Scope.** The plumbing — data, statistics, backtesting, walk-forward
> validation, metrics — is built and tested. The *trading edge* (signal design)
> is left as open research in `statarb/signals.py`. See **Research tasks**.

## Layout

```
cryptostat/
  common/       data.py  stats.py  metrics.py         # shared foundation
  statarb/      pairs.py  signals.py  backtest.py  walkforward.py
  crossvenue/   exchanges.py  crossexchange.py  arbgraph.py
  funding/      data.py  carry.py
scripts/        01..08  (fetch → screen → backtest → walk-forward → batch →
                         cross-exchange → triangular → funding carry)
tests/          run_all.py + one suite per module   (30 tests, no pytest needed)
results/        committed example outputs
```

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests (+ optional matplotlib)

python scripts/01_fetch_universe.py                          # cache ~2y daily prices
python scripts/02_screen_pairs.py                            # rank cointegrated pairs
python scripts/04_walk_forward.py  --a MATIC-USD --b ADA-USD # honest out-of-sample stat-arb
python scripts/07_triangular.py                              # cross-venue triangular scan
python scripts/08_funding_carry.py                           # funding-rate carry

python tests/run_all.py                # 30 tests
```

```python
import cryptostat as cs                # everything re-exported at top level
panel = cs.price_panel(["BTC-USD", "ETH-USD", "LTC-USD"], days=730)
cs.screen_pairs(panel)                 # statistical arbitrage
cs.scan_triangular()                   # cross-venue triangular arbitrage
cs.carry_backtest(cs.funding_history("BTC"))   # funding-rate carry
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

## 3. Funding-rate carry (`funding/`)

Perpetual swaps never expire, so a **funding rate** paid every 8 hours tethers the
perp to spot: when the crowd is long, longs pay shorts. Hold **long spot + short
perp** and your price exposure cancels while you *collect that funding* — a
market-neutral yield. Unlike the arbitrage above, this is a **risk premium**, not
a fleeting mispricing, so it persists and isn't latency-bound.

`funding/data.py` pulls OKX funding history (free); `carry.py` backtests the
delta-neutral carry (naive long-basis, or `flip` to always collect).
`scripts/08_funding_carry.py` writes `results/funding/`.

**Honest finding:** in the current calm regime, funding is modest — BTC ≈ +1.7%,
ETH ≈ +2.1%, DOGE ≈ +4.2% annualized (memecoins draw crowded longs) — so carry
yields are low single digits (they run far richer in bull markets). Reported
Sharpes look huge (8–20) **only because the model assumes a perfect hedge**, i.e.
a near-zero-variance funding drip; that number excludes the real risks —
exchange/counterparty failure (FTX), perp-leg liquidation on sharp moves, and
basis drift. The naive long-basis version beats `flip` here because flipping on
every funding sign-change churns fees.

---

## Research tasks (the open, meaty part)

Each is a self-contained experiment — implement, backtest, keep only what survives
**out-of-sample**:

1. **Walk-forward everything.** Built for stat-arb (`walkforward.py`); use OOS
   Sharpe as the only judge. Extend it to walk-forward *pair selection* (choosing
   pairs on the training window only) to kill selection bias.
2. **Dynamic hedge ratio (Kalman filter)** for the stat-arb spread.
3. **Half-life-aware signals & time-stops.**
4. **Portfolio of pairs / portfolio of carry** with a risk budget.
5. **Realistic funding carry:** add basis drift, margin/liquidation modeling, and
   exchange-risk haircuts so the Sharpe reflects real risk, not the ideal hedge.
6. **Cross-venue execution simulator** with latency and transfer times.

## Honest caveats

- Stat-arb screening tests cointegration on log-prices while the backtester forms
  the raw spread — reconcile these (log-spread trading).
- Multiple-testing bias: screening hundreds of pairs surfaces some cointegrated
  by luck. Out-of-sample validation is not optional.
- Funding carry Sharpes assume a perfect hedge and ignore counterparty/liquidation
  risk — treat them as idealized.
- This is a **research/backtest toolkit, not a live trader** — no broker hookup.

## Tests

`tests/run_all.py` validates each module on synthetic data with known truth:
cointegration stats, the pairs backtester, the walk-forward harness (no leakage),
cross-exchange and triangular arbitrage math, and the funding carry (positive
funding earns, negative loses without flip, fees reduce returns). **All 30 pass**,
no pytest required.
