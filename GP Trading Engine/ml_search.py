"""
Supervised-ML strategy finder — a different search method than the GP.

Instead of evolving formulas, this fits a gradient-boosting regressor that
predicts each asset's next-day return from the causal features, converts the
prediction to a long/flat position, and combines across the 10-asset universe
with risk-parity weighting.

Anti-overfitting rigor is unchanged and is the whole point:
  - causal features only (no look-ahead)
  - ONE pooled model across all assets (more data, harder to curve-fit)
  - purged walk-forward: the model only ever predicts days AFTER the days it
    was trained on, with an embargo gap (no leakage)
  - a locked final holdout (last ~3y) used once, never for training/selection
  - regularized model (shallow trees, big leaves, L2) to resist memorizing
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from gp_trading_engine import DataLayer, GPTradingEngine, BacktestEngine
from robust_search import build_features, make_blocks, robust_score
from multi_asset_search import ASSETS, START, INTERVAL, HOLDOUT_DAYS, EMBARGO, \
    N_BLOCKS, BLOCKS_PER_DRAW, VOL_WINDOW, VOL_TARGET_GRID, COST, TARGET_SHARPE

ann = GPTradingEngine.annualization_for_interval(INTERVAL)
WF_FOLDS = 6          # purged walk-forward folds over the search region
import random


def load_universe():
    feats, rc = {}, {}
    for s in ASSETS:
        d = DataLayer.fetch_spy_data(symbol=s, start=START, interval=INTERVAL)
        f = build_features(d)
        feats[s] = f
        rc[s] = d.loc[f.index, "returns"]
    common = feats[ASSETS[0]].index
    for s in ASSETS:
        common = common.intersection(feats[s].index)
    X = [feats[s].loc[common].values for s in ASSETS]         # list of (T, k), by asset index
    Rc = np.stack([rc[s].loc[common].values for s in ASSETS])  # (A, T) contemporaneous
    IV = np.stack([
        (1.0 / rc[s].loc[common].rolling(VOL_WINDOW).std().shift(1)
         .replace(0, np.nan)).fillna(0.0).values for s in ASSETS])
    return X, Rc, IV, feats[ASSETS[0]].loc[common].columns.tolist()


def new_model():
    return HistGradientBoostingRegressor(
        max_depth=3, max_iter=250, learning_rate=0.05,
        min_samples_leaf=200, l2_regularization=1.0, random_state=0)


def train_on(days, X, Rc):
    """Pooled training matrix over the given day indices (label = next-day ret)."""
    days = days[days < Rc.shape[1] - 1]
    Xs = np.concatenate([X[a][days] for a in range(len(ASSETS))])
    ys = np.concatenate([Rc[a, days + 1] for a in range(len(ASSETS))])
    m = new_model(); m.fit(Xs, ys); return m


def predict_positions(model, day_idx, X):
    """Long/flat position per asset for the given days: long when the model
    predicts a positive next-day return."""
    P = np.zeros((len(ASSETS), len(day_idx)))
    for a in range(len(ASSETS)):
        P[a] = (model.predict(X[a][day_idx]) > 0).astype(float)
    return P


def portfolio_returns(P, day_idx, Rc, IV, target_vol):
    """Risk-parity (inverse-vol) weighted long/flat portfolio over day_idx.
    Each selected day t earns its actual next-day return Rc[:, t+1], so this is
    correct even when day_idx concatenates non-contiguous blocks."""
    W = IV[:, day_idx]
    W = W / np.clip(W.sum(0, keepdims=True), 1e-9, None)
    eff = W * P                                                     # (A, L) holdings
    valid = (day_idx < Rc.shape[1] - 1).astype(float)              # day has a t+1
    nxt = np.minimum(day_idx + 1, Rc.shape[1] - 1)
    fwd = Rc[:, nxt]                                                # (A, L) actual t->t+1 return
    pr = (eff * fwd * valid).sum(0)                                 # (L,)
    turn = np.abs(np.diff(eff, axis=1, prepend=0.0)).sum(0)
    pr = pr - COST * turn
    if target_vol:
        rv = pd.Series(pr).rolling(VOL_WINDOW).std().shift(1).values * np.sqrt(ann)
        scal = np.where(rv > 0, np.clip(target_vol / rv, 0.0, 1.5), 1.0)
        pr = pr * np.nan_to_num(scal, nan=1.0)
    return pr


def stats(pr):
    eq = np.cumprod(1 + pr); peak = np.maximum.accumulate(eq)
    dd = float(np.min(eq / peak - 1)) if len(eq) else 0.0
    return {"sharpe": BacktestEngine.compute_sharpe(pr, ann),
            "total_return": float(eq[-1] - 1) if len(eq) else 0.0, "drawdown": dd}


def main():
    X, Rc, IV, feat_names = load_universe()
    A, T = Rc.shape
    holdout_start = T - HOLDOUT_DAYS
    search_end = holdout_start - EMBARGO
    print(f"assets={A} common_bars={T} feats={len(feat_names)} | "
          f"search={search_end} | locked holdout={T - holdout_start}")

    # ── purged walk-forward OOS predictions over the search region ─────────────
    fold_edges = np.linspace(0, search_end, WF_FOLDS + 1, dtype=int)
    oos_pos = np.full((A, search_end), np.nan)
    for i in range(1, WF_FOLDS):
        tr_end = fold_edges[i] - EMBARGO            # embargo gap before the test fold
        train_days = np.arange(0, tr_end)
        test_days = np.arange(fold_edges[i], fold_edges[i + 1])
        if len(train_days) < 250 or len(test_days) == 0:
            continue
        m = train_on(train_days, X, Rc)
        oos_pos[:, test_days] = predict_positions(m, test_days, X)
    have = np.where(~np.isnan(oos_pos[0]))[0]        # days with an OOS prediction
    print(f"walk-forward OOS days: {len(have)} of {search_end}")

    # block-CV Sharpe distribution over the OOS-predicted search region
    blocks = [(a, b) for (a, b) in make_blocks(search_end, N_BLOCKS)
              if np.any(~np.isnan(oos_pos[0, a:b]))]

    def oos_block_dist(target_vol, draws=200):
        rng = random.Random(123); out = []
        for _ in range(draws):
            chosen = sorted(rng.sample(blocks, min(BLOCKS_PER_DRAW, len(blocks))))
            days = np.concatenate([np.arange(a, b) for a, b in chosen])
            days = days[~np.isnan(oos_pos[0, days])]
            if len(days) < 30:
                continue
            P = oos_pos[:, days]
            pr = portfolio_returns(P, days, Rc, IV, target_vol)
            out.append(BacktestEngine.compute_sharpe(pr, ann))
        return np.array(out) if out else np.array([0.0])

    # select vol-target by OOS block-CV (holdout untouched)
    best = max(VOL_TARGET_GRID, key=lambda tv: robust_score(oos_block_dist(tv, 120)))
    dist = oos_block_dist(best, 300)
    print(f"selected vol_target={best} by walk-forward OOS block-CV")

    # ── final: train on all search region, predict locked holdout (once) ───────
    m_final = train_on(np.arange(0, search_end), X, Rc)
    hd = np.arange(holdout_start, T)
    P_h = predict_positions(m_final, hd, X)
    pr_h = portfolio_returns(P_h, hd, Rc, IV, best)
    ho = stats(pr_h)

    # benchmarks on holdout
    W = IV[:, hd]; W = W / np.clip(W.sum(0, keepdims=True), 1e-9, None)
    rp = np.zeros(len(hd))
    for a in range(A):
        rp[:-1] += W[a, :-1] * Rc[a, hd[1:]]
    bh = stats(rp)
    spy = stats(Rc[0, hd])

    naive = float(np.median(dist))
    profitable = ho["total_return"] > 0
    robust = (np.median(dist) > 0) and (np.mean(dist > 0) >= 0.6)
    not_overfit = ho["sharpe"] >= 0.7 * max(naive, 1e-9)
    hits = ho["sharpe"] >= TARGET_SHARPE
    ok = profitable and robust and not_overfit and hits

    print("\n" + "=" * 60)
    print("SUPERVISED-ML STRATEGY (gradient boosting, pooled, risk-parity)")
    print("=" * 60)
    print(f"walk-forward OOS block Sharpe median={np.median(dist):6.3f}  "
          f"[25-75: {np.percentile(dist,25):.3f}..{np.percentile(dist,75):.3f}]  "
          f">0 in {np.mean(dist>0)*100:.0f}%")
    print(f"LOCKED HOLDOUT   : Sharpe {ho['sharpe']:6.3f}  return {ho['total_return']*100:6.1f}%  maxDD {ho['drawdown']*100:5.1f}%")
    print(f"risk-parity B&H  : Sharpe {bh['sharpe']:6.3f}  return {bh['total_return']*100:6.1f}%  maxDD {bh['drawdown']*100:5.1f}%")
    print(f"SPY buy & hold   : Sharpe {spy['sharpe']:6.3f}  return {spy['total_return']*100:6.1f}%  maxDD {spy['drawdown']*100:5.1f}%")
    print(f"\nprofitable={profitable} robust={robust} not_overfit={not_overfit} "
          f"holdout_sharpe>={TARGET_SHARPE}: {hits}  ==> {'GOAL MET' if ok else 'not yet'}")
    return ok


if __name__ == "__main__":
    main()
