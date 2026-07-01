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
| `optlib/monte_carlo.py` | Risk-neutral GBM pricer with antithetic variates + control variate, standard errors / 95% CI, finite-difference Greeks (common random numbers), path simulation |
| `optlib/compare.py` | BS ↔ MC comparison tables for price, Greeks, and convergence |
| `optlib/visualize.py` | Greek curves, vol smile, vol surface, MC convergence, payoff/P&L, sample paths |
| `cli.py` | Command-line calculator |
| `demo.py` | End-to-end report + figure generation |
| `tests/test_pricing.py` | Correctness tests (reference prices, parity, FD Greek checks, IV round-trip, MC-in-CI) |

---

## Quick start

```bash
cd options-pricing
pip install -r requirements.txt      # numpy, scipy, matplotlib, pandas

python demo.py                       # prints everything + writes figures/
python -m pytest -q                  # or: python tests/test_pricing.py
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

## Do the two models agree?

From `demo.py` (contract `S=100, K=105, T=0.75, r=4.5%, σ=28%, q=1%`, 1M paths):

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

## Figures (generated into `figures/`)

- `greeks_vs_spot.png` — price + all five Greeks vs spot
- `vol_smile.png` — implied-vol smile / skew across strikes
- `vol_surface.png` — 3-D implied-vol surface over (strike, maturity)
- `mc_convergence.png` — MC price ± CI converging to Black-Scholes
- `payoff_diagram.png` — payoff, P&L, and current value with breakeven
- `sample_paths.png` — simulated GBM paths + terminal distribution

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

All 9 tests pass.
