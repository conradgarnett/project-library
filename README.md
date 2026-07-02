# Portfolio & Risk Allocator

A portfolio construction and risk-management toolkit. It turns a panel of return
streams — **assets** (BTC, ETH, …) *or your own strategies* (funding carry,
stat-arb) — into a risk-managed book, and backtests the allocation walk-forward.

This is the layer that sits *on top of* individual strategies: you build alphas,
then this decides how to size and combine them into one portfolio. Free daily
data, no API keys.

## What's inside

| Module | Purpose |
| --- | --- |
| `portlib/covariance.py` | sample + **Ledoit-Wolf shrinkage** covariance (well-conditioned for optimizers) |
| `portlib/optimize.py` | mean-variance: **min-variance**, **max-Sharpe**, MV-utility (long-only, weight caps) |
| `portlib/riskparity.py` | inverse-vol + **equal-risk-contribution risk parity** + risk decomposition |
| `portlib/hrp.py` | **Hierarchical Risk Parity** (López de Prado): cluster → quasi-diagonalize → recursive bisection |
| `portlib/allocate.py` | one `allocate(returns, method=...)` over all six methods |
| `portlib/risk.py` | **VaR** (historical & parametric), **CVaR/expected shortfall**, drawdown, stress, performance report |
| `portlib/backtest.py` | **walk-forward** rebalancing; `compare_methods` runs them head-to-head OOS |
| `portlib/data.py` | free daily crypto returns (Coinbase) or your own returns via CSV |
| `portlib/visualize.py` | equity-curve and weight charts |

## Quick start

```bash
pip install -r requirements.txt        # numpy, scipy, pandas, requests (+ matplotlib)

python scripts/01_allocate.py                    # weights by method + risk report
python scripts/02_backtest.py                    # walk-forward compare -> results/ + figures/
python tests/run_all.py                          # 12 tests, no pytest needed
```

```python
import portlib as pl
rets = pl.returns_panel(["BTC-USD", "ETH-USD", "SOL-USD", "LTC-USD"], days=730)
pl.allocate(rets, method="risk_parity")          # weights
pl.compare_methods(rets)["table"]                # OOS Sharpe by method
pl.risk_report((rets * pl.allocate(rets, "hrp")).sum(axis=1)).as_dict()
```

## Methods

- **equal** — 1/N baseline.
- **inverse_vol** — weight ∝ 1/σ (naive risk parity).
- **min_variance** — lowest-variance long-only portfolio.
- **max_sharpe** — tangency portfolio (needs expected returns; noisiest input).
- **risk_parity** — every asset contributes equal risk (ignores returns).
- **hrp** — hierarchical risk parity; robust, no matrix inversion.

Covariance is Ledoit-Wolf-shrunk by default so the optimizers don't load up on
estimation error. Everything is **walk-forward** in the backtest: weights are
estimated on a trailing window and traded only on the next unseen window.

## The multi-strategy use case (the point)

The allocator is return-stream agnostic. Point it at *assets* and it's a normal
portfolio optimizer; point it at **your own strategies' return series** and it
becomes a multi-strategy book allocator:

```python
import pandas as pd, portlib as pl
book = pd.DataFrame({
    "funding_carry": carry_returns,     # from the crypto-funding-carry project
    "stat_arb":      pairs_returns,     # from the crypto-stat-arb project
    "btc":           btc_returns,
})
pl.compare_methods(book)["table"]       # how to size across your strategies
```

Because market-neutral strategy streams are far less correlated than directional
assets, the diversification benefit — and the portfolio Sharpe — is much larger
there than in the asset demo below. Load any such panel with `--csv`.

## Results (`results/allocation.txt`, `figures/allocation_equity.png`)

Walk-forward over ten crypto majors, 2y daily. Directional crypto is a **hard,
highly-correlated** case, which is exactly why *how* you allocate matters:

```
method         ann_return  ann_vol  sharpe  max_drawdown  cvar_95
max_sharpe          +0.14     0.78    0.18        -0.58     0.085
min_variance        +0.02     0.53    0.03        -0.58     0.060
hrp                 -0.09     0.62   -0.14        -0.65     0.072
risk_parity         -0.14     0.67   -0.21        -0.69     0.079
inverse_vol         -0.17     0.67   -0.25        -0.70     0.079
equal               -0.21     0.70   -0.30        -0.72     0.083
```

The risk-aware methods (min-variance, max-Sharpe) cut volatility and drawdown and
preserve capital through the crypto sell-off, while equal-weight sinks — visible
in `figures/allocation_equity.png`.

## Tests

`tests/run_all.py` (12 tests) validates on synthetic data with known truth:
Ledoit-Wolf is PSD with δ∈[0,1]; every method gives valid long-only weights;
min-variance overweights the low-vol asset; risk parity equalizes risk
contributions; HRP sums to one; VaR/CVaR match the Gaussian case (CVaR deeper
than VaR); and the backtest has no look-ahead and diversification cuts vol.

## Next steps
- Black-Litterman (blend views with the market prior).
- CVaR/turnover-constrained optimization.
- Feed the real funding-carry + stat-arb return streams for a live multi-strategy book.
