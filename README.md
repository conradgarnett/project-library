# Project Library

A collection of **quantitative-finance projects** built end-to-end on **free,
key-less market data** — with a hard emphasis on *honest* backtesting. Every
strategy is validated walk-forward (no look-ahead), and the results say plainly
what works and what doesn't.

The projects form one pipeline — **pricing → strategies → allocation → book**:

| Folder | What it is |
| --- | --- |
| [`options-pricing/`](options-pricing) | Full derivatives pricing library: Black-Scholes, Monte-Carlo, binomial & Crank-Nicolson PDE, all Greeks (incl. higher-order), exotics, jump-diffusion/Heston, implied-vol surface calibration, and a no-arbitrage scanner. 48 tests. |
| [`crypto-stat-arb/`](crypto-stat-arb) | Statistical arbitrage: cointegration pair screening, z-score **and ML / neural-net (LSTM)** signals, cross-venue / triangular arbitrage across five free exchanges, and a QuantConnect/LEAN port — with **walk-forward** validation. |
| [`crypto-funding-carry/`](crypto-funding-carry) | Market-neutral perpetual-futures **funding carry**: long-spot / short-perp, with a **basis-aware** backtest, a portfolio-of-carries, and a 3-year real-data validation. |
| [`portfolio-allocator/`](portfolio-allocator) | Portfolio construction (mean-variance, risk parity, HRP) + risk engine (VaR/CVaR/stress) + the Markowitz **efficient frontier**, all walk-forward. |
| [`multi-strategy-book/`](multi-strategy-book) | **Capstone** — wires the real strategy returns into the allocator to form one risk-managed book. |
| [`GP Trading Engine/`](GP%20Trading%20Engine) | A genetic-programming engine that *evolves* trading strategies as expression trees, with walk-forward and Monte-Carlo robustness checks, overfitting-resistant search (randomized block CV + locked holdout), vol targeting, ensembling, multi-asset search, and a supervised-ML strategy finder. |

## The thesis

Free/key-less data · honest **walk-forward** backtesting · market-neutral
strategies · and being explicit about what *doesn't* work.

## What the research actually found (the honest part)

- **Arbitrage is efficient.** Cross-exchange and triangular gross edges exist but
  don't survive taker fees — **0 executable loops after costs**.
- **Model the real hedge.** Funding carry is harvestable, but pricing the actual
  perp/spot **basis** cuts the idealized Sharpe **~2–7×**. The idealized number
  was a mirage.
- **The carry premium is real but compressing.** On 3 years of real data, 11 of
  12 coins were positive with zero selection — but returns fell from +11.7%
  (2024) to roughly flat in 2026. It's a *when* strategy, not an *always* one.
- **In-sample lies.** Stat-arb looks great in-sample and mostly doesn't survive
  **out-of-sample** — walk-forward validation is the only honest judge.
- **There's a ceiling.** Robust search, ensembling, multi-asset search and a
  supervised-ML finder all land at an out-of-sample Sharpe of roughly **1.0** on
  free daily data.
- **Diversification is the free lunch.** Genuinely uncorrelated strategies
  (funding carry vs stat-arb ≈ 0.07 correlation) combine into a lower-risk book
  than any of them alone.

## Capstone — Multi-Strategy Book

The **real** return streams of the two crypto strategies (funding carry +
stat-arb) fed into the allocator to form one book. Run with
`python multi-strategy-book/build_book.py`.

- **The strategies are genuinely uncorrelated** — funding-carry vs stat-arb ≈ 0.07,
  and both ≈ 0 / negative to BTC (market-neutral).
- **Risk-based allocation sizes them inversely to risk** — risk parity puts ~97% on
  the low-vol funding carry and ~3% on the volatile stat-arb, more than halving the
  book's volatility vs the risky sleeve.
- **Honest scope:** the common window is ~65 days and it was a *losing* window for
  stat-arb and BTC, so the book's **return is negative**. This is a proof of the
  **architecture and risk management**, not a track record.

## Run any of it

Each folder is a self-contained project with its own README, `requirements.txt`,
and a no-pytest test runner:

```bash
cd portfolio-allocator
pip install -r requirements.txt
python scripts/03_frontier.py       # -> figures/efficient_frontier.png
python tests/run_all.py             # 17 tests
```

## Development branches

Some projects were first developed on their own branches; `main` holds the
latest version of each as a folder:
[`gp-trading-engine`](https://github.com/conradgarnett/project-library/tree/gp-trading-engine) ·
[`options-pricing-greeks`](https://github.com/conradgarnett/project-library/tree/options-pricing-greeks) ·
[`crypto-stat-arb`](https://github.com/conradgarnett/project-library/tree/crypto-stat-arb) ·
[`crypto-funding-carry`](https://github.com/conradgarnett/project-library/tree/crypto-funding-carry) ·
[`portfolio-allocator`](https://github.com/conradgarnett/project-library/tree/portfolio-allocator)

## License

MIT — see [LICENSE](LICENSE).
