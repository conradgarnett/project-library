"""CME-complex futures — quotes via Yahoo (yf_throttle) + CFTC Commitment
of Traders positioning (official, free, no key).

CME's own APIs (DataMine / CME Direct) are licensed; Yahoo's =F symbols carry
the same front-month contracts with ~10-min delay, and the CFTC legacy
futures-only COT report adds real positioning data (large-spec net length,
weekly change, open interest) per market.
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

# Socrata endpoint for the CFTC legacy futures-only COT report (weekly)
COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# complex → [(yahoo_symbol, display_name)]
FUTURES_GROUPS = {
    "Equity Index": [
        ("ES=F", "E-mini S&P 500"), ("NQ=F", "E-mini Nasdaq 100"),
        ("YM=F", "E-mini Dow"),     ("RTY=F", "E-mini Russell 2000"),
    ],
    "Rates": [
        ("ZT=F", "2Y T-Note"), ("ZF=F", "5Y T-Note"),
        ("ZN=F", "10Y T-Note"), ("ZB=F", "30Y T-Bond"),
    ],
    "Energy": [
        ("CL=F", "WTI Crude"), ("BZ=F", "Brent Crude"),
        ("NG=F", "Nat Gas"),   ("RB=F", "RBOB Gasoline"),
        ("HO=F", "Heating Oil"),
    ],
    "Metals": [
        ("GC=F", "Gold"), ("SI=F", "Silver"),
        ("HG=F", "Copper"), ("PL=F", "Platinum"), ("PA=F", "Palladium"),
    ],
    "Grains": [
        ("ZC=F", "Corn"), ("ZS=F", "Soybeans"), ("ZW=F", "Wheat (SRW)"),
        ("ZM=F", "Soybean Meal"), ("ZL=F", "Soybean Oil"),
    ],
    "Softs": [
        ("KC=F", "Coffee"), ("SB=F", "Sugar"),
        ("CC=F", "Cocoa"),  ("CT=F", "Cotton"),
    ],
    "Livestock": [
        ("LE=F", "Live Cattle"), ("HE=F", "Lean Hogs"),
    ],
    "FX": [
        ("6E=F", "Euro FX"), ("6J=F", "Japanese Yen"),
        ("6B=F", "British Pound"), ("6A=F", "Aussie Dollar"),
        ("6C=F", "Canadian Dollar"),
    ],
    "Crypto": [
        ("BTC=F", "Bitcoin"), ("ETH=F", "Ether"),
    ],
}

ALL_SYMBOLS = [(sym, name, grp)
               for grp, pairs in FUTURES_GROUPS.items()
               for sym, name in pairs]

# COT market name substrings → our symbol (legacy report names, all caps)
COT_MATCH = {
    "E-MINI S&P 500":         "ES=F",
    "NASDAQ MINI":            "NQ=F",
    "DJIA Consolidated":      "YM=F",
    "RUSSELL E-MINI":         "RTY=F",
    "UST 2Y NOTE":            "ZT=F",
    "UST 5Y NOTE":            "ZF=F",
    "UST 10Y NOTE":           "ZN=F",
    "UST BOND":               "ZB=F",
    "WTI-PHYSICAL":           "CL=F",
    "NAT GAS NYME":           "NG=F",
    "GASOLINE RBOB":          "RB=F",
    "GOLD - COMMODITY":       "GC=F",
    "SILVER - COMMODITY":     "SI=F",
    "COPPER- #1":             "HG=F",
    "PLATINUM":               "PL=F",
    "PALLADIUM":              "PA=F",
    "CORN - CHICAGO":         "ZC=F",
    "SOYBEANS - CHICAGO":     "ZS=F",
    "WHEAT-SRW":              "ZW=F",
    "SOYBEAN MEAL":           "ZM=F",
    "SOYBEAN OIL":            "ZL=F",
    "COFFEE C":               "KC=F",
    "SUGAR NO. 11":           "SB=F",
    "COCOA":                  "CC=F",
    "COTTON NO. 2":           "CT=F",
    "LIVE CATTLE":            "LE=F",
    "LEAN HOGS":              "HE=F",
    "EURO FX - CHICAGO":      "6E=F",
    "JAPANESE YEN":           "6J=F",
    "BRITISH POUND":          "6B=F",
    "AUSTRALIAN DOLLAR":      "6A=F",
    "CANADIAN DOLLAR":        "6C=F",
    "BITCOIN - CHICAGO":      "BTC=F",
    "ETHER":                  "ETH=F",
}


@dataclass
class FuturesState:
    quotes:  dict  = field(default_factory=dict)   # symbol → quote dict
    groups:  dict  = field(default_factory=dict)   # complex → [symbols]
    cot:     dict  = field(default_factory=dict)   # symbol → positioning dict
    cot_date: str  = ""
    updated: float = 0.0
    error:   Optional[str] = None


_state = FuturesState()


def get_futures() -> FuturesState:
    return _state


# ── quotes (yfinance, serialized through the global throttle) ────────────────

def _yf_quote(sym: str, name: str, grp: str) -> Optional[dict]:
    try:
        import yfinance as yf
        fi = yf.Ticker(sym).fast_info
        price = float(fi.last_price or 0)
        prev  = float(fi.previous_close or price)
        if price <= 0:
            return None
        change = price - prev
        return {
            "symbol":     sym,
            "name":       name,
            "complex":    grp,
            "price":      price,
            "change":     round(change, 4),
            "change_pct": round(change / prev * 100, 3) if prev else 0.0,
            "day_high":   float(fi.day_high or 0),
            "day_low":    float(fi.day_low or 0),
        }
    except Exception:
        return None


# ── CFTC COT positioning ─────────────────────────────────────────────────────

def _fnum(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


async def _fetch_cot(session: aiohttp.ClientSession) -> tuple[str, dict]:
    """Latest weekly COT report: large-spec (non-commercial) net positioning
    for the markets we track. Two queries: newest report date, then all rows
    for that date."""
    async with session.get(
        COT_URL,
        params={"$limit": "1", "$order": "report_date_as_yyyy_mm_dd DESC",
                "$select": "report_date_as_yyyy_mm_dd"},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as r:
        if r.status != 200:
            return "", {}
        rows = await r.json()
    if not rows:
        return "", {}
    latest = rows[0]["report_date_as_yyyy_mm_dd"]

    async with session.get(
        COT_URL,
        params={"$limit": "500",
                "$where": f"report_date_as_yyyy_mm_dd='{latest}'"},
        timeout=aiohttp.ClientTimeout(total=20),
    ) as r:
        if r.status != 200:
            return latest[:10], {}
        rows = await r.json()

    cot: dict = {}
    for row in rows:
        mkt = (row.get("market_and_exchange_names") or "").upper()
        sym = next((s for pat, s in COT_MATCH.items() if pat.upper() in mkt), None)
        if not sym or sym in cot:
            continue
        nc_long  = _fnum(row.get("noncomm_positions_long_all"))
        nc_short = _fnum(row.get("noncomm_positions_short_all"))
        cot[sym] = {
            "market":          row.get("market_and_exchange_names", ""),
            "spec_long":       nc_long,
            "spec_short":      nc_short,
            "spec_net":        nc_long - nc_short,
            "spec_net_change": (_fnum(row.get("change_in_noncomm_long_all"))
                                - _fnum(row.get("change_in_noncomm_short_all"))),
            "comm_net":        (_fnum(row.get("comm_positions_long_all"))
                                - _fnum(row.get("comm_positions_short_all"))),
            "open_interest":   _fnum(row.get("open_interest_all")),
        }
    return latest[:10], cot


# ── poller ────────────────────────────────────────────────────────────────────

async def run_poller(interval: int = 600):
    global _state
    from feeds.yf_throttle import run as yf_run
    cot_last = 0.0
    while True:
        try:
            quotes: dict = {}
            for sym, name, grp in ALL_SYMBOLS:
                q = await yf_run(_yf_quote, sym, name, grp)
                if q:
                    quotes[sym] = q

            # COT is weekly — refetch every 6h at most
            if time.time() - cot_last >= 6 * 3600:
                try:
                    async with aiohttp.ClientSession(
                        headers={"User-Agent": "OpenBloombergTerminal/2.0"}
                    ) as session:
                        cot_date, cot = await _fetch_cot(session)
                    if cot:
                        _state.cot, _state.cot_date = cot, cot_date
                        cot_last = time.time()
                except Exception:
                    pass

            if quotes:
                _state.quotes  = quotes
                _state.groups  = {grp: [s for s, _ in pairs]
                                  for grp, pairs in FUTURES_GROUPS.items()}
                _state.updated = time.time()
                _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
