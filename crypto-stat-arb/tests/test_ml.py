"""ML / neural-net signal: features are leak-free, models learn a real spread,
and the walk-forward driver never peeks at the test window."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cryptostat.statarb.ml import (  # noqa: E402
    spread_features, forward_label, MLSignal, walk_forward_ml,
)


def _mean_reverting_pair(n=1400, seed=0, beta=1.5, amp=8.0, theta=0.06):
    """A genuinely cointegrated pair: B is a random walk, the spread is an OU
    process, A = beta*B + spread. The ML signal should learn to trade it."""
    rng = np.random.default_rng(seed)
    b = np.cumsum(rng.standard_normal(n)) * 0.5 + 100
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = spread[t - 1] - theta * spread[t - 1] + rng.standard_normal() * amp * np.sqrt(theta)
    a = beta * b + spread
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(a, idx), pd.Series(b, idx)


def test_features_shape_and_finite():
    s = np.cumsum(np.random.default_rng(0).standard_normal(200))
    f = spread_features(s, mu=s.mean(), sd=s.std(), lookback=10)
    assert f.shape[0] == s.size
    assert f.shape[1] >= 8
    assert np.isfinite(f).all()           # no NaN/inf leaks into the model


def test_forward_label_is_future_change_with_nan_tail():
    s = np.arange(10, dtype=float)
    lab = forward_label(s, horizon=3, sd=1.0)
    # first entries are the 3-ahead change (=3 for a unit ramp); tail is NaN.
    assert np.allclose(lab[:7], 3.0)
    assert np.isnan(lab[7:]).all()


def test_forward_label_does_not_use_future_beyond_horizon():
    # Changing a value only affects labels at indices within `horizon` before it.
    s = np.zeros(20)
    lab0 = forward_label(s, horizon=4, sd=1.0)
    s2 = s.copy(); s2[10] = 5.0
    lab1 = forward_label(s2, horizon=4, sd=1.0)
    changed = np.where(~np.isclose(np.nan_to_num(lab0), np.nan_to_num(lab1)))[0]
    assert changed.min() >= 10 - 4 and changed.max() <= 10


def test_mlsignal_predict_is_ternary():
    a, b = _mean_reverting_pair(n=600)
    spread = (a - 1.5 * b).values
    sig = MLSignal(kind="gbm", horizon=5).fit(spread[:400])
    pos = sig.predict(spread[400:])
    assert set(np.unique(pos)).issubset({-1.0, 0.0, 1.0})
    assert len(pos) == 200


def test_gbm_learns_tradeable_spread_out_of_sample():
    a, b = _mean_reverting_pair(amp=8.0)
    wf = walk_forward_ml(a, b, train=250, test=40, kind="gbm", cost_bps=1.0, seed=0)
    assert wf.oos_sharpe > 0.3            # a real OU spread should survive OOS
    assert len(wf.folds) > 5


def test_lstm_learns_tradeable_spread_out_of_sample():
    a, b = _mean_reverting_pair(amp=8.0)
    wf = walk_forward_ml(a, b, train=250, test=40, kind="lstm", cost_bps=1.0, seed=0)
    assert wf.oos_sharpe > 0.3


def test_walk_forward_ml_is_deterministic():
    a, b = _mean_reverting_pair(n=900)
    s1 = walk_forward_ml(a, b, train=250, test=40, kind="lstm", seed=1).oos_sharpe
    s2 = walk_forward_ml(a, b, train=250, test=40, kind="lstm", seed=1).oos_sharpe
    assert abs(s1 - s2) < 1e-6            # same seed => identical OOS result


def test_no_leakage_untradeable_when_gated_out():
    # A huge conviction gate can never be cleared => no trades, zero OOS P&L.
    a, b = _mean_reverting_pair(n=900)
    wf = walk_forward_ml(a, b, train=250, test=40, kind="gbm", entry_sigma=1e9, cost_bps=1.0)
    assert wf.folds["n_trades"].sum() == 0
    assert (wf.oos_returns.abs() < 1e-12).all()


def test_z_gate_blocks_disagreeing_trades():
    # With the z-agreement gate, a long can only occur on a cheap spread
    # (z <= -gate) and a short only on a rich one (z >= +gate).
    a, b = _mean_reverting_pair(n=700)
    spread = (a - 1.5 * b).values
    tr, te = spread[:500], spread[500:]
    sig = MLSignal(kind="gbm", z_gate=1.0).fit(tr)
    pos = sig.predict(te)
    z = (te - sig._mu) / sig._sd
    assert (z[pos > 0] <= -1.0).all()
    assert (z[pos < 0] >= 1.0).all()


def test_ensemble_reduces_prediction_variance():
    # The seed-ensemble prediction should sit closer to the seed-average than
    # a typical single seed does (variance reduction, the point of ensembling).
    a, b = _mean_reverting_pair(n=700)
    spread = (a - 1.5 * b).values
    tr, te = spread[:500], spread[500:]
    def feats_of(s_, sig):
        return spread_features(s_, sig._mu, sig._sd, sig.lookback)

    singles = []
    for seed in range(4):
        sig = MLSignal(kind="lstm", n_ensemble=1, seed=seed,
                       model_kwargs={"epochs": 40}).fit(tr)
        singles.append(sig._ensemble_predict(feats_of(te, sig)))
    ens = MLSignal(kind="lstm", n_ensemble=4, seed=0,
                   model_kwargs={"epochs": 40}).fit(tr)
    ens_pred = ens._ensemble_predict(feats_of(te, ens))
    center = np.mean(singles, axis=0)
    mean_single_dev = np.mean([np.std(p - center) for p in singles])
    assert np.std(ens_pred - center) < mean_single_dev + 1e-9


def test_tune_entry_runs_and_records_gate():
    a, b = _mean_reverting_pair(n=900)
    wf = walk_forward_ml(a, b, train=250, test=40, kind="gbm", tune_entry=True, seed=0)
    assert "entry_sigma" in wf.folds.columns
    assert wf.folds["entry_sigma"].isin((0.25, 0.5, 0.75, 1.0, 1.5)).all()


def test_recheck_coint_stands_down_on_broken_pair():
    rng = np.random.default_rng(7)
    n = 1200
    a = pd.Series(np.cumsum(rng.standard_normal(n)) + 100)
    b = pd.Series(np.cumsum(rng.standard_normal(n)) + 100)
    wf = walk_forward_ml(a, b, train=250, test=40, kind="gbm", recheck_coint=True)
    assert wf.folds["stood_down"].any()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1; print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
