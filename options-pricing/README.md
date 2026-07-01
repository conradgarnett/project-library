# Options Pricing & Greeks Calculator

A self-contained derivatives pricing toolkit: **closed-form Black-Scholes-Merton**
pricing with **all five Greeks**, a **Monte-Carlo** pricer that cross-checks the
analytic results, an **implied-volatility solver**, and a set of
**volatility & risk visualizations**.

Everything is pure `numpy` / `scipy` / `matplotlib` / `pandas` — no external
services, fully reproducible.

---

## What's inside

| Module | Purpose |
| --- | --- |
| `optlib/black_scholes.py` | BSM price, Delta/Gamma/Vega/Theta/Rho, implied vol (Brent), put-call parity check |
| `optlib/greeks_advanced.py` | Higher-order Greeks: vanna, charm, vomma, veta, speed, zomma, color, ultima, dual-delta, dual-gamma (all FD-validated) |
| `optlib/monte_carlo.py` | Risk-neutral GBM pricer with antithetic variates + control variate, standard errors / 95% CI, finite-difference Greeks (common random numbers), path simulation |
| `optlib/binomial.py` | Cox-Ross-Rubinstein lattice pricer — European **and American** options (early exercise), plus tree Greeks |
| `optlib/finite_difference.py` | Crank-Nicolson PDE solver — European & American, second-order accurate, grid delta/gamma |
| `optlib/exotic.py` | Digital, geometric/arithmetic Asian, barrier (Reiner-Rubinstein + MC), lookback |
| `optlib/models.py` | Merton jump-diffusion (closed form + MC) and Heston stochastic vol (MC) — both generate the smile |
| `optlib/implied.py` | Implied vs realized: realized-vol estimators, implied ITM probability, Breeden-Litzenberger density, variance risk premium, delta-hedge P&L |
| `optlib/strategy.py` | Multi-leg strategy analyzer: net premium, aggregate Greeks, payoff/P&L, breakevens, max profit/loss + ready-made spreads/straddle/strangle/condor/covered-call/protective-put |
| `optlib/compare.py` | Four-way (BS / MC / binomial / PDE) comparison tables for price, Greeks, and convergence |
| `optlib/visualize.py` | Greek curves, vol smile & surface, MC/model convergence, payoff/P&L, sample paths, strategy P&L, implied density, hedged-P&L-vs-realized, model smiles |
| `cli.py` | Command-line calculator |
| `demo.py` | End-to-end report + figure generation |
| `tests/test_pricing.py` | Correctness tests (reference prices, parity, FD Greek checks, IV round-trip, MC-in-CI) |

---

## Quick start

```bash
cd options-pricing
pip install -r requirements.txt      # numpy, scipy, matplotlib, pandas

python demo.py                       # prints everything + writes figures/
python tests/run_all.py              # 35 tests, no pytest needed (or: python -m pytest -q)
```

### Command-line calculator

```bash
# Price a call, show all Greeks, and cross-check with Monte-Carlo
python cli.py --S 100 --K 105 --T 0.5 --r 0.05 --sigma 0.25 --kind call

# Invert an observed price into an implied volatility
python cli.py --S 100 --K 100 --T 1 --r 0.05 --kind call --implied-from 10.4506

# Analytic only (skip Monte-Carlo)
python cli.py --S 100 --K 100 --T 1 --r 0.05 --sigma 0.2 --no-mc
```

### Library

```python
from optlib import BlackScholes, mc_price
from optlib.compare import compare_prices

bs = BlackScholes(S=100, K=105, T=0.75, r=0.045, sigma=0.28, q=0.01, kind="call")
print(bs.price())          # 8.5976
g = bs.greeks()
print(g.delta, g.gamma, g.vega, g.theta, g.rho)

print(mc_price(100, 105, 0.75, 0.045, 0.28, q=0.01, kind="call"))
print(compare_prices(100, 105, 0.75, 0.045, 0.28, q=0.01))
```

```python
# Binomial tree — American put with early exercise
from optlib import binomial_price
print(binomial_price(100, 110, 1.0, 0.06, 0.3, kind="put", exercise="american"))

# Multi-leg strategy — aggregate Greeks, breakevens, max profit/loss
from optlib.strategy import iron_condor
prof = iron_condor(85, 95, 110, 120).profile(S=100, T=0.5, r=0.04, sigma=0.25)
print(prof["net_premium"], prof["breakevens"], prof["greeks"]["delta"])
```

---

## The model

### Black-Scholes-Merton (with dividend yield `q`)

```
d1 = [ln(S/K) + (r - q + σ²/2)·T] / (σ·√T)
d2 = d1 - σ·√T

Call = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)
Put  = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)
```

**The five Greeks** (call/put forms handled explicitly; Gamma & Vega are
identical for both):

| Greek | Meaning | Unit reported |
| --- | --- | --- |
| Delta | ∂V/∂S | per $1 of spot |
| Gamma | ∂²V/∂S² | per $1 of spot |
| Vega | ∂V/∂σ | per 1 vol point (CLI) / per 1.00 σ (library) |
| Theta | ∂V/∂t | per calendar day (CLI) / per year (library) |
| Rho | ∂V/∂r | per 1% rate (CLI) / per 1.00 rate (library) |

### Monte-Carlo

Under the risk-neutral measure `S_T = S₀·exp[(r - q - σ²/2)T + σ√T·Z]`, price =
`e^(-rT)·E[payoff(S_T)]`. Variance reduction via **antithetic variates** and a
**control variate** (the discounted underlying, whose mean is known exactly).
The reported **standard error** and **95% confidence interval** quantify the
sampling error, and Greeks use **common random numbers** so bump-and-revalue
differencing is stable.

---

### Binomial tree (CRR) — European & American

A lattice with up/down factors `u = e^{σ√dt}`, `d = 1/u`, risk-neutral
probability `p = (e^{(r-q)dt} - d)/(u - d)`, solved by backward induction. For
American options the node value is `max(continuation, intrinsic)` at every step,
capturing the early-exercise premium.

---

## Do the models agree?

From `demo.py` (contract `S=100, K=105, T=0.75, r=4.5%, σ=28%, q=1%`, 1M paths,
1000 tree steps) — three independent methods land on the same price:

```
model                        price    note
Black-Scholes (closed form)  8.5976   analytic truth
Monte-Carlo (simulation)     8.6026   ±0.0073 SE (95% CI 8.5882-8.6170)
Binomial tree, European      8.5979   err vs BS = 0.0003
Binomial tree, American      8.5979   early-exercise premium = 0.0000
```

For the **put**, the American tree correctly shows a positive early-exercise
premium (10.86 European → 11.24 American). Call/put price agreement vs MC:

```
kind   black_scholes  monte_carlo  mc_std_error  abs_error  bs_within_ci
call          8.5976       8.6026        0.0073     0.0050          True
put          10.8602      10.8652        0.0073     0.0050          True
```

Greeks (call) agree to well under 0.2%:

```
greek   black_scholes  monte_carlo  rel_error_%
delta          0.5075       0.5074       0.0070
gamma          0.0163       0.0163       0.1837
vega          34.2775      34.2950       0.0509
theta         -7.7877      -7.7970       0.1188
rho           31.6116      31.6115       0.0005
```

Monte-Carlo error shrinks like `O(1/√N)`, and the analytic price stays inside
the MC 95% CI as paths grow — see `figures/mc_convergence.png`.

---

## Implied vs realized — "are there implied Greeks?"

Implied volatility is the *only* BS input inverted from the market price; the
Greeks are then computed **at** that implied vol, so desk Greeks already are
"implied Greeks." What you can additionally back out of prices, and check
against what actually happens:

- **Implied ITM probability** `N(d2) = -e^{rT}·dual_delta` — the risk-neutral
  `Q(S_T > K)`. Compare to the real-world probability (with physical drift μ):
  the gap is the risk premium / change of measure.
- **Implied risk-neutral density** `f(K) = e^{rT}·∂²C/∂K²`
  (Breeden-Litzenberger) — the whole distribution the market prices in.
- **Variance risk premium** — implied vol vs realized vol over the option's
  life (implied is systematically richer).
- **Gamma-theta identity** — a delta-hedged long option earns
  `≈ ½(σ_realized² − σ_implied²)·∫ΓS²dt`. `delta_hedge_pnl` simulates this and
  it matches the closed-form prediction to Monte-Carlo error; the P&L crosses
  zero exactly at `realized == implied` (see `figures/iv_vs_realized_hedge.png`).

```python
from optlib.implied import implied_prob_itm, variance_risk_premium, delta_hedge_pnl
implied_prob_itm(100, 105, 0.5, 0.04, 0.25, kind="call")            # risk-neutral N(d2)
variance_risk_premium(implied_vol=0.20, realized_vol=0.16)          # options were rich
delta_hedge_pnl(100, 100, 0.5, 0.03, 0.20, 0.30, kind="call")       # realized>implied => +P&L
```

## Exotics & alternative models

```python
from optlib.exotic import barrier_price, geometric_asian_price
from optlib.models import merton_jump_price, heston_price_mc

barrier_price(100, 100, 90, 1, 0.05, 0.2, kind="call", barrier_type="down-out")
geometric_asian_price(100, 100, 1, 0.05, 0.2, kind="call")          # closed form
merton_jump_price(100, 100, 1, 0.05, 0.2, lam=1, muJ=-0.1, sigJ=0.15)  # + skew
heston_price_mc(100, 100, 1, 0.05, v0=0.04, theta=0.04, xi=0.5, rho=-0.7)
```

Barrier in-out parity (`knock_in + knock_out == vanilla`) holds to machine
precision, and every closed form is cross-checked against Monte-Carlo.

## Figures (generated into `figures/`)

- `greeks_vs_spot.png` — price + all five Greeks vs spot
- `vol_smile.png` — implied-vol smile / skew across strikes
- `vol_surface.png` — 3-D implied-vol surface over (strike, maturity)
- `mc_convergence.png` — MC price ± CI converging to Black-Scholes
- `model_convergence.png` — MC *and* binomial tree both converging to Black-Scholes
- `payoff_diagram.png` — payoff, P&L, and current value with breakeven
- `sample_paths.png` — simulated GBM paths + terminal distribution
- `strategy_iron_condor.png` — multi-leg strategy P&L with breakevens & Greeks
- `risk_neutral_density.png` — implied density (Breeden-Litzenberger) vs exact lognormal
- `iv_vs_realized_hedge.png` — delta-hedged P&L vs realized vol (gamma-theta fact-check)
- `model_smiles.png` — implied-vol smiles generated by Merton & Heston

---

## Validation

`tests/test_pricing.py` checks:
- reference prices (Hull ATM example: call 10.4506, put 5.5735)
- put-call parity to machine precision
- every analytic Greek against an independent central finite difference
- Gamma/Vega equality for calls vs puts, Delta bounds
- implied-vol round-trip (price → σ → price)
- expiry intrinsic values
- Monte-Carlo price within a few standard errors of Black-Scholes
- binomial European price converges to Black-Scholes
- American ≥ European, with a strictly positive early-exercise premium for the
  American put on a non-dividend stock
- strategy Greeks, breakevens, and capped payoffs (bull spread, straddle,
  covered call)
- every higher-order Greek vs an independent finite difference
- Crank-Nicolson PDE converges to BS; American matches the tree
- exotic closed forms vs Monte-Carlo; barrier in-out parity
- Merton/Heston reduce to BS in the right limits and generate a skew
- implied-vs-realized: density recovery, `N(d2)` = `-e^{rT}·dual_delta`, and the
  delta-hedge P&L tracking the gamma-theta prediction

All 35 tests pass (`python tests/run_all.py`).
