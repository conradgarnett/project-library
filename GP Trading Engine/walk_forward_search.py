"""
Walk-forward GP validation and Calmar-focused search.

Each fold trains on a historical window and validates on the following unseen
window. The script searches for strategies with strong out-of-sample Sharpe and
Calmar, then saves the best validated champion to strategy_vault.json.
"""

from __future__ import annotations

import random
import time

import numpy as np
import pandas as pd

from gp_trading_engine import (
    BacktestEngine,
    DataLayer,
    GeneticEvolutionEngine,
    STRATEGY_VAULT_PATH,
    SignalExecutor,
    Strategy,
    StrategyVault,
    TreeEvaluator,
)


TARGET_SHARPE = 1.0
TARGET_CALMAR = 3.0
INITIAL_CAPITAL = 10_000
TRAIN_WINDOW = 1000
TEST_WINDOW = 252
STEP = 252
MAX_ATTEMPTS = 6
POPULATION_SIZE = 55
GENERATIONS = 10
ELITE_SIZE = 8
MUTATION_RATE = 0.4
ANNUALIZATION = 252
RISK_PRESETS = [
    {
        "name": "long_flat_vol10_dd8",
        "position_mode": "long_flat",
        "max_exposure": 1.0,
        "target_vol": 0.10,
        "drawdown_throttle": 0.08,
        "throttle_exposure": 0.10,
    },
    {
        "name": "long_flat_vol12_dd10",
        "position_mode": "long_flat",
        "max_exposure": 1.0,
        "target_vol": 0.12,
        "drawdown_throttle": 0.10,
        "throttle_exposure": 0.15,
    },
    {
        "name": "capped_long_short_vol10_dd8",
        "position_mode": "long_short",
        "max_exposure": 0.65,
        "target_vol": 0.10,
        "drawdown_throttle": 0.08,
        "throttle_exposure": 0.15,
    },
]


def build_raw_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    close = df["Close"]
    returns = df["returns"]

    features["ret1"] = df["Close"].pct_change(1)
    features["ret5"] = df["Close"].pct_change(5)
    features["ret20"] = df["Close"].pct_change(20)
    features["mom10"] = df["Close"].pct_change(10)
    features["vol"] = returns.rolling(20).std()
    features["vol_60"] = returns.rolling(60).std()

    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma100 = close.rolling(100).mean()
    ma200 = close.rolling(200).mean()
    features["ma_fast"] = (close - ma5) / ma5
    features["ma_slow"] = (close - ma20) / ma20
    features["trend_50"] = (close - ma50) / ma50
    features["trend_100"] = (close - ma100) / ma100
    features["trend_200"] = (close - ma200) / ma200
    features["trend_stack"] = (ma50 / ma200) - 1

    high_low = (df["High"] - df["Low"]) / close
    features["range_20"] = high_low.rolling(20).mean()
    features["dist_52w_high"] = (close / close.rolling(252).max()) - 1
    features["volume_z"] = (
        (df["Volume"] - df["Volume"].rolling(60).mean())
        / df["Volume"].rolling(60).std()
    )
    features["dow"] = df.index.dayofweek / 4.0
    features["month"] = (df.index.month - 1) / 11.0

    return features.replace([np.inf, -np.inf], np.nan)


def normalize_like_train(train_raw: pd.DataFrame, test_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = train_raw.dropna().copy()
    test = test_raw.dropna().copy()

    for col in train.columns:
        mean = train[col].mean()
        std = train[col].std()
        if std > 1e-8:
            train[col] = (train[col] - mean) / std
            test[col] = (test[col] - mean) / std
        else:
            train[col] = 0.0
            test[col] = 0.0

    return train, test


def fold_slices(data: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    folds = []
    for start in range(0, len(data) - TRAIN_WINDOW - TEST_WINDOW + 1, STEP):
        train = data.iloc[start : start + TRAIN_WINDOW]
        test = data.iloc[start + TRAIN_WINDOW : start + TRAIN_WINDOW + TEST_WINDOW]
        folds.append((train, test))
    return folds


def train_fold_strategy(train_features: pd.DataFrame, train_returns: np.ndarray, seed_trees, risk_preset: dict) -> Strategy:
    engine = GeneticEvolutionEngine(
        feature_names=train_features.columns.tolist(),
        population_size=POPULATION_SIZE,
        elite_size=ELITE_SIZE,
        mutation_rate=MUTATION_RATE,
        annualization=ANNUALIZATION,
        initial_capital=INITIAL_CAPITAL,
        position_mode=risk_preset["position_mode"],
        max_exposure=risk_preset["max_exposure"],
        target_vol=risk_preset["target_vol"],
        drawdown_throttle=risk_preset["drawdown_throttle"],
        throttle_exposure=risk_preset["throttle_exposure"],
        calmar_weight=2.5,
        return_weight=1.0,
        cagr_weight=8.0,
        drawdown_weight=3.0,
    )
    engine.initialize_population(seed_trees=seed_trees)

    for gen in range(GENERATIONS):
        engine.evaluate_population(train_features, train_returns)
        if gen < GENERATIONS - 1:
            engine.evolve_generation()

    return engine.get_best_strategy()


def evaluate_tree_on_features(
    tree,
    features: pd.DataFrame,
    returns: np.ndarray,
    risk_preset: dict,
    capital: float = INITIAL_CAPITAL,
) -> dict:
    signal = TreeEvaluator.evaluate_tree(tree, features)
    position = SignalExecutor.signal_to_position(signal)
    position = SignalExecutor.apply_risk_controls(
        position,
        returns,
        mode=risk_preset["position_mode"],
        max_exposure=risk_preset["max_exposure"],
        target_vol=risk_preset["target_vol"],
        annualization=ANNUALIZATION,
    )
    return BacktestEngine.backtest_strategy(
        position,
        returns,
        annualization=ANNUALIZATION,
        initial_capital=capital,
        drawdown_throttle=risk_preset["drawdown_throttle"],
        throttle_exposure=risk_preset["throttle_exposure"],
        calmar_weight=2.5,
        return_weight=1.0,
        cagr_weight=8.0,
        drawdown_weight=3.0,
    )


def aggregate_fold_returns(fold_returns: list[np.ndarray]) -> dict:
    if not fold_returns:
        raise RuntimeError("No fold returns to aggregate.")

    returns = np.concatenate(fold_returns)
    return BacktestEngine.backtest_strategy(
        np.ones(len(returns)),
        np.r_[0.0, returns],
        turnover_cost=0.0,
        annualization=ANNUALIZATION,
        initial_capital=INITIAL_CAPITAL,
    )


def print_metrics(label: str, metrics: dict) -> None:
    print(
        f"{label}: sharpe={metrics['sharpe']:.4f} | "
        f"calmar={metrics['calmar']:.4f} | "
        f"cagr={metrics['cagr'] * 100:.2f}% | "
        f"pnl=${metrics['pnl']:,.2f} | "
        f"return={metrics['total_return'] * 100:.2f}% | "
        f"dd={metrics['drawdown']:.4f} | "
        f"win={metrics['win_rate'] * 100:.2f}%"
    )


def consistency_score(fold_metrics: list[dict]) -> dict:
    cagr_values = np.array([metrics["cagr"] for metrics in fold_metrics])
    sharpe_values = np.array([metrics["sharpe"] for metrics in fold_metrics])
    calmar_values = np.array([metrics["calmar"] for metrics in fold_metrics])
    dd_values = np.array([metrics["drawdown"] for metrics in fold_metrics])

    positive_cagr = float(np.mean(cagr_values > 0))
    positive_sharpe = float(np.mean(sharpe_values > 0))
    median_calmar = float(np.median(calmar_values))
    worst_drawdown = float(np.min(dd_values))

    score = (
        positive_cagr
        + positive_sharpe
        + median_calmar
        + worst_drawdown
        - float(np.std(cagr_values))
    )
    return {
        "score": score,
        "positive_cagr": positive_cagr,
        "positive_sharpe": positive_sharpe,
        "median_calmar": median_calmar,
        "worst_drawdown": worst_drawdown,
    }


def main() -> None:
    started = time.time()
    print("=" * 70)
    print("WALK-FORWARD CALMAR SEARCH")
    print("=" * 70)
    print(f"Targets: Sharpe >= {TARGET_SHARPE:.2f}, Calmar >= {TARGET_CALMAR:.2f}")
    print("Risk controls: volatility targeting, exposure caps, long/flat option, drawdown throttle")

    data = DataLayer.fetch_spy_data(symbol="SPY", start="2001-01-01", interval="1d")
    folds = fold_slices(data)
    print(f"Created {len(folds)} walk-forward folds")

    feature_names = build_raw_features(data).columns.tolist()
    best_oos = None
    best_tree = None
    best_score = -np.inf

    for attempt in range(1, MAX_ATTEMPTS + 1):
        random.seed()
        np.random.seed(None)

        risk_preset = RISK_PRESETS[(attempt - 1) % len(RISK_PRESETS)]

        print("\n" + "=" * 70)
        print(f"ATTEMPT {attempt}/{MAX_ATTEMPTS} | risk={risk_preset['name']}")
        print("=" * 70)

        seed_trees = StrategyVault.load_champions(
            feature_names,
            path=STRATEGY_VAULT_PATH,
            max_champions=20,
        )

        attempt_oos_returns = []
        attempt_candidates = []
        attempt_fold_metrics = []
        attempt_benchmark_returns = []

        for fold_num, (train_df, test_df) in enumerate(folds, 1):
            combined_raw = build_raw_features(pd.concat([train_df, test_df]))
            train_raw = combined_raw.loc[train_df.index]
            test_raw = combined_raw.loc[test_df.index]
            train_features, test_features = normalize_like_train(train_raw, test_raw)

            train_returns = train_df.loc[train_features.index, "returns"].values
            test_returns = test_df.loc[test_features.index, "returns"].values

            candidate = train_fold_strategy(train_features, train_returns, seed_trees, risk_preset)
            test_metrics = evaluate_tree_on_features(candidate.tree, test_features, test_returns, risk_preset)
            attempt_oos_returns.append(test_metrics["returns"])
            attempt_candidates.append(candidate)
            attempt_fold_metrics.append(test_metrics)

            benchmark_metrics = BacktestEngine.benchmark_buy_hold(
                test_returns,
                annualization=ANNUALIZATION,
                initial_capital=INITIAL_CAPITAL,
            )
            attempt_benchmark_returns.append(benchmark_metrics["returns"])

            if fold_num in {1, len(folds)}:
                print_metrics(f"  Fold {fold_num:02d} OOS", test_metrics)

        oos_metrics = aggregate_fold_returns(attempt_oos_returns)
        benchmark_oos = aggregate_fold_returns(attempt_benchmark_returns)
        consistency = consistency_score(attempt_fold_metrics)
        research_score = (
            oos_metrics["cagr"] * 8
            + oos_metrics["sharpe"]
            + oos_metrics["calmar"] * 2
            + consistency["score"]
            + (oos_metrics["cagr"] - benchmark_oos["cagr"]) * 4
        )

        print_metrics("Attempt OOS aggregate", oos_metrics)
        print_metrics("SPY buy-hold aggregate", benchmark_oos)
        print(
            "Consistency: "
            f"pos_cagr={consistency['positive_cagr'] * 100:.1f}% | "
            f"pos_sharpe={consistency['positive_sharpe'] * 100:.1f}% | "
            f"median_calmar={consistency['median_calmar']:.3f} | "
            f"score={research_score:.3f}"
        )

        if research_score > best_score:
            best_score = research_score
            best_oos = oos_metrics
            best_tree = max(attempt_candidates, key=lambda strategy: strategy.fitness).tree
            print("  New best walk-forward aggregate.")

        if oos_metrics["sharpe"] >= TARGET_SHARPE and oos_metrics["calmar"] >= TARGET_CALMAR:
            winner = Strategy(
                tree=max(attempt_candidates, key=lambda strategy: strategy.fitness).tree,
                sharpe=oos_metrics["sharpe"],
                calmar=oos_metrics["calmar"],
                cagr=oos_metrics["cagr"],
                drawdown=oos_metrics["drawdown"],
                fitness=oos_metrics["fitness"],
                turnover=oos_metrics["turnover"],
                final_equity=oos_metrics["final_equity"],
                pnl=oos_metrics["pnl"],
                total_return=oos_metrics["total_return"],
                win_rate=oos_metrics["win_rate"],
            )
            StrategyVault.save_strategy(
                winner,
                metadata={
                    "symbol": "SPY",
                    "validation": "walk_forward",
                    "train_window": TRAIN_WINDOW,
                    "test_window": TEST_WINDOW,
                    "step": STEP,
                    "attempt": attempt,
                    "target_sharpe": TARGET_SHARPE,
                    "target_calmar": TARGET_CALMAR,
                    "initial_capital": INITIAL_CAPITAL,
                    "risk_preset": risk_preset,
                    "consistency": consistency,
                    "benchmark": {
                        "sharpe": benchmark_oos["sharpe"],
                        "calmar": benchmark_oos["calmar"],
                        "cagr": benchmark_oos["cagr"],
                        "drawdown": benchmark_oos["drawdown"],
                    },
                },
                path=STRATEGY_VAULT_PATH,
            )
            print("\nTARGET ACHIEVED")
            print_metrics("Winning walk-forward OOS", oos_metrics)
            print(f"Elapsed: {time.time() - started:.1f}s")
            print("Expression:")
            print(winner.get_expr())
            return

    print("\nTARGET NOT REACHED")
    if best_oos is not None:
        print_metrics("Best walk-forward OOS", best_oos)
    if best_tree is not None:
        print("Best representative expression:")
        print(best_tree.to_expr())


if __name__ == "__main__":
    main()
