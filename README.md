# GP Trading Engine

A **genetic-programming research engine** that automatically discovers trading
strategies for SPY. Instead of hand-coding a strategy, it represents each one as
a math formula, then breeds and mutates a population of them over many
generations, keeping the ones that backtest best.

> This is a **research/backtest engine**, not a live trader — it evolves and
> evaluates on historical SPY data only (no broker or execution hookup).

## How a strategy is represented

Each strategy is an **expression tree**:

- **Leaves** = market features
- **Operators** = `add`, `sub`, `mul`, `div` (binary) and `tanh` (unary)

So an evolved strategy is a formula like `tanh(sub(mom10, mul(vol, ma_fast)))`
that outputs a number each day, which becomes the trading position.

## Pipeline (`gp_trading_engine.py`)

| Component | Role |
|---|---|
| `DataLayer` | Pulls real SPY OHLCV data (yfinance, with an HTTP fallback) |
| `FeatureEngine` | Builds 6 z-scored features: `ret1`, `ret5`, `mom10`, `vol`, `ma_fast`, `ma_slow` |
| `GPTree` / `TreeNode` | Genetic-programming expression trees |
| `TreeEvaluator` | Runs a strategy tree over features → raw signal |
| `SignalExecutor` | Squashes signal to a position (`tanh`); applies risk controls (long/short modes, max exposure, vol targeting, drawdown throttle) |
| `BacktestEngine` | Simulates trading with correct alignment (no look-ahead) and per-trade costs; scores Sharpe, Calmar, CAGR, drawdown, turnover, win rate, PnL |
| `GeneticEvolutionEngine` | The GA: population init (can seed from the vault = transfer learning), selection, crossover, mutation, elitism |
| `WalkForwardEngine` | Trains on one window, validates on the next unseen window (out-of-sample) |
| `MonteCarloSimulator` | Stress-tests a strategy's return stream for robustness |
| `StrategyVault` | Persists champion strategies to `strategy_vault.json` |
| `GPTradingEngine` | Top-level orchestrator |

**Fitness** is a weighted blend favoring risk-adjusted, low-drawdown returns:
`Sharpe + 0.75·Calmar + CAGR + 2.0·return + drawdown_term − cost_penalty`.

## Runner scripts

- **`walk_forward_search.py`** — walk-forward validation; hunts for strong
  *out-of-sample* Sharpe and Calmar (targets: Sharpe ≥ 1.0, Calmar ≥ 3.0) and
  saves the best validated champion to the vault.
- **`search_until_sharpe.py`** — repeatedly evolves new populations (up to 100
  runs, pop 80, 30 generations) until a target Sharpe of 1.0 is hit, seeding
  each run from the vault and saving new champions back.

## Files

- `gp_trading_engine.py` — the engine (data, features, GP, backtest, evolution)
- `walk_forward_search.py` — walk-forward / out-of-sample search
- `search_until_sharpe.py` — evolve-until-target-Sharpe runner
- `strategy_vault.json` — persisted champion strategies

## Requirements

Python 3 with `numpy`, `pandas`, `yfinance`, `matplotlib`.

## Caveats

With only 6 features, simple operators, and a search that explicitly maximizes
Sharpe/Calmar, results are **prone to overfitting**. The walk-forward and Monte
Carlo components exist to push back on that — treat any in-sample Sharpe
skeptically until it survives genuinely fresh data.
