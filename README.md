# Crypto Statistical Arbitrage

A research toolkit for **market-neutral pairs trading on crypto**: find two coins
whose prices move together, trade the spread when it diverges, and profit as it
reverts to its historical relationship.

Crypto is used deliberately — its market data is **free and deep** (full history,
down to the minute, from public exchange APIs), so the entire pipeline runs with
**no paid data feeds and no API keys**, unlike equities where good history costs
hundreds to thousands of dollars.

> **Scope.** The plumbing — data, cointegration statistics, pair screening, the
> backtest engine, and performance metrics — is built and tested. The *trading
> edge* (signal design) is deliberately left as open research in
> [`cryptostat/signals.py`](cryptostat/signals.py). See **Research tasks** below.

---

## The idea

Two assets are **cointegrated** if some linear combination of their prices is
stationary (mean-reverting) even though each price on its own wanders. That
stationary combination is the **spread**. The strategy:

1. **Screen** a universe of coins for cointegrated pairs (Engle-Granger test).
2. For a pair, estimate the **hedge ratio** β so that `spread = A − β·B` is
   mean-reverting, and measure its **half-life**.
3. **Trade** the spread's z-score: short it when unusually high, buy it when
   unusually low, exit as it reverts. The position is dollar-neutral, so it
   makes money whether the market goes up or down — only the *relationship*
   matters.

## Pipeline

```
data.price_panel   →   pairs.screen_pairs   →   backtest.backtest_pair   →   metrics
 free exchange          Engle-Granger +          dollar-neutral spread       Sharpe,
 OHLCV (cached)         half-life ranking        trading + costs             drawdown, ...
```

| Module | Role |
| --- | --- |
| `cryptostat/data.py` | Free key-less OHLCV from Coinbase (paginated history) & Kraken, with CSV caching; aligned price panels |
| `cryptostat/exchanges.py` | Multi-venue layer over **5 free USD exchanges** (Coinbase, Kraken, Bitstamp, Gemini, Bitfinex): daily-close panels and live bid/ask quotes for the same asset |
| `cryptostat/crossexchange.py` | **Cross-exchange arbitrage**: live buy-here/sell-there scan net of taker fees, and historical cross-venue dislocation stats |
| `cryptostat/stats.py` | ADF unit-root test, Engle-Granger cointegration, OLS/TLS hedge ratio, OU half-life, z-score — all pure numpy/scipy |
| `cryptostat/pairs.py` | Scan every pair in a universe, rank cointegrated candidates by test statistic and half-life |
| `cryptostat/signals.py` | Baseline z-score signal **+ the research surface (your edge goes here)** |
| `cryptostat/backtest.py` | Vectorized, look-ahead-free pairs backtester with transaction costs |
| `cryptostat/walkforward.py` | **Out-of-sample validation**: re-fit on a rolling train window, trade only the next unseen window; reports the in-sample-vs-OOS overfitting gap |
| `cryptostat/metrics.py` | Sharpe, Sortino, Calmar, max drawdown, hit rate, equity curve |
| `scripts/` | `01_fetch_universe` → `02_screen_pairs` → `03_backtest_pair` → `04_walk_forward`; `05_batch_results` writes a `results/` folder; `06_cross_exchange` hunts cross-venue arbitrage |
| `tests/` | Cointegration + backtest correctness on synthetic series with known truth |

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests (+ optional matplotlib)

python scripts/01_fetch_universe.py     # download ~2y daily prices (cached to data/)
python scripts/02_screen_pairs.py       # rank cointegrated pairs
python scripts/03_backtest_pair.py --a BCH-USD --b LTC-USD   # in-sample backtest
python scripts/04_walk_forward.py  --a MATIC-USD --b ADA-USD # honest out-of-sample test

python tests/run_all.py                 # 21 tests, no pytest needed
```

```python
from cryptostat import price_panel, screen_pairs, backtest_pair, performance_summary
panel = price_panel(["BTC-USD", "ETH-USD", "LTC-USD", "BCH-USD"], days=730)
pairs = screen_pairs(panel)                                  # ranked candidates
res = backtest_pair(panel["BCH-USD"], panel["LTC-USD"])
print(performance_summary(res.returns).as_dict())
```

## Method notes

- **Cointegration (Engle-Granger):** regress A on B, then ADF-test the residual
  spread for stationarity. Uses Engle-Granger-specific critical values (stricter
  than a plain ADF because the spread is fitted, not observed).
- **Half-life:** from an Ornstein-Uhlenbeck / AR(1) fit, `half-life = −ln2 / b`.
  It filters pairs: too fast reverts into transaction costs, too slow ties up
  capital.
- **No look-ahead:** the position earns P&L on the *next* period, and the
  z-score uses a trailing window only.

## Cross-exchange arbitrage

A second, different arbitrage lens: instead of two *assets* on one venue, look at
one *asset* across many venues. `cryptostat/exchanges.py` pulls the same coin
from five free USD exchanges; `cryptostat/crossexchange.py` hunts dislocations.

```python
from cryptostat.crossexchange import scan_live_arbitrage, cross_exchange_spread, dislocation_stats
scan_live_arbitrage(["BTC", "ETH", "SOL"])          # live buy-here/sell-there, net of fees
sp = cross_exchange_spread("SOL", days=300)         # historical dearest-vs-cheapest spread
dislocation_stats(sp, fee_bps=80)                   # how often the gap beat round-trip fees
```

`python scripts/06_cross_exchange.py` writes `results/cross_exchange/`. The honest
finding: between major USD venues, live gross gaps (single-digit to low-tens of
bps) rarely beat ~50-100 bps round-trip taker fees, so **executable spot arbitrage
is essentially zero** — markets are efficient. Real, fleeting edges show up only in
volatility spikes and on thinner altcoins (in one run AAVE's cross-venue spread
beat fees on 2.3% of days vs 0% for BTC), and capturing them needs low-latency
execution with balances pre-positioned on both venues. Measuring exactly that is
the point.

## Research tasks (the open, meaty part)

The baseline signal is intentionally naive and, on many pairs, loses money after
costs — which is the point. Real edge comes from the work below (each is a
self-contained experiment: implement, backtest, and keep only what survives
**out-of-sample**):

1. **Walk-forward validation — built (`cryptostat/walkforward.py`).** Use it as
   the judge for *every* idea below: an experiment only counts if it improves the
   **out-of-sample** Sharpe, not the in-sample one. (On the raw baseline the gap
   is large and OOS is negative — that's your starting point to beat.)
2. **Dynamic hedge ratio (Kalman filter).** Replace the static β with a Kalman
   filter so the spread tracks a slowly-drifting relationship.
3. **Half-life-aware signals & time-stops.** Scale windows/holding to each pair's
   half-life; exit if it hasn't reverted within ~N half-lives.
4. **Portfolio of pairs** with a risk budget, instead of one pair at a time.
5. **Cointegration decay filter.** Re-test pairs on a rolling basis and stand
   down when the relationship breaks (rolling Engle-Granger p-value).
6. **Realistic costs & execution.** Model fees + spread + slippage per venue; the
   current cost model is a single `cost_bps` proxy.
7. **Cross-exchange arbitrage — analysis built (`crossexchange.py`).** The
   measurement layer (live scan + historical dislocation) is done; the open work
   is a live execution simulator that accounts for latency, transfer times, and
   pre-positioned balances, plus extending to funding-rate / perp-spot basis.

## Honest caveats

- Screening tests cointegration on log-prices while the backtester forms the raw
  spread — reconcile these (log-spread trading) as part of task 1.
- Multiple-testing bias: screening hundreds of pairs will surface some that are
  cointegrated by luck. Out-of-sample validation is not optional.
- This is a **research/backtest tool, not a live trader** — no broker or
  execution hookup.

## Tests

`tests/` validates the statistics against synthetic series with known truth
(ADF separates random walks from stationary series; Engle-Granger detects a
constructed cointegrated pair and rejects independent walks; half-life recovers a
known OU speed) and the backtester (profitable on a synthetic mean-reverting
spread, flat when never triggered, costs reduce returns) and the walk-forward
harness (no leakage, stands down on broken pairs, tradeable OOS on a real OU
spread), and cross-exchange arbitrage math (best route, fee-adjusted edge,
dislocation stats). All 21 pass.
