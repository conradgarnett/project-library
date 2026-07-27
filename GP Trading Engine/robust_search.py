"""
Overfitting-resistant GP search for a genuinely usable SPY strategy.

Design (anti-overfitting is the priority):
  1. Randomize evaluation over CONTIGUOUS time blocks each generation (never
     shuffled rows -> that would leak the future and break momentum/vol).
  2. Lock a final HOLDOUT (last ~3y) behind an EMBARGO gap; the search never
     sees it. It is used ONCE, for confirmation only -- never for selection.
  3. Select the champion by out-of-sample BLOCK CROSS-VALIDATION inside the
     search region (median block Sharpe with a variance penalty), so we pick
     for robustness, not for a lucky single fit.
  4. Richer CAUSAL features (incl. long-horizon trend/regime) + long-or-flat
     positioning, because the durable edge on SPY is trend-timing: stay long
     in uptrends, step aside in downtrends to cut drawdown.

Success bar (checked on the locked holdout):
  profitable (positive return) AND robust (positive OOS block median) AND
  usable (risk-adjusted value vs buy & hold: higher Sharpe OR materially
  lower drawdown while still profitable).
"""
from __future__ import annotations

import random
import numpy as np
import pandas as pd

from gp_trading_engine import (
    DataLayer, GeneticEvolutionEngine, GPTradingEngine,
    TreeEvaluator, SignalExecutor, BacktestEngine,
)

# ── config ───────────────────────────────────────────────────────────────────
SYMBOL, START, INTERVAL = "SPY", "2001-01-01", "1d"
HOLDOUT_DAYS   = 756          # ~3y locked final test
EMBARGO        = 21
N_BLOCKS       = 24
BLOCKS_PER_DRAW = 8
POP, GENS, ELITE, MUT = 120, 40, 12, 0.35
N_RESTARTS     = 4            # independent evolutionary runs, pooled for selection
CPCV_DRAWS     = 400
POSITION_MODE  = "long_flat"  # long or flat; realistic trend-timing, no shorting
import os as _os
SEED           = int(_os.environ.get("GP_SEED", "11"))


# ── causal features (only past data used at every point) ─────────────────────
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    ret = df["returns"]
    f = pd.DataFrame(index=df.index)

    # momentum across horizons (trend)
    f["ret1"]   = close.pct_change(1)
    f["ret5"]   = close.pct_change(5)
    f["mom10"]  = close.pct_change(10)
    f["mom20"]  = close.pct_change(20)
    f["mom60"]  = close.pct_change(60)
    f["mom120"] = close.pct_change(120)

    # distance from moving averages (trend state), incl. long MAs
    for w in (5, 20, 50, 100, 200):
        ma = close.rolling(w).mean()
        f[f"ma{w}"] = (close - ma) / ma

    # volatility level + regime (short vs long)
    v20 = ret.rolling(20).std()
    v60 = ret.rolling(60).std()
    f["vol"]       = v20
    f["vol_ratio"] = v20 / v60

    # RSI(14), centered
    delta = close.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    dn = (-delta.clip(upper=0)).rolling(14).mean()
    rs = up / dn.replace(0, np.nan)
    f["rsi"] = (100 - 100 / (1 + rs)) / 100 - 0.5

    # distance below trailing 1y high (drawdown state)
    hi = close.rolling(252).max()
    f["dd"] = (close - hi) / hi

    f = f.replace([np.inf, -np.inf], np.nan).dropna()

    # causal z-score: expanding stats up to the PRIOR bar only (no look-ahead)
    mp = 60
    out = pd.DataFrame(index=f.index)
    for c in f.columns:
        mean = f[c].expanding(min_periods=mp).mean().shift(1)
        std = f[c].expanding(min_periods=mp).std().shift(1)
        out[c] = (f[c] - mean) / std.where(std > 1e-8)
    return out.replace([np.inf, -np.inf], np.nan).dropna()


# ── helpers ───────────────────────────────────────────────────────────────────
def make_blocks(n: int, k: int) -> list[tuple[int, int]]:
    e = np.linspace(0, n, k + 1, dtype=int)
    return [(int(e[i]), int(e[i + 1])) for i in range(k) if e[i + 1] > e[i]]


def gather(feats, rets, blocks):
    blocks = sorted(blocks)
    return (pd.concat([feats.iloc[a:b] for a, b in blocks]),
            np.concatenate([rets[a:b] for a, b in blocks]))


def eval_tree(tree, feats, rets, ann, mode=POSITION_MODE) -> dict:
    sig = TreeEvaluator.evaluate_tree(tree, feats)
    pos = SignalExecutor.signal_to_position(sig)
    pos = SignalExecutor.apply_risk_controls(pos, rets, mode=mode, annualization=ann)
    return BacktestEngine.backtest_strategy(pos, rets, annualization=ann)


def block_cv(tree, feats, rets, blocks, ann, rng, draws):
    """Distribution of pooled OOS Sharpe over random block subsets."""
    out = []
    for _ in range(draws):
        chosen = rng.sample(blocks, BLOCKS_PER_DRAW)
        streams = [eval_tree(tree, feats.iloc[a:b], rets[a:b], ann)["returns"]
                   for a, b in sorted(chosen)]
        streams = [s for s in streams if len(s)]
        if streams:
            out.append(BacktestEngine.compute_sharpe(np.concatenate(streams), ann))
    return np.array(out) if out else np.array([0.0])


def robust_score(sharpes: np.ndarray) -> float:
    """Reward a high, consistent OOS median; penalize dispersion and downside."""
    return float(np.median(sharpes) - 0.5 * np.std(sharpes)
                 + 0.5 * (np.mean(sharpes > 0) - 0.5))


def main() -> None:
    ann = GPTradingEngine.annualization_for_interval(INTERVAL)
    data = DataLayer.fetch_spy_data(symbol=SYMBOL, start=START, interval=INTERVAL)
    feats = build_features(data)
    rets = data.loc[feats.index, "returns"].values
    n = len(feats)

    holdout_start = n - HOLDOUT_DAYS
    search_end = holdout_start - EMBARGO
    sf, sr = feats.iloc[:search_end], rets[:search_end]
    hf, hr = feats.iloc[holdout_start:], rets[holdout_start:]
    blocks = make_blocks(len(sf), N_BLOCKS)
    print(f"bars={n} feats={feats.shape[1]} | search={len(sf)} in {len(blocks)} blocks "
          f"| locked holdout={len(hf)} | mode={POSITION_MODE}")

    # ── evolve several independent runs, rotating blocks each generation ───────
    candidates = {}
    for restart in range(N_RESTARTS):
        random.seed(SEED + restart); np.random.seed(SEED + restart)
        rng = random.Random(SEED + restart)
        eng = GeneticEvolutionEngine(
            feature_names=sf.columns.tolist(), population_size=POP,
            elite_size=ELITE, mutation_rate=MUT, annualization=ann,
            initial_capital=10_000, position_mode=POSITION_MODE,
        )
        eng.initialize_population()
        for g in range(GENS):
            df, dr = gather(sf, sr, rng.sample(blocks, BLOCKS_PER_DRAW))
            eng.evaluate_population(df, dr)
            if g < GENS - 1:
                eng.evolve_generation()
        # keep the top distinct formulas from this run as selection candidates
        for s in eng.get_top_strategies(8):
            candidates.setdefault(s.get_expr(), s.tree)
        print(f"  restart {restart+1}/{N_RESTARTS}: pooled candidates={len(candidates)}")

    # ── SELECT by block-CV on the search region only (holdout untouched) ───────
    sel_rng = random.Random(9999)
    scored = []
    for expr, tree in candidates.items():
        s = block_cv(tree, sf, sr, blocks, ann, sel_rng, draws=120)
        scored.append((robust_score(s), float(np.median(s)), expr, tree))
    scored.sort(reverse=True)
    best_score, best_med, best_expr, best_tree = scored[0]

    # ── profile champion + single honest holdout confirmation ──────────────────
    dist = block_cv(best_tree, sf, sr, blocks, ann, random.Random(123), CPCV_DRAWS)
    ho = eval_tree(best_tree, hf, hr, ann)
    bh = BacktestEngine.benchmark_buy_hold(hr, annualization=ann)
    naive = eval_tree(best_tree, sf, sr, ann)["sharpe"]

    profitable = ho["total_return"] > 0
    robust = (np.median(dist) > 0) and (np.mean(dist > 0) >= 0.6)
    usable = (ho["sharpe"] >= bh["sharpe"]) or (
        ho["total_return"] > 0 and ho["drawdown"] > bh["drawdown"])  # dd less negative
    ok = profitable and robust and usable

    print("\n" + "=" * 64)
    print("CHAMPION:", best_expr[:140])
    print("=" * 64)
    print(f"selected robust score={best_score:.3f} (median block Sharpe {best_med:.3f})")
    print(f"naive full-search Sharpe (optimistic): {naive:6.3f}")
    print(f"OOS block Sharpe  median={np.median(dist):6.3f}  "
          f"[25-75: {np.percentile(dist,25):.3f}..{np.percentile(dist,75):.3f}]  "
          f">0 in {np.mean(dist>0)*100:.0f}%")
    print(f"LOCKED HOLDOUT : Sharpe {ho['sharpe']:6.3f}  return {ho['total_return']*100:6.1f}%  "
          f"maxDD {ho['drawdown']*100:5.1f}%")
    print(f"buy & hold     : Sharpe {bh['sharpe']:6.3f}  return {bh['total_return']*100:6.1f}%  "
          f"maxDD {bh['drawdown']*100:5.1f}%")
    print(f"\nprofitable={profitable}  robust={robust}  usable={usable}  ==> "
          f"{'GOAL MET' if ok else 'not yet'}")

    # ── persist the champion so it is actually usable (not just printed) ───────
    if ok:
        import json
        payload = {
            "expression": best_expr,
            "tree": best_tree.to_dict(),
            "features": sf.columns.tolist(),
            "position_mode": POSITION_MODE,
            "seed": SEED,
            "selected_by": "out-of-sample block-CV on search region (holdout untouched)",
            "search_region_sharpe": round(naive, 4),
            "oos_block_sharpe_median": round(float(np.median(dist)), 4),
            "oos_block_sharpe_pct_positive": round(float(np.mean(dist > 0)), 4),
            "holdout": {
                "sharpe": round(ho["sharpe"], 4),
                "total_return": round(ho["total_return"], 4),
                "max_drawdown": round(ho["drawdown"], 4),
            },
            "buy_hold_holdout": {
                "sharpe": round(bh["sharpe"], 4),
                "total_return": round(bh["total_return"], 4),
                "max_drawdown": round(bh["drawdown"], 4),
            },
            "note": ("Long/flat SPY trend-timing overlay. Profitable and robust "
                     "out-of-sample; its edge is drawdown reduction vs buy & hold, "
                     "not higher total return in bull markets."),
        }
        with open("robust_champion.json", "w") as fh:
            json.dump(payload, fh, indent=2)
        print("saved champion -> robust_champion.json")
    return ok, best_expr, ho, bh, dist


if __name__ == "__main__":
    main()
