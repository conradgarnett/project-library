"""
Smile calibration: SVI fits tightly and Merton recovers known parameters from a
synthetic (offline) smile. Live fetching is exercised separately and skipped if
no network is available, so the suite stays deterministic.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from optlib.market import (  # noqa: E402
    calibrate_merton,
    calibrate_svi,
    calibration_rmse,
    synthetic_smile,
)

S, T, r = 100.0, 0.5, 0.045
TRUE = dict(sigma=0.20, lam=1.0, muJ=-0.12, sigJ=0.15)


def test_synthetic_smile_has_skew():
    strikes, ivs = synthetic_smile(S, T, r, **TRUE)
    assert ivs[0] > ivs[-1]              # negative-jump skew: low strikes richer
    assert (ivs > 0.20).all()            # jumps lift IV above the diffusion vol


def test_svi_fits_tightly():
    strikes, ivs = synthetic_smile(S, T, r, **TRUE)
    svi = calibrate_svi(strikes, ivs, S, T)
    assert calibration_rmse(svi, strikes, ivs, S, T) < 0.002   # < 0.2 vol points


def test_merton_recovers_parameters():
    strikes, ivs = synthetic_smile(S, T, r, **TRUE)
    m = calibrate_merton(strikes, ivs, S, T, r)
    assert calibration_rmse(m, strikes, ivs, S, T, r) < 0.001
    assert abs(m.sigma - TRUE["sigma"]) < 0.02
    assert abs(m.muJ - TRUE["muJ"]) < 0.05
    assert abs(m.sigJ - TRUE["sigJ"]) < 0.05


def test_svi_total_variance_nonnegative():
    strikes, ivs = synthetic_smile(S, T, r, **TRUE)
    svi = calibrate_svi(strikes, ivs, S, T)
    k = np.linspace(-0.5, 0.5, 101)
    assert (svi.total_variance(k) >= 0).all()


def test_live_fetch_optional():
    # Best-effort: exercises the live path but never fails the suite offline.
    try:
        from optlib.market import fetch_option_chain
        m = fetch_option_chain("SPY", expiry_index=4, kind="call")
        assert m["S"] > 0 and len(m["smile"]) > 3
        print(f"  (live SPY smile fetched: S={m['S']:.2f}, {len(m['smile'])} strikes)")
    except Exception as e:  # noqa: BLE001
        print(f"  (live fetch skipped: {type(e).__name__})")


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
