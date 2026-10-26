# Crypto Funding-Rate Carry

A market-neutral crypto strategy that harvests **perpetual-swap funding**. It runs
entirely on **free, key-less exchange APIs** (OKX for funding, Coinbase/Kraken for
spot) — no paid data feeds.

This is a *sibling* project to the crypto arbitrage toolkit (statistical /
cross-venue arbitrage) and the options pricing model — kept on its own branch
because it's a distinct **strategy**, not arbitrage and not a pricing model.

## Honest validation on 3 years of real data (2026-07)

The strategy was put through the same gauntlet that falsified the sibling
stat-arb project (`crypto-stat-arb/quantconnect/backtest_local.py`): real data,
real costs, walk-forward-only decisions. Source: Gate.io (OKX's public funding
history caps at ~3 months — see `scripts/fetch_funding_data.py`). 12 coins,
2023-07 -> 2026-07, basis-aware P&L, 15 bps entry / 30 bps switch costs.
Run it: `python scripts/validate_carry.py`.

| test | ann. return* | Sharpe | maxDD |
| --- | --- | --- | --- |
| hold-all equal-weight (**zero selection bias**) | +5.5% | 6.2 | −1.4% |
| walk-forward top-4 by trailing funding | +5.5% | 4.2 | −0.7% |
| causal ≥5% funding hurdle (on 43% of the time) | +5.0% | 7.1 | −0.5% |

*Per unit of one leg's notional; a fully-funded spot+margin setup earns
roughly **half** this on total capital.

**The premium is real** — 11 of 12 coins positive over 3 years with no
selection at all, positive in 2023, 2024 and 2025. Three honest findings:

1. **It is compressing**: 2024 +11.7% -> 2025 +2.5% -> 2026 YTD −0.7%
   (hold-all). Funding carry got crowded; on total capital, recent levels
   trail T-bills. This is a *when* strategy, not an *always* strategy.
2. **Coin selection adds nothing**: chasing trailing funding (Sharpe 4.2)
   loses to simply holding all 12 (6.2) — the premium is market-wide, not
   coin-specific, so selection only adds turnover and concentration.
3. **The causal hurdle rule is the deployment answer**: next-interval funding
   is known in advance, so "harvest only when trailing funding annualizes
   above a hurdle" is causal, not curve-fit. It kept ~all the return at a
   third of the drawdown and correctly stands aside in 2026. (Hurdles 3% and
   5% behave near-identically — the rule is not fragile to the threshold.)

**Sharpe 6 needs a health warning.** Carry strategies have smooth P&L until
they don't: perp-leg liquidation in a crash, exchange/counterparty failure,
and cross-venue basis blowouts are all OUTSIDE this sample. Size as if the
true risk were multiples of the measured vol.

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
  funding/   data.py  carry.py  portfolio.py   # funding data + carry + portfolio
scripts/     funding_carry.py  funding_portfolio.py
tests/       run_all.py + test_funding.py + test_portfolio.py
results/     funding/carry.txt  funding/portfolio.txt
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

Two backtest models (annualized over 1095 eight-hour intervals per year):

- **Idealized** (`carry_backtest`): assumes a perfect hedge, so the per-interval
  return is just the funding collected. Optimistic.
- **Basis-aware** (`basis_carry_backtest`): the honest version. Uses the *actual*
  OKX perp and spot price paths, so the return includes the real price-leg P&L:
  `return = funding − Δ(basis)`, where `basis = perp/spot − 1`. `compare_carry`
  runs both side by side.

Position modes (both models):
- **Naive long-basis** (`flip=False`): always long-spot / short-perp — collect
  funding when positive, *pay* when it flips negative.
- **Flip** (`flip=True`): switch sides when funding turns negative to always
  collect its magnitude, paying a rebalance fee on each switch.

## Honest findings & caveats

From `results/funding/carry.txt` (current, calm market): funding is modest —
BTC ≈ +1.6%, ETH ≈ +2.1%, DOGE ≈ +4.2% annualized (memecoins draw crowded
longs) — so carry yields are low single digits. They run far richer in bull
markets.

**The basis-aware model is the headline result.** The idealized (funding-only)
Sharpe looks huge, but pricing the *real* perp/spot legs collapses it:

| coin | idealized Sharpe | basis-aware Sharpe | basis vol |
| --- | --- | --- | --- |
| BTC | 7.7 | 3.2 | 0.9 bps |
| ETH | 9.2 | 3.9 | 1.0 bps |
| DOGE | 20.0 | 4.8 | 1.7 bps |
| XRP | 5.7 | 0.8 | 4.0 bps |

Even though the perp/spot basis is *tiny* (sub-1 to a few bps, same venue), its
interval-to-interval **changes** are large relative to the minuscule 8-hour
funding drip — so they dominate the return variance and cut the Sharpe roughly
2–7×. The idealized number was a mirage; the basis-aware one is honest.

Still **not** modeled (would lower it further):
- **perp-leg liquidation** on sharp moves (margin management),
- **exchange / counterparty failure** (e.g. FTX),
- **cross-venue hedging** would add a much larger, noisier basis than same-venue.

This is a **research/backtest tool, not a live trader** — no broker or margin engine.

## Portfolio of carries (`funding/portfolio.py`)

A single-coin carry is thin and noisy. Running it across several coins and
combining them with a risk budget diversifies away idiosyncratic basis/funding
noise, which **raises the risk-adjusted return honestly** — it's built on the
basis-aware returns and weights use trailing data only (no look-ahead).

```python
from cryptostat.funding.portfolio import carry_returns_panel, carry_portfolio
panel = carry_returns_panel(["BTC", "ETH", "SOL", "DOGE", "XRP", "LTC"])
carry_portfolio(panel, scheme="inverse_vol").summary()
```

Result (`results/funding/portfolio.txt`): combining six coins lifts the
basis-aware Sharpe well above the average standalone coin — **avg standalone ≈ 2.6
→ portfolio ≈ 4.0 (equal weight) / ≈ 5.5 (inverse-vol)**, a diversification ratio
of ~2. Inverse-vol (risk-balanced) beats equal weight because it down-weights the
noisiest coins. This is a genuine diversification gain, not a modeling shortcut.

## Charts (`figures/`)

`python scripts/funding_charts.py` writes:
- `portfolio_equity.png` — portfolio equity (equal vs inverse-vol) over the jagged
  individual-coin carries, showing the diversification benefit visually.
- `idealized_vs_basis.png` — BTC idealized vs basis-aware equity; the basis-aware
  line is visibly noisier, which is why its Sharpe is lower even at a similar level.
- `funding_over_time.png` — annualized funding per coin across time (regimes).

### Next steps
- **Done:** basis-aware backtest (`basis_carry_backtest`), portfolio of carries
  (`carry_portfolio`), and charts (`funding/visualize.py`).
- Model perp-leg **margin & liquidation** at a chosen leverage.

## Tests

`tests/run_all.py` validates the carry math on synthetic funding series:
positive funding earns, negative loses without flip (and wins with flip), and
fees reduce returns. A guarded live check pulls real OKX funding when reachable.
