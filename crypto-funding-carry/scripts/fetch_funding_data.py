#!/usr/bin/env python3
"""
Fetch and cache funding + perp + spot history for the carry gauntlet.

Two free, key-less sources:

  * ``--source okx``  — the project's original source. CAVEAT discovered
    2026-07: OKX's public funding-history endpoint only pages back ~3 months,
    which is too short to judge a strategy across regimes.
  * ``--source gate`` (default) — Gate.io pages back YEARS (90 intervals per
    call via the ``to`` cursor) and serves same-venue spot + futures candles,
    so the basis-aware backtest works over the full span. Funding settles
    every 8h, same convention as OKX (1095 intervals/year).

Writes ``data/funding_<COIN>.csv``, ``data/perp_<COIN>.csv``,
``data/spot_<COIN>.csv`` — the exact contract ``scripts/validate_carry.py``
reads. (Binance and Bybit both geo-block US IPs; Kraken Futures caps at ~1y.)

    python scripts/fetch_funding_data.py --years 3
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA",
         "LINK", "LTC", "AVAX", "DOT", "BCH", "ATOM"]

_S = requests.Session()
_S.headers.update({"User-Agent": "cryptostat-funding/0.2"})
_GATE = "https://api.gateio.ws/api/v4"


def gate_funding_history(coin, years):
    """Page Gate.io funding back ``years`` via the ``to`` cursor (90/call)."""
    horizon = int(time.time()) - int(years * 365.25 * 86400)
    rows, to = [], None
    while True:
        params = {"contract": f"{coin}_USDT", "limit": 1000}
        if to:
            params["to"] = to
        d = _S.get(f"{_GATE}/futures/usdt/funding_rate", params=params,
                   timeout=20).json()
        if not isinstance(d, list) or not d:
            break
        rows.extend(d)
        oldest = min(x["t"] for x in d)
        if oldest <= horizon or len(d) < 2:
            break
        to = oldest - 1
        time.sleep(0.25)
    if not rows:
        raise RuntimeError(f"no Gate funding for {coin}")
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"].astype("int64"), unit="s", utc=True)
    df["funding_rate"] = df["r"].astype(float)
    df = (df.drop_duplicates("t").set_index("t").sort_index()[["funding_rate"]])
    return df[df.index >= pd.Timestamp(horizon, unit="s", tz="UTC")]


def gate_perp_history(coin, years):
    """Gate.io futures 8h closes, paged with from/to (<=1999 candles/call)."""
    end = int(time.time())
    start = end - int(years * 365.25 * 86400)
    step = 1999 * 8 * 3600
    out = []
    cur = start
    while cur < end:
        d = _S.get(f"{_GATE}/futures/usdt/candlesticks",
                   params={"contract": f"{coin}_USDT", "interval": "8h",
                           "from": cur, "to": min(cur + step, end)},
                   timeout=20).json()
        if isinstance(d, list):
            out.extend(d)
        cur += step
        time.sleep(0.25)
    if not out:
        raise RuntimeError(f"no Gate perp candles for {coin}")
    idx = pd.to_datetime([int(x["t"]) for x in out], unit="s", utc=True)
    ser = pd.Series([float(x["c"]) for x in out], index=idx, name="close")
    return ser[~ser.index.duplicated()].sort_index()


def gate_spot_history(coin, years):
    """Gate.io spot 8h closes. Spot candle: [t, quote_v, close, high, low, open, ...]."""
    end = int(time.time())
    start = end - int(years * 365.25 * 86400)
    step = 999 * 8 * 3600                       # spot caps at 1000 candles/call
    out = []
    cur = start
    while cur < end:
        d = _S.get(f"{_GATE}/spot/candlesticks",
                   params={"currency_pair": f"{coin}_USDT", "interval": "8h",
                           "from": cur, "to": min(cur + step, end)},
                   timeout=20).json()
        if isinstance(d, list):
            out.extend(x for x in d if isinstance(x, list))
        cur += step
        time.sleep(0.25)
    if not out:
        raise RuntimeError(f"no Gate spot candles for {coin}")
    idx = pd.to_datetime([int(x[0]) for x in out], unit="s", utc=True)
    ser = pd.Series([float(x[2]) for x in out], index=idx, name="close")
    return ser[~ser.index.duplicated()].sort_index()


def fetch_okx(coin, years):
    """Original OKX source (kept for comparison; ~3 months depth only)."""
    from cryptostat.funding.data import (
        funding_history, perp_price_history, spot_price_history)
    n = int(years * 1095)
    return (funding_history(coin, limit=n),
            perp_price_history(coin, limit=n + 200),
            spot_price_history(coin, limit=n + 200))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["gate", "okx"], default="gate")
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--coins", nargs="*", default=COINS)
    args = ap.parse_args()

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    for c in args.coins:
        try:
            if args.source == "gate":
                f = gate_funding_history(c, args.years)
                p = gate_perp_history(c, args.years)
                s = gate_spot_history(c, args.years)
            else:
                f, p, s = fetch_okx(c, args.years)
            f.to_csv(os.path.join(ROOT, "data", f"funding_{c}.csv"))
            p.to_csv(os.path.join(ROOT, "data", f"perp_{c}.csv"))
            s.to_csv(os.path.join(ROOT, "data", f"spot_{c}.csv"))
            print(f"{c}: funding {len(f)} ({f.index.min().date()} -> "
                  f"{f.index.max().date()}) | perp {len(p)} | spot {len(s)}",
                  flush=True)
        except Exception as e:  # noqa: BLE001 — one bad coin shouldn't sink the fetch
            print(f"{c}: FAILED {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
