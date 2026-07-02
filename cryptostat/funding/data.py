"""
Funding-rate data (OKX perpetual swaps) — free, key-less.

Perpetual futures never expire, so a **funding rate** paid every 8 hours tethers
the perp price to spot: when the perp trades rich (crowd is long), longs pay
shorts; when cheap, shorts pay longs. That recurring payment is the edge a
delta-neutral carry harvests (see :mod:`cryptostat.funding.carry`).

OKX publishes current and full historical funding rates for its `*-USDT-SWAP`
perps with no API key. (Binance is geo-blocked from some regions; OKX works.)
"""

from __future__ import annotations

import time

import pandas as pd
import requests

OKX_FUNDING_INTERVAL_H = 8          # OKX settles funding every 8 hours
FUNDING_INTERVALS_PER_YEAR = int(round(365 * 24 / OKX_FUNDING_INTERVAL_H))  # 1095

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "cryptostat/0.1"})
_BASE = "https://www.okx.com/api/v5/public"


def _inst(coin: str) -> str:
    return f"{coin.upper()}-USDT-SWAP"


def funding_now(coin: str = "BTC") -> dict:
    """Current (upcoming) funding rate for a coin's OKX perp."""
    d = _SESSION.get(f"{_BASE}/funding-rate", params={"instId": _inst(coin)},
                     timeout=15).json()
    row = d["data"][0]
    return {
        "coin": coin.upper(),
        "funding_rate": float(row["fundingRate"]),
        "next_funding_time": pd.to_datetime(int(row["fundingTime"]), unit="ms", utc=True),
    }


def funding_history(coin: str = "BTC", limit: int = 1095) -> pd.DataFrame:
    """
    Historical realized funding rates for a coin's OKX perp, time-indexed
    (most recent ``limit`` settlements; OKX pages 100 at a time going back).

    Returns a DataFrame with a single ``funding_rate`` column (fraction paid per
    8-hour interval). Multiply by ~1095 to annualize a constant rate.
    """
    url = f"{_BASE}/funding-rate-history"
    rows, after = [], None
    while len(rows) < limit:
        params = {"instId": _inst(coin), "limit": 100}
        if after:
            params["after"] = after
        d = _SESSION.get(url, params=params, timeout=20).json()
        data = d.get("data", [])
        if not data:
            break
        rows.extend(data)
        after = data[-1]["fundingTime"]         # oldest ts in this batch -> page back
        time.sleep(0.2)
        if len(data) < 100:
            break

    if not rows:
        raise RuntimeError(f"no OKX funding history for {coin}")
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms", utc=True)
    df["funding_rate"] = df["fundingRate"].astype(float)
    df = (df.drop_duplicates("fundingTime").set_index("fundingTime")
            .sort_index()[["funding_rate"]])
    return df.tail(limit)
