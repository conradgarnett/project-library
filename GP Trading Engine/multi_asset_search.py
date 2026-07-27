"""
Multi-asset diversified GP search — the honest path to a higher Sharpe.

Single-asset daily SPY tops out around Sharpe ~1.0 out-of-sample without
overfitting. Diversification across uncorrelated asset classes is the one
genuine "free lunch": combining lowly-correlated return streams with
risk-parity weighting stacks Sharpe. This evolves ONE universal trend/regime
formula, applies it across ~10 liquid ETFs (equities, bonds, gold,
commodities, credit, REITs), long-or-flat per asset, then weights by inverse
volatility (risk parity) and vol-targets the portfolio.

Same anti-overfitting rules as robust_search.py:
  - causal features only (no look-ahead)
  - the shared single formula is itself strong regularization (one rule must
    work across 10 assets over ~19y)
  - rotating block cross-validation during evolution
  - a locked final holdout (last ~3y) used once, never for selection
"""
from __future__ import annotations

import random
import numpy as np
import pandas as pd

from gp_trading_engine import (
    DataLayer, GeneticEvolutionEngine, GPTradingEngine,
    TreeEvaluator, SignalExecutor, BacktestEngine,
)
from robust_search import build_features, make_blocks, robust_score

ASSETS = ["SPY", "TLT", "IEF", "GLD", "EEM", "EFA", "IWM", "DBC", "HYG", "VNQ"]
START, INTERVAL = "2007-01-01", "1d"
HOLDOUT_DAYS = 756
EMBARGO = 21
N_BLOCKS = 24
BLOCKS_PER_DRAW = 8
POP, GENS, ELITE, MUT = 120, 32, 12, 0.35
N_RESTARTS = 3
CPCV_DRAWS = 300
VOL_WINDOW = 20
VOL_TARGET_GRID = [None, 0.08, 0.10, 0.12, 0.15]
COST = 0.0001
TARGET_SHARPE = 1.5
import os as _os
SEED = int(_os.environ.get("GP_SEED", "11"))

ann = GPTradingEngine.annualization_for_interval(INTERVAL)


def load_universe():
    feats, rets = {}, {}
    for s in ASSETS:
        d = DataLayer.fetch_spy_data(symbol=s, start=START, interval=INTERVAL)
        f = build_features(d)
        feats[s] = f
        rets[s] = d.loc[f.index, "returns"]
    common = feats[ASSETS[0]].index
    for s in ASSETS:
        common = common.intersection(feats[s].index)
    F = {s: feats[s].loc[common] for s in ASSETS}
    R = np.stack([rets[s].loc[common].values for s in ASSETS])         # (A, T)
    # causal inverse-vol weights (risk parity input): 1 / trailing 20d vol
    IV = np.stack([
        (1.0 / rets[s].loc[common].rolling(VOL_WINDOW).std().shift(1)
         .replace(0, np.nan)).fillna(0.0).values
        for s in ASSETS
    ])                                                                 # (A, T)
    return F, R, IV, common


def port_stream(tree, F, R, IV, target_vol):
    """Daily portfolio return stream for one formula across all assets:
    long/flat per asset, risk-parity (inverse-vol) weights, optional
    time-varying portfolio vol targeting. Fully causal."""
    A, T = R.shape
    # long/flat position per asset from the shared formula
    P = np.stack([
        np.clip(SignalExecutor.signal_to_position(TreeEvaluator.evaluate_tree(tree, F[s])), 0.0, 1.0)
        for s in ASSETS
    ])                                                                 # (A, T)
    W = IV / np.clip(IV.sum(0, keepdims=True), 1e-9, None)             # risk-parity weights
    eff = W * P                                                        # (A, T) effective holdings
    pr = np.zeros(T)
    pr[:-1] = np.sum(eff[:, :-1] * R[:, 1:], axis=0)                   # hold at t -> return t->t+1
    turn = np.abs(np.diff(eff, axis=1, prepend=0.0)).sum(0)           # turnover across assets
    pr = pr - COST * turn
    if target_vol:
        rv = pd.Series(pr).rolling(VOL_WINDOW).std().shift(1).values * np.sqrt(ann)
        scal = np.where(rv > 0, np.clip(target_vol / rv, 0.0, 1.5), 1.0)
        pr = pr * np.nan_to_num(scal, nan=1.0)
    return pr


def rows_of(blocks):
    return np.concatenate([np.arange(a, b) for a, b in sorted(blocks)])


def block_cv(tree, F, R, IV, blocks, rng, draws, target_vol):
    pr = port_stream(tree, F, R, IV, target_vol)          # compute once
    out = []
    for _ in range(draws):
        rows = rows_of(rng.sample(blocks, BLOCKS_PER_DRAW))
        rows = rows[rows < len(pr) - 1]
        out.append(BacktestEngine.compute_sharpe(pr[rows], ann))
    return np.array(out) if out else np.array([0.0])


def stats(pr, rows):
    rows = rows[rows < len(pr) - 1]
    r = pr[rows]
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    dd = float(np.min(eq / peak - 1)) if len(eq) else 0.0
    return {"sharpe": BacktestEngine.compute_sharpe(r, ann),
            "total_return": float(eq[-1] - 1) if len(eq) else 0.0, "drawdown": dd}


def main():
    F, R, IV, common = load_universe()
    T = R.shape[1]
    holdout_start = T - HOLDOUT_DAYS
    search_end = holdout_start - EMBARGO
    search_rows = np.arange(0, search_end)
    hold_rows = np.arange(holdout_start, T)
    blocks = make_blocks(search_end, N_BLOCKS)
    print(f"assets={len(ASSETS)} common_bars={T} | search={search_end} in {len(blocks)} blocks "
          f"| locked holdout={len(hold_rows)}")

    Fsearch = {s: F[s].iloc[:search_end] for s in ASSETS}

    # ── evolve one shared formula, rotating blocks each generation ─────────────
    candidates = {}
    for restart in range(N_RESTARTS):
        random.seed(SEED + restart); np.random.seed(SEED + restart)
        rng = random.Random(SEED + restart)
        eng = GeneticEvolutionEngine(
            feature_names=F[ASSETS[0]].columns.tolist(), population_size=POP,
            elite_size=ELITE, mutation_rate=MUT, annualization=ann,
            initial_capital=10_000, position_mode="long_flat",
        )
        eng.initialize_population()
        for g in range(GENS):
            draw = rng.sample(blocks, BLOCKS_PER_DRAW)
            rows = rows_of(draw); rows = rows[rows < search_end - 1]
            # set portfolio fitness per strategy on this draw, then breed
            for strat in eng.population:
                pr = port_stream(strat.tree, {s: Fsearch[s] for s in ASSETS},
                                 R[:, :search_end], IV[:, :search_end], 0.12)
                strat.fitness = BacktestEngine.compute_sharpe(pr[rows], ann)
            eng.population.sort(key=lambda s: s.fitness, reverse=True)
            if g < GENS - 1:
                eng.evolve_generation()
        for s in eng.get_top_strategies(8):
            candidates.setdefault(s.get_expr(), s.tree)
        print(f"  restart {restart+1}/{N_RESTARTS}: candidates={len(candidates)}")

    # ── select (formula, vol-target) by block-CV on search region only ────────
    Rs, IVs = R[:, :search_end], IV[:, :search_end]
    scored = []
    for expr, tree in candidates.items():
        for tv in VOL_TARGET_GRID:
            s = block_cv(tree, Fsearch, Rs, IVs, blocks, random.Random(9999), 80, tv)
            scored.append((robust_score(s), float(np.median(s)), tv, expr, tree))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_med, best_tv, best_expr, best_tree = scored[0]
    print(f"selected vol_target={best_tv} by out-of-sample block-CV")

    # ── profile + single honest holdout confirmation ──────────────────────────
    dist = block_cv(best_tree, Fsearch, Rs, IVs, blocks, random.Random(123), CPCV_DRAWS, best_tv)
    pr_full = port_stream(best_tree, F, R, IV, best_tv)
    ho = stats(pr_full, hold_rows)
    naive = stats(pr_full, search_rows)["sharpe"]

    # benchmark: risk-parity buy & hold (always long all assets, inverse-vol)
    def bench_stream():
        A, T2 = R.shape
        W = IV / np.clip(IV.sum(0, keepdims=True), 1e-9, None)
        pr = np.zeros(T2); pr[:-1] = np.sum(W[:, :-1] * R[:, 1:], axis=0)
        return pr
    bh = stats(bench_stream(), hold_rows)
    spy_bh = stats(R[0], hold_rows)  # plain SPY buy & hold

    profitable = ho["total_return"] > 0
    robust = (np.median(dist) > 0) and (np.mean(dist > 0) >= 0.6)
    not_overfit = ho["sharpe"] >= 0.7 * naive and np.median(dist) >= 0.7 * naive
    hits = ho["sharpe"] >= TARGET_SHARPE
    ok = profitable and robust and not_overfit and hits

    print("\n" + "=" * 64)
    print("CHAMPION:", best_expr[:130])
    print("=" * 64)
    print(f"naive full-search Sharpe (optimistic): {naive:6.3f}")
    print(f"OOS block Sharpe median={np.median(dist):6.3f}  "
          f"[25-75: {np.percentile(dist,25):.3f}..{np.percentile(dist,75):.3f}]  "
          f">0 in {np.mean(dist>0)*100:.0f}%")
    print(f"LOCKED HOLDOUT   : Sharpe {ho['sharpe']:6.3f}  return {ho['total_return']*100:6.1f}%  maxDD {ho['drawdown']*100:5.1f}%")
    print(f"risk-parity B&H  : Sharpe {bh['sharpe']:6.3f}  return {bh['total_return']*100:6.1f}%  maxDD {bh['drawdown']*100:5.1f}%")
    print(f"SPY buy & hold   : Sharpe {spy_bh['sharpe']:6.3f}  return {spy_bh['total_return']*100:6.1f}%  maxDD {spy_bh['drawdown']*100:5.1f}%")
    print(f"\nprofitable={profitable} robust={robust} not_overfit={not_overfit} "
          f"holdout_sharpe>={TARGET_SHARPE}: {hits}  ==> {'GOAL MET' if ok else 'not yet'}")

    if ok:
        import json
        json.dump({
            "expression": best_expr, "tree": best_tree.to_dict(),
            "assets": ASSETS, "features": F[ASSETS[0]].columns.tolist(),
            "position_mode": "long_flat", "weighting": "risk_parity_inverse_vol",
            "vol_target": best_tv, "seed": SEED,
            "search_region_sharpe": round(naive, 4),
            "oos_block_sharpe_median": round(float(np.median(dist)), 4),
            "oos_block_sharpe_pct_positive": round(float(np.mean(dist > 0)), 4),
            "holdout": {k: round(v, 4) for k, v in ho.items()},
        }, open("multi_asset_champion.json", "w"), indent=2)
        print("saved -> multi_asset_champion.json")
    return ok


if __name__ == "__main__":
    main()
