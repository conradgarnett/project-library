# Crypto Funding-Rate Carry

A market-neutral crypto strategy that harvests **perpetual-swap funding**. It runs
entirely on **free, key-less exchange APIs** (OKX for funding, Coinbase/Kraken for
spot) — no paid data feeds.

This is a *sibling* project to the crypto arbitrage toolkit (statistical /
cross-venue arbitrage) and the options pricing model — kept on its own branch
because it's a distinct **strategy**, not arbitrage and not a pricing model.

## The idea

A **perpetual future** ("perp") never expires, so a **funding rate** paid every
8 hours tethers its price to spot: when the crowd is long (perp rich), longs pay
shorts; when short (perp cheap), shorts pay longs.

Hold a **delta-neutral** position — long spot + short perp — and your price
exposure cancels while you *collect the funding* each interval. Because funding
is a **risk premium** (leveraged longs choose to pay to hold exposure), not a
fleeting mispricing, the edge persists and isn't latency-bound — unlike
cross-exchange or triangular arbitrage.

```
funding.data.funding_history   →   funding.carry.carry_backtest   →   metrics
 OKX perp funding (free)            delta-neutral carry P&L            yield / Sharpe /
                                    (long-basis or flip)               drawdown
```

## Layout

```
cryptostat/
  common/    data.py  stats.py  metrics.py     # shared foundation
  funding/   data.py  carry.py                 # funding data + carry backtest
scripts/     funding_carry.py                  # multi-coin carry report
tests/       run_all.py + test_funding.py
results/     funding/carry.txt                 # committed example output
```

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests

python scripts/funding_carry.py        # carry yield per coin -> results/funding/
python tests/run_all.py                # tests, no pytest needed
```

```python
import cryptostat as cs
h = cs.funding_history("BTC")                       # OKX 8h funding history
print(cs.carry_backtest(h, flip=False).summary())  # delta-neutral carry stats
```

## Method

- **Naive long-basis** (`flip=False`): always long-spot / short-perp. Collect
  funding when it's positive (the usual state); *pay* it when it flips negative.
- **Flip** (`flip=True`): switch sides when funding turns negative to always
  collect its magnitude, paying a rebalance fee on each switch.
- Per-interval return ≈ funding collected (the delta-neutral hedge zeroes price
  P&L), annualized over 1095 eight-hour intervals per year.

## Honest findings & caveats

From `results/funding/carry.txt` (current, calm market): funding is modest —
BTC ≈ +1.7%, ETH ≈ +2.1%, DOGE ≈ +4.2% annualized (memecoins draw crowded
longs) — so carry yields are low single digits. They run far richer in bull
markets.

- The reported **Sharpes look huge (8–20) only because the model assumes a
  perfect hedge** — a near-zero-variance funding drip. That number **excludes the
  real risks**: exchange/counterparty failure (FTX), perp-leg liquidation on
  sharp moves, and spot-perp basis drift.
- The naive long-basis version beats `flip` when funding is mostly positive,
  because flipping on every sign change churns fees.
- **Research/backtest tool, not a live trader** — no broker or margin engine.

### Next steps
- Add basis drift + margin/liquidation modeling so the Sharpe reflects real risk.
- Combine the spot leg (from `common/data.py`) to track the actual basis.
- Portfolio of carries across coins with a risk budget.

## Tests

`tests/run_all.py` validates the carry math on synthetic funding series:
positive funding earns, negative loses without flip (and wins with flip), and
fees reduce returns. A guarded live check pulls real OKX funding when reachable.
