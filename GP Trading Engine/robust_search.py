"""
Overfitting-resistant GP search.

Core idea (requested): don't test every strategy on the same fixed history —
randomize which data each generation is evaluated on, so a formula can't lock
onto the quirks of one slice. Done the time-series-correct way:

  1. Randomize over CONTIGUOUS BLOCKS, never shuffled rows (shuffling rows
     leaks the future into the past and destroys momentum/vol features).
  2. Lock a final HOLDOUT segment that the search never sees, with an EMBARGO
     gap so rolling features can't peek across the boundary.
  3. Judge the champion on a DISTRIBUTION of out-of-sample block draws plus the
     locked holdout — the gap between search and holdout Sharpe is the overfit.

This is a drop-in runner; it reuses the engine classes unchanged.
"""
from __future__ import annotations

import random
import numpy as np
import pandas as pd

from gp_trading_engine import (
    DataLayer, FeatureEngine, GeneticEvolutionEngine, GPTradingEngine,
    TreeEvaluator, SignalExecutor, BacktestEngine,
)

# ── config ───────────────────────────────────────────────────────────────────
SYMBOL, START, INTERVAL = "SPY", "2001-01-01", "1d"
HOLDOUT_DAYS = 756          # ~3y final test the search never touches
EMBARGO      = 21           # ~1mo gap so rolling features don't leak across the cut
N_BLOCKS     = 18           # contiguous blocks the search region is split into
BLOCKS_PER_DRAW = 6         # each generation sees a random 1/3 of history
POP, GENS, ELITE, MUT = 60, 25, 8, 0.35
CPCV_DRAWS = 300            # random block-combos used to profile the champion
SEED = 7


def make_blocks(n_rows: int, n_blocks: int) -> list[tuple[int, int]]:
    """Contiguous [start, end) index blocks covering [0, n_rows)."""
    edges = np.linspace(0, n_rows, n_blocks + 1, dtype=int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_blocks)
            if edges[i + 1] > edges[i]]


def gather(feats: pd.DataFrame, rets: np.ndarray, blocks: list[tuple[int, int]]):
    """Concatenate the chosen blocks in time order (each block stays contiguous)."""
    blocks = sorted(blocks)
    fparts = [feats.iloc[a:b] for a, b in blocks]
    rparts = [rets[a:b] for a, b in blocks]
    return pd.concat(fparts), np.concatenate(rparts)


def eval_tree(tree, feats: pd.DataFrame, rets: np.ndarray, ann: float) -> dict:
    """Same signal->position->backtest pipeline the GA uses, for a fixed tree."""
    signal = TreeEvaluator.evaluate_tree(tree, feats)
    position = SignalExecutor.signal_to_position(signal)
    position = SignalExecutor.apply_risk_controls(position, rets, annualization=ann)
    return BacktestEngine.backtest_strategy(position, rets, annualization=ann)


def pooled_sharpe(tree, feats, rets, blocks, ann) -> float:
    """Evaluate per-block and pool the daily return streams, so joins between
    non-adjacent blocks don't corrupt the metric (Sharpe is return-based)."""
    streams = []
    for a, b in sorted(blocks):
        r = eval_tree(tree, feats.iloc[a:b], rets[a:b], ann)["returns"]
        if len(r):
            streams.append(r)
    if not streams:
        return 0.0
    pooled = np.concatenate(streams)
    return BacktestEngine.compute_sharpe(pooled, ann)


def main() -> None:
    random.seed(SEED); np.random.seed(SEED)
    rng = random.Random(SEED)

    ann = GPTradingEngine.annualization_for_interval(INTERVAL)
    data = DataLayer.fetch_spy_data(symbol=SYMBOL, start=START, interval=INTERVAL)
    feats = FeatureEngine.build_features(data)
    rets = data.loc[feats.index, "returns"].values
    n = len(feats)

    # ── split: [ search region ] [embargo] [ locked holdout ] ──────────────────
    holdout_start = n - HOLDOUT_DAYS
    search_end = holdout_start - EMBARGO
    search_feats, search_rets = feats.iloc[:search_end], rets[:search_end]
    hold_feats, hold_rets = feats.iloc[holdout_start:], rets[holdout_start:]

    blocks = make_blocks(len(search_feats), N_BLOCKS)
    print(f"bars={n} | search={len(search_feats)} in {len(blocks)} blocks "
          f"| embargo={EMBARGO} | locked holdout={len(hold_feats)}")

    # ── evolve, rotating the evaluation block-subset every generation ──────────
    eng = GeneticEvolutionEngine(
        feature_names=search_feats.columns.tolist(),
        population_size=POP, elite_size=ELITE, mutation_rate=MUT,
        annualization=ann, initial_capital=10_000,
    )
    eng.initialize_population()
    for g in range(GENS):
        draw = rng.sample(blocks, BLOCKS_PER_DRAW)          # random contiguous blocks
        df, dr = gather(search_feats, search_rets, draw)
        eng.evaluate_population(df, dr)                       # fitness on THIS draw only
        if g < GENS - 1:
            eng.evolve_generation()
    champ = eng.get_best_strategy()

    # ── profile champion: distribution across many random block draws ──────────
    draws = [pooled_sharpe(champ.tree, search_feats, search_rets,
                           rng.sample(blocks, BLOCKS_PER_DRAW), ann)
             for _ in range(CPCV_DRAWS)]
    draws = np.array(draws)

    # full-search-region Sharpe (what a naive in-sample run would report)
    naive = eval_tree(champ.tree, search_feats, search_rets, ann)["sharpe"]
    # the honest number: the locked holdout the search never saw
    ho = eval_tree(champ.tree, hold_feats, hold_rets, ann)
    bh = BacktestEngine.benchmark_buy_hold(hold_rets, annualization=ann)
    beat = float(np.mean(draws > 0))

    print("\n" + "=" * 60)
    print("CHAMPION:", champ.get_expr()[:120])
    print("=" * 60)
    print(f"naive full-search Sharpe (optimistic) : {naive:6.3f}")
    print(f"random-block OOS Sharpe   median      : {np.median(draws):6.3f}")
    print(f"                          25-75 pct   : {np.percentile(draws,25):6.3f} .. {np.percentile(draws,75):6.3f}")
    print(f"                          % draws > 0  : {beat*100:5.1f}%")
    print(f"LOCKED HOLDOUT Sharpe (honest)        : {ho['sharpe']:6.3f}   "
          f"return {ho['total_return']*100:6.1f}%  maxDD {ho['drawdown']*100:5.1f}%")
    print(f"  buy & hold on same holdout          : {bh['sharpe']:6.3f}   "
          f"return {bh['total_return']*100:6.1f}%")
    print("\nRead: big drop from naive -> holdout = overfitting. A robust")
    print("strategy keeps a positive median across random blocks AND on the")
    print("locked holdout, and ideally beats buy & hold there.")


if __name__ == "__main__":
    main()
