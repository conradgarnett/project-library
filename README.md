# Project Library

A portfolio of quantitative-finance projects, all built on **free, key-less
market data**. Each project lives on its own branch and is mirrored as a folder
here.

## Overview

The projects form one pipeline — **pricing → strategies → allocation → book**:

1. **Delta Terminal · GP Trading Engine** — data terminal and a genetic-programming
   strategy evolver (research tooling).
2. **Options Pricing & Greeks** — a full derivatives pricing library.
3. **Crypto Arbitrage Toolkit · Crypto Funding-Rate Carry** — two *market-neutral*
   crypto strategies.
4. **Portfolio & Risk Allocator** — combines return streams into a risk-managed book.
5. **Multi-Strategy Book** (capstone) — wires the *real* strategy returns into the
   allocator: build strategies, then allocate across them.

**Principles throughout:** free/key-less data; honest **walk-forward** backtesting
(no look-ahead); market-neutral strategies; and being explicit about what *doesn't*
work.

### What I learned (the honest findings)

- **Arbitrage is efficient.** Cross-exchange and triangular gross edges exist but
  don't survive taker fees — 0 executable loops after costs.
- **Model the real hedge.** Funding carry is harvestable, but pricing the actual
  perp/spot **basis** cuts the idealized Sharpe ~2–7×. The idealized number was a
  mirage.
- **In-sample lies.** Stat-arb looks great in-sample and mostly doesn't survive
  **out-of-sample** — walk-forward validation is the only honest judge.
- **Diversification is the free lunch.** Genuinely uncorrelated strategies combine
  into a lower-risk book than any of them alone.

## Projects

- **Delta Terminal** — open-source markets/data terminal. Completely made from free APIs.
  → [`delta-terminal`](https://github.com/conradgarnett/project-library/tree/delta-terminal)
- **GP Trading Engine** — genetic-programming intraday strategy evolver (Python).
  → [`gp-trading-engine`](https://github.com/conradgarnett/project-library/tree/gp-trading-engine)
- **Options Pricing & Greeks** — derivatives pricing toolkit: Black-Scholes, Monte-Carlo, binomial & Crank-Nicolson PDE pricers, all Greeks, exotics, alternative models with smile calibration, and risk/scenario tools (Python).
  → [`options-pricing-greeks`](https://github.com/conradgarnett/project-library/tree/options-pricing-greeks)
- **Crypto Arbitrage Toolkit** — market-neutral crypto arbitrage research: cointegration/statistical pairs trading with walk-forward validation, plus cross-venue & triangular arbitrage across five free exchanges (Python).
  → [`crypto-stat-arb`](https://github.com/conradgarnett/project-library/tree/crypto-stat-arb)
- **Crypto Funding-Rate Carry** — market-neutral perpetual-futures strategy: harvest exchange funding with a delta-neutral (long spot / short perp) position; backtested on free OKX funding data (Python).
  → [`crypto-funding-carry`](https://github.com/conradgarnett/project-library/tree/crypto-funding-carry)
- **Portfolio & Risk Allocator** — portfolio construction (mean-variance, risk parity, HRP) + risk engine (VaR/CVaR/stress) with walk-forward backtesting; allocates across assets or across your own strategies (Python).
  → [`portfolio-allocator`](https://github.com/conradgarnett/project-library/tree/portfolio-allocator)

## Capstone — Multi-Strategy Book (`multi-strategy-book/`)

The payoff that ties it together: the **real** return streams of the two crypto
strategies (funding carry + stat-arb) fed into the allocator to form one book.
Run with `python multi-strategy-book/build_book.py`.

- **The strategies are genuinely uncorrelated** — funding-carry vs stat-arb ≈ 0.07,
  and both ≈ 0 / negative to BTC (market-neutral). See
  `multi-strategy-book/figures/book_correlation.png` — the diversification
  precondition is real.
- **Risk-based allocation sizes them inversely to risk** — risk parity puts ~97% on
  the low-vol funding carry and ~3% on the volatile stat-arb, more than halving the
  book's volatility vs the risky sleeve. The allocator does its job on real strategy
  data.
- **Honest scope:** the common window is ~65 days (free OKX funding history is only
  ~3 months deep) and it was a *losing* window for stat-arb and BTC, so the book's
  **return is negative**. This is a proof of the **architecture and risk
  management**, not a track record — with longer history and more strategies it is
  exactly how a systematic multi-strategy book is assembled.
