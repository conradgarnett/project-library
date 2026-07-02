"""
Fixed-budget GP strategy search with honest out-of-sample reporting.

This replaces the previous "evolve until in-sample Sharpe > 1.0" loop, which
fished with a randomized search until it stumbled onto a lucky *in-sample*
result, then stopped and saved it — with no out-of-sample check at all. That is
textbook selection bias: run enough random searches and you will clear any
in-sample target on noise.

Honest design used here:
  * Data is split chronologically into TRAIN / VALIDATION / HOLDOUT.
  * The GP optimizes fitness on TRAIN only.
  * Candidates are ranked by VALIDATION Sharpe (out-of-sample during the search).
  * The single selected champion is scored ONCE on the locked HOLDOUT, which is
    never used for any selection decision.
  * A FIXED search budget runs to completion (no stopping early on success), and
    the full distribution of out-of-sample scores is reported, so a lucky
    maximum is obvious rather than hidden.
  * The number of strategies evaluated is recorded (it feeds the deflated-Sharpe
    multiple-testing correction in a later fix).

To avoid the vault "ratchet" (re-seeding each search from past champions slowly
mines the validation window), this runner does NOT seed from or write to
strategy_vault.json. It writes a provenance record to search_results.json.
"""

from __future__ import annotations

import io
import json
import contextlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gp_trading_engine import (
    BacktestEngine,
    DataLayer,
    FeatureEngine,
    GeneticEvolutionEngine,
    SignalExecutor,
    TreeEvaluator,
    deepcopy,
)

# ── Fixed search budget (no early stopping) ──────────────────────────────────
N_RUNS = 20
POPULATION_SIZE = 80
NUM_GENERATIONS = 30
INITIAL_CAPITAL = 10_000

# Chronological split fractions (holdout = remainder)
TRAIN_FRAC = 0.60
VAL_FRAC = 0.20  # holdout = 1 - TRAIN_FRAC - VAL_FRAC = 0.20

RESULTS_PATH = Path("search_results.json")


@contextlib.contextmanager
def _quiet():
    """Silence the engine's internal prints during the heavy search loop."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def score_strategy(tree, engine, features, returns) -> dict:
    """Score one strategy tree on an arbitrary (features, returns) slice using
    the exact same pipeline as GeneticEvolutionEngine.evaluate_population."""
    signal = TreeEvaluator.evaluate_tree(tree, features)
    position = SignalExecutor.signal_to_position(signal)
    position = SignalExecutor.apply_risk_controls(
        position, returns,
        mode=engine.position_mode, max_exposure=engine.max_exposure,
        target_vol=engine.target_vol, vol_window=engine.vol_window,
        annualization=engine.annualization,
    )
    return BacktestEngine.backtest_strategy(
        position, returns,
        annualization=engine.annualization, initial_capital=engine.initial_capital,
    )


def main() -> None:
    symbol, start_date, interval = "SPY", "2001-01-01", "1d"
    annualization = GeneticEvolutionEngine(feature_names=["ret1"]).annualization  # default 252

    print("=" * 70)
    print(f"FIXED-BUDGET GP SEARCH  |  {N_RUNS} runs x {POPULATION_SIZE} pop x "
          f"{NUM_GENERATIONS} gens (no early stop)")
    print("=" * 70)

    data = DataLayer.fetch_spy_data(symbol=symbol, start=start_date, interval=interval)
    features = FeatureEngine.build_features(data)          # causal (leak-free) normalization
    returns = data.loc[features.index, "returns"].values
    names = features.columns.tolist()

    # Chronological train / validation / holdout split
    n = len(features)
    i_tr = int(n * TRAIN_FRAC)
    i_va = int(n * (TRAIN_FRAC + VAL_FRAC))
    f_tr, r_tr = features.iloc[:i_tr], returns[:i_tr]
    f_va, r_va = features.iloc[i_tr:i_va], returns[i_tr:i_va]
    f_ho, r_ho = features.iloc[i_va:], returns[i_va:]
    print(f"\nbars: {n} | train {len(f_tr)} ({features.index[0].date()}..{features.index[i_tr-1].date()}) "
          f"| val {len(f_va)} ({features.index[i_tr].date()}..{features.index[i_va-1].date()}) "
          f"| holdout {len(f_ho)} ({features.index[i_va].date()}..{features.index[-1].date()})\n")

    ref = GeneticEvolutionEngine(feature_names=names, population_size=POPULATION_SIZE,
                                 annualization=annualization, initial_capital=INITIAL_CAPITAL)

    n_eval = 0
    champion = None              # best-by-validation tree seen anywhere
    champion_val = -np.inf
    val_scores = []              # validation Sharpe of each run's best-by-validation

    for run in range(1, N_RUNS + 1):
        engine = GeneticEvolutionEngine(
            feature_names=names, population_size=POPULATION_SIZE, elite_size=8,
            mutation_rate=0.35, annualization=annualization, initial_capital=INITIAL_CAPITAL,
        )
        with _quiet():
            engine.initialize_population(seed_trees=[])     # no vault seeding (no ratchet)

        run_best_tree, run_best_val = None, -np.inf
        for gen in range(1, NUM_GENERATIONS + 1):
            with _quiet():
                engine.evaluate_population(f_tr, r_tr)      # optimize on TRAIN only
            n_eval += len(engine.population)
            # rank this generation's elite by VALIDATION (out-of-sample) Sharpe
            for strat in engine.get_top_strategies(engine.elite_size):
                v = score_strategy(strat.tree, ref, f_va, r_va)["sharpe"]
                if v > run_best_val:
                    run_best_val, run_best_tree = v, deepcopy(strat.tree)
            if gen < NUM_GENERATIONS:
                with _quiet():
                    engine.evolve_generation()

        val_scores.append(run_best_val)
        if run_best_val > champion_val:
            champion_val, champion = run_best_val, run_best_tree
        print(f"run {run:2d}/{N_RUNS} | best validation Sharpe = {run_best_val:+.3f}")

    # Score the single selected champion ONCE on the locked holdout
    tr = score_strategy(champion, ref, f_tr, r_tr)
    va = score_strategy(champion, ref, f_va, r_va)
    ho = score_strategy(champion, ref, f_ho, r_ho)
    val_arr = np.array(val_scores)

    print("\n" + "=" * 70)
    print("RESULTS (honest, fixed-budget)")
    print("=" * 70)
    print(f"strategies evaluated      : {n_eval}")
    print(f"validation Sharpe across {N_RUNS} runs:")
    print(f"   best {val_arr.max():+.3f} | median {np.median(val_arr):+.3f} | "
          f"min {val_arr.min():+.3f} | runs > 0: {int((val_arr > 0).sum())}/{N_RUNS}")
    print(f"selected champion         : {_expr(champion)}")
    print(f"   train      Sharpe {tr['sharpe']:+.3f}  return {tr['total_return']*100:+.1f}%")
    print(f"   validation Sharpe {va['sharpe']:+.3f}  return {va['total_return']*100:+.1f}%")
    print(f"   HOLDOUT    Sharpe {ho['sharpe']:+.3f}  return {ho['total_return']*100:+.1f}%   (scored once)")
    print(f"   overfit gap (train - holdout) : {tr['sharpe'] - ho['sharpe']:+.3f}")
    print("\nNOTE: with this many strategies evaluated, the *best* validation Sharpe")
    print("is upward-biased by chance. A deflated-Sharpe correction (next fix) tells")
    print("you whether the holdout result clears that bar.")

    record = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "start_date": start_date, "interval": interval,
        "budget": {"n_runs": N_RUNS, "population": POPULATION_SIZE,
                   "generations": NUM_GENERATIONS, "strategies_evaluated": n_eval},
        "splits": {"train": len(f_tr), "validation": len(f_va), "holdout": len(f_ho)},
        "champion_expression": _expr(champion),
        "champion_tree": champion.to_dict(),
        "scores": {"train": tr["sharpe"], "validation": va["sharpe"], "holdout": ho["sharpe"]},
        "validation_distribution": {"best": float(val_arr.max()),
                                    "median": float(np.median(val_arr)),
                                    "min": float(val_arr.min())},
    }
    RESULTS_PATH.write_text(json.dumps(record, indent=2))
    print(f"\nProvenance written to: {RESULTS_PATH}")


def _expr(tree) -> str:
    return tree.to_expr()


if __name__ == "__main__":
    main()
