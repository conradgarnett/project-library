#!/usr/bin/env python3
"""Run every test module and print a combined summary (no pytest needed)."""

from __future__ import annotations

import glob
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _load(path):
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    total = passed = 0
    for f in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        mod = _load(f)
        fns = [v for k, v in sorted(vars(mod).items())
               if k.startswith("test_") and callable(v)]
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except AssertionError as e:
                print(f"FAIL  {os.path.basename(f)}::{fn.__name__}: {e}")
            except Exception as e:  # noqa: BLE001
                print(f"ERROR {os.path.basename(f)}::{fn.__name__}: {type(e).__name__}: {e}")
        print(f"  {os.path.basename(f):24s} ({len(fns)} tests)")
    print(f"\n{passed}/{total} tests passed")
    return 1 if passed != total else 0


if __name__ == "__main__":
    sys.exit(main())
