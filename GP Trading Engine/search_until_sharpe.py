"""
Repeatedly evolve GP strategies until a target Sharpe ratio is found.

This runner reuses real SPY data, seeds each run from strategy_vault.json,
randomizes every attempt, and saves new champions back to the vault.
"""

from __future__ import annotations

import random
import time

import numpy as np

from gp_trading_engine import (
    DataLayer,
    FeatureEngine,
    GeneticEvolutionEngine,
    GPTradingEngine,
    STRATEGY_VAULT_PATH,
    StrategyVault,
)


TARGET_SHARPE = 1.0
MAX_RUNS = 100
POPULATION_SIZE = 80
NUM_GENERATIONS = 30
INITIAL_CAPITAL = 10_000


def print_strategy_summary(label: str, strategy) -> None:
    print(
        f"{label}: fitness={strategy.fitness:.4f} | "
        f"sharpe={strategy.sharpe:.4f} | "
        f"calmar={strategy.calmar:.4f} | "
        f"pnl=${strategy.pnl:,.2f} | "
        f"return={strategy.total_return * 100:.2f}% | "
        f"dd={strategy.drawdown:.4f}"
    )


def main() -> None:
    symbol = "SPY"
    start_date = "2001-01-01"
    interval = "1d"
    annualization = GPTradingEngine.annualization_for_interval(interval)

    print("=" * 70)
    print(f"SEARCHING FOR SHARPE > {TARGET_SHARPE:.2f}")
    print("=" * 70)

    data = DataLayer.fetch_spy_data(symbol=symbol, start=start_date, interval=interval)
    features = FeatureEngine.build_features(data)
    market_returns = data.loc[features.index, "returns"].values
    feature_names = features.columns.tolist()

    best_overall = None
    start_time = time.time()

    for run_num in range(1, MAX_RUNS + 1):
        random.seed()
        np.random.seed(None)

        seed_trees = StrategyVault.load_champions(
            feature_names,
            path=STRATEGY_VAULT_PATH,
            max_champions=20,
        )

        engine = GeneticEvolutionEngine(
            feature_names=feature_names,
            population_size=POPULATION_SIZE,
            elite_size=8,
            mutation_rate=0.35,
            annualization=annualization,
            initial_capital=INITIAL_CAPITAL,
        )
        engine.initialize_population(seed_trees=seed_trees)

        print(f"\nRun {run_num}/{MAX_RUNS} | seeded champions: {len(seed_trees)}")

        for gen in range(1, NUM_GENERATIONS + 1):
            engine.evaluate_population(features, market_returns)
            best = engine.get_best_strategy()

            if best_overall is None or best.sharpe > best_overall.sharpe:
                best_overall = best
                print_strategy_summary(f"  New best Sharpe at gen {gen}", best_overall)

            if best.sharpe > TARGET_SHARPE:
                StrategyVault.save_strategy(
                    best,
                    metadata={
                        "symbol": symbol,
                        "start_date": start_date,
                        "interval": interval,
                        "population_size": POPULATION_SIZE,
                        "num_generations": gen,
                        "initial_capital": INITIAL_CAPITAL,
                        "target_sharpe": TARGET_SHARPE,
                        "search_run": run_num,
                    },
                    path=STRATEGY_VAULT_PATH,
                )
                elapsed = time.time() - start_time
                print("\n" + "=" * 70)
                print("TARGET ACHIEVED")
                print("=" * 70)
                print_strategy_summary("Best strategy", best)
                print(f"Elapsed: {elapsed:.1f}s")
                print(f"Saved to: {STRATEGY_VAULT_PATH}")
                print("\nExpression:")
                print(best.get_expr())
                return

            if gen < NUM_GENERATIONS:
                engine.evolve_generation()

        run_best = engine.get_best_strategy()
        StrategyVault.save_strategy(
            run_best,
            metadata={
                "symbol": symbol,
                "start_date": start_date,
                "interval": interval,
                "population_size": POPULATION_SIZE,
                "num_generations": NUM_GENERATIONS,
                "initial_capital": INITIAL_CAPITAL,
                "target_sharpe": TARGET_SHARPE,
                "search_run": run_num,
            },
            path=STRATEGY_VAULT_PATH,
        )
        print_strategy_summary(f"Run {run_num} best", run_best)

    print("\n" + "=" * 70)
    print("TARGET NOT REACHED")
    print("=" * 70)
    if best_overall is not None:
        print_strategy_summary("Best Sharpe found", best_overall)
        print("\nExpression:")
        print(best_overall.get_expr())


if __name__ == "__main__":
    main()
