"""Scenario / risk grid behaves correctly for known positions."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from optlib.scenario import scenario_grid, scenario_summary  # noqa: E402
from optlib.strategy import Leg, straddle  # noqa: E402


def test_straddle_grid_shape_and_entry():
    sg = scenario_grid(straddle(100), 100, 0.25, 0.04, 0.25)
    assert sg.metrics["pnl"].shape == (sg.vols.size, sg.spots.size)
    ci, ri = sg.spots.size // 2, sg.vols.size // 2
    # At (base vol, ATM) the P&L is ~0 (that's the entry point).
    assert abs(sg.metrics["pnl"][ri, ci]) < 1e-6


def test_long_straddle_gains_on_moves_and_vol():
    sg = scenario_grid(straddle(100), 100, 0.25, 0.04, 0.25)
    ci, ri = sg.spots.size // 2, sg.vols.size // 2
    pnl = sg.metrics["pnl"]
    assert pnl[ri, -1] > 0 and pnl[ri, 0] > 0        # big spot moves profit
    assert pnl[-1, ci] > pnl[0, ci]                   # higher vol helps long vega


def test_time_decay_hurts_atm_straddle():
    base = scenario_grid(straddle(100), 100, 0.25, 0.04, 0.25)
    rolled = scenario_grid(straddle(100), 100, 0.25, 0.04, 0.25, days_forward=20)
    ci, ri = base.spots.size // 2, base.vols.size // 2
    assert rolled.metrics["pnl"][ri, ci] < 0          # theta bleed at ATM


def test_single_leg_delta_bounds():
    sg = scenario_grid(Leg("call", 1, 100), 100, 0.5, 0.04, 0.2)
    assert 0.0 <= sg.metrics["delta"].min() and sg.metrics["delta"].max() <= 1.0
    summ = scenario_summary(sg)
    assert set(summ["metric"]) >= {"pnl", "delta", "gamma", "vega", "theta", "rho"}


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
