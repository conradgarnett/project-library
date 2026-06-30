#!/usr/bin/env python3
"""
Open Bloomberg Terminal v2
──────────────────────────
Tabs: Markets · Crypto · World Map · Flights · Ships · Space · Commodities · Weather · Earthquakes · Macro · News

Install:  pip install textual aiohttp yfinance feedparser websockets plotext rich
Run:      python bloomberg_v2.py
"""

import asyncio
import json
import sys
import time
import calendar
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
import feedparser
import aiohttp
from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, TabbedContent, TabPane,
    DataTable, Label, RichLog
)
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.binding import Binding
from textual.reactive import reactive
from textual import work
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich import box

try:
    import plotext as plt
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False

try:
    import websockets as _ws_lib
    HAS_WS = True
except ImportError:
    HAS_WS = False

# ══════════════════════════════════════════════════════════════════════════════
# WATCHLISTS
# ══════════════════════════════════════════════════════════════════════════════

STOCKS = [
    ("^GSPC","S&P 500"),("^DJI","Dow Jones"),("^IXIC","NASDAQ"),("^RUT","Russell 2K"),
    ("^VIX","VIX"),("SPY","SPY"),("QQQ","QQQ"),("IWM","IWM"),
    ("AAPL","Apple"),("MSFT","Microsoft"),("NVDA","NVIDIA"),("GOOGL","Alphabet"),
    ("META","Meta"),("AMZN","Amazon"),("TSLA","Tesla"),("AMD","AMD"),
    ("JPM","JPMorgan"),("BAC","Bank of America"),("GS","Goldman Sachs"),
    ("UNH","UnitedHealth"),("JNJ","J&J"),("XOM","ExxonMobil"),("CVX","Chevron"),
]

CRYPTO_TICKERS = [
    ("BTC-USD","Bitcoin"),("ETH-USD","Ethereum"),("SOL-USD","Solana"),
    ("BNB-USD","BNB"),("XRP-USD","XRP"),("ADA-USD","Cardano"),
    ("DOGE-USD","Dogecoin"),("AVAX-USD","Avalanche"),("LINK-USD","Chainlink"),
]

COMMODITIES = [
    ("GC=F","Gold"),("SI=F","Silver"),("HG=F","Copper"),("CL=F","WTI Crude"),
    ("BZ=F","Brent Crude"),("NG=F","Natural Gas"),("ZC=F","Corn"),("ZW=F","Wheat"),
    ("ZS=F","Soybeans"),("LBS=F","Lumber"),("PL=F","Platinum"),("PA=F","Palladium"),
]

FX = [
    ("EURUSD=X","EUR/USD"),("GBPUSD=X","GBP/USD"),("JPY=X","USD/JPY"),
    ("AUDUSD=X","AUD/USD"),("USDCAD=X","USD/CAD"),("USDCHF=X","USD/CHF"),
    ("USDINR=X","USD/INR"),("USDCNY=X","USD/CNY"),("DX-Y.NYB","USD Index"),
]

BONDS = [
    ("^TNX","US 10Y Treasury"),("^TYX","US 30Y Treasury"),("^FVX","US 5Y Treasury"),
    ("^IRX","US 3M T-Bill"),("TLT","iShares 20Y"),("HYG","High Yield"),
    ("LQD","Invest Grade"),("EMB","EM Bonds"),
]

BINANCE_SYMBOLS = ["btcusdt","ethusdt","solusdt","bnbusdt","xrpusdt","adausdt","dogeusdt","avaxusdt","linkusdt"]
BINANCE_MAP = {s: s.replace("usdt","-USD").upper().replace("-USD","-USD") for s in BINANCE_SYMBOLS}
BINANCE_MAP = {
    "btcusdt":"BTC-USD","ethusdt":"ETH-USD","solusdt":"SOL-USD","bnbusdt":"BNB-USD",
    "xrpusdt":"XRP-USD","adausdt":"ADA-USD","dogeusdt":"DOGE-USD","avaxusdt":"AVAX-USD","linkusdt":"LINK-USD",
}

# Major airports (lat, lon, display name)
AIRPORTS = {
    "JFK":(40.6413,-73.7781,"New York JFK"),
    "LAX":(33.9425,-118.408,"Los Angeles LAX"),
    "ORD":(41.9742,-87.9073,"Chicago O'Hare"),
    "LHR":(51.4700,-0.4543,"London Heathrow"),
    "CDG":(49.0097,2.5479,"Paris CDG"),
    "FRA":(50.0379,8.5622,"Frankfurt"),
    "AMS":(52.3086,4.7639,"Amsterdam"),
    "DXB":(25.2532,55.3657,"Dubai"),
    "SIN":(1.3644,103.9915,"Singapore"),
    "NRT":(35.7647,140.3864,"Tokyo Narita"),
    "SYD":(-33.9399,151.1753,"Sydney"),
    "GRU":(-23.4356,-46.4731,"São Paulo"),
}

WMO = {0:"Clear ☀",1:"Mainly Clear 🌤",2:"Partly Cloudy ⛅",3:"Overcast ☁",
       45:"Fog 🌫",48:"Icy Fog 🌫",51:"Drizzle 🌦",53:"Drizzle 🌧",55:"Heavy Drizzle 🌧",
       61:"Light Rain 🌦",63:"Rain 🌧",65:"Heavy Rain 🌧",
       71:"Light Snow 🌨",73:"Snow ❄",75:"Heavy Snow ❄",
       80:"Showers 🌦",81:"Showers 🌧",82:"Violent Showers ⛈",
       95:"Thunderstorm ⛈",96:"T-Storm+Hail ⛈",99:"T-Storm+Hail ⛈"}

WEATHER_CITIES = {
    "New York":(40.7128,-74.0060),"London":(51.5074,-0.1278),
    "Tokyo":(35.6762,139.6503),"Sydney":(-33.8688,151.2093),
    "Dubai":(25.2048,55.2708),"Singapore":(1.3521,103.8198),
    "Los Angeles":(34.0522,-118.2437),"Chicago":(41.8781,-87.6298),
    "Paris":(48.8566,2.3522),"Frankfurt":(50.1109,8.6821),
    "Moscow":(55.7558,37.6173),"Mumbai":(19.0760,72.8777),
    "São Paulo":(-23.5505,-46.6333),"Hong Kong":(22.3193,114.1694),
    "Seoul":(37.5665,126.9780),
}

SHIP_TYPES = {
    0:"Unknown",20:"WIG",21:"WIG",30:"Fishing",31:"Towing",36:"Sailing",37:"Pleasure",
    40:"High Speed",50:"Pilot",51:"SAR",52:"Tug",53:"Port Tender",60:"Passenger",
    70:"Cargo",71:"Cargo",72:"Cargo",73:"Cargo",80:"Tanker",81:"Tanker",90:"Other",
}

NAV_STATUS = {
    0:"Under Way",1:"At Anchor",2:"Not Under Command",3:"Restricted",
    4:"Draft Constrained",5:"Moored",6:"Aground",7:"Fishing",8:"Sailing",15:"Unknown",
}

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ══════════════════════════════════════════════════════════════════════════════

quotes:         dict = {}   # ticker -> quote dict (stocks, ETFs, crypto)
commodity_q:    dict = {}
fx_q:           dict = {}
bond_q:         dict = {}
aircraft_data:  list = []
ships_data:     list = []
weather_data:   dict = {}
quake_data:     list = []
news_data:      list = []
iss_data:       dict = {}
macro_data:     dict = {}   # indicator -> value
price_history:  dict = {}   # ticker -> [prices]
selected_ticker: str = "^GSPC"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _pct_color(v: float) -> str:
    return "green" if v >= 0 else "red"

def _arrow(v: float) -> str:
    return "▲" if v >= 0 else "▼"

def _fmt_price(v: float, decimals: int = 2) -> str:
    if v is None or v == 0: return "—"
    if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
    if v >= 1_000:     return f"{v:,.{decimals}f}"
    return f"{v:.{decimals}f}"

def _fmt_vol(v) -> str:
    if not v: return "—"
    v = float(v)
    if v >= 1e12: return f"{v/1e12:.2f}T"
    if v >= 1e9:  return f"{v/1e9:.1f}B"
    if v >= 1e6:  return f"{v/1e6:.1f}M"
    if v >= 1e3:  return f"{v/1e3:.0f}K"
    return str(int(v))

def _ship_type_name(t: int) -> str:
    for k in sorted(SHIP_TYPES.keys(), reverse=True):
        if t >= k: return SHIP_TYPES[k]
    return "Unknown"

def _time_ago(dt: datetime) -> str:
    secs = int((datetime.utcnow() - dt.replace(tzinfo=None)).total_seconds())
    if secs < 60:    return f"{secs}s"
    if secs < 3600:  return f"{secs//60}m"
    if secs < 86400: return f"{secs//3600}h"
    return f"{secs//86400}d"

def make_sparkline(prices: list, width: int = 8) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not prices or len(prices) < 2:
        return "─" * width
    step = max(1, len(prices) // width)
    s = [prices[i] for i in range(0, len(prices), step)][:width]
    mn, mx = min(s), max(s)
    if mn == mx: return "─" * len(s)
    return "".join(bars[int((p - mn) / (mx - mn) * 7)] for p in s)

def make_price_chart(prices: list, width: int = 70, height: int = 14, ticker: str = "") -> str:
    if not prices:
        return "  Fetching chart data…"
    if HAS_PLOTEXT:
        try:
            plt.clf()
            plt.plotsize(width, height)
            color = "green" if prices[-1] >= prices[0] else "red"
            plt.plot(list(range(len(prices))), prices, color=color)
            plt.theme("dark")
            plt.canvas_color("black")
            plt.axes_color((12, 22, 40))
            plt.ticks_color("cyan")
            plt.xfrequency(0)
            pct = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] else 0
            plt.title(f"{ticker}  {_arrow(pct)}{abs(pct):.2f}%  today")
            return plt.build()
        except Exception as e:
            return f"  Chart error: {e}"
    # Fallback ASCII chart
    mn, mx = min(prices), max(prices)
    rng = mx - mn or 1
    step = max(1, len(prices) // width)
    cols = prices[::step][:width]
    rows = []
    for r in range(height):
        thresh = mx - (r / (height - 1)) * rng
        line = "".join("▓" if p >= thresh else " " for p in cols)
        rows.append(f"{thresh:>8.2f} │{line}")
    rows.append(f"{'':>8} └{'─'*len(cols)}")
    return "\n".join(rows)

def make_world_map(planes: list, ships: list) -> str:
    if not HAS_PLOTEXT:
        return (f"  Install plotext for world map: pip install plotext\n\n"
                f"  Aircraft tracked: {len(planes)}\n  Ships tracked: {len(ships)}")
    try:
        plt.clf()
        plt.plotsize(112, 38)
        plt.theme("dark")
        plt.canvas_color("black")
        plt.axes_color((10,18,32))
        plt.ticks_color((0,100,180))

        if ships:
            slons = [s["lon"] for s in ships if s.get("lon") is not None and s.get("lat") is not None]
            slats = [s["lat"] for s in ships if s.get("lon") is not None and s.get("lat") is not None]
            if slons:
                plt.scatter(slons, slats, color=(200,180,0), marker="·", label=f"Ships {len(slons)}")

        if planes:
            air = [p for p in planes if not p.get("on_ground") and p.get("lon") is not None]
            if air:
                plons = [p["lon"] for p in air]
                plats = [p["lat"] for p in air]
                plt.scatter(plons, plats, color=(0,210,210), marker="+", label=f"Aircraft {len(air)}")

        plt.xlim(-180, 180)
        plt.ylim(-60, 80)
        plt.title("◉  LIVE WORLD MAP  —  Aircraft + Ships")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        return plt.build()
    except Exception as e:
        return f"  Map error: {e}"

def get_airport_flights(iata: str) -> list:
    """Return the 60 closest aircraft to this airport (no hard radius cutoff)."""
    if not aircraft_data or iata not in AIRPORTS:
        return []
    lat, lon, _ = AIRPORTS[iata]
    def _dist(p):
        if p.get("lat") is None or p.get("lon") is None:
            return 9999.0
        return ((p["lat"] - lat) ** 2 + (p["lon"] - lon) ** 2) ** 0.5
    return sorted(aircraft_data, key=_dist)[:60]


# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHERS (run as background tasks)
# ══════════════════════════════════════════════════════════════════════════════

async def poller_markets(interval: int = 30):
    """Batch-fetch all tickers in one yf.download() call — ~5s instead of ~90s."""
    global quotes
    loop = asyncio.get_event_loop()
    all_pairs  = STOCKS + CRYPTO_TICKERS
    all_syms   = [t for t, _ in all_pairs]
    name_map   = {t: n for t, n in all_pairs}

    while True:
        def _batch_fetch():
            result = {}
            try:
                # Single network call fetches all tickers at once
                df = yf.download(
                    all_syms, period="2d", interval="1d",
                    auto_adjust=True, progress=False,
                    threads=True, group_by="ticker",
                )
                for ticker in all_syms:
                    try:
                        if len(all_syms) == 1:
                            col = df["Close"].dropna()
                        else:
                            col = df[ticker]["Close"].dropna()
                        if col.empty:
                            continue
                        price = float(col.iloc[-1])
                        prev  = float(col.iloc[-2]) if len(col) >= 2 else price
                        chg   = price - prev
                        pct   = (chg / prev * 100) if prev else 0
                        result[ticker] = {
                            "ticker": ticker, "name": name_map.get(ticker, ticker),
                            "price": price, "change": chg, "change_pct": pct,
                            "volume": 0, "day_high": price, "day_low": price,
                            "market_cap": None,
                            "is_crypto": ticker.endswith("-USD"),
                        }
                    except Exception:
                        pass
            except Exception:
                pass
            return result

        try:
            r = await loop.run_in_executor(None, _batch_fetch)
            if r:
                quotes.update(r)
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_commodities(interval: int = 60):
    """Batch-fetch commodities, FX, bonds in one call."""
    global commodity_q, fx_q, bond_q
    loop = asyncio.get_event_loop()
    all_pairs = COMMODITIES + FX + BONDS
    all_syms  = [t for t, _ in all_pairs]
    name_map  = {t: n for t, n in all_pairs}

    while True:
        def _batch_fetch():
            result = {}
            try:
                df = yf.download(
                    all_syms, period="2d", interval="1d",
                    auto_adjust=True, progress=False, threads=True, group_by="ticker",
                )
                for ticker in all_syms:
                    try:
                        col = df[ticker]["Close"].dropna() if len(all_syms) > 1 else df["Close"].dropna()
                        if col.empty: continue
                        price = float(col.iloc[-1])
                        prev  = float(col.iloc[-2]) if len(col) >= 2 else price
                        chg   = price - prev
                        pct   = (chg / prev * 100) if prev else 0
                        result[ticker] = {"ticker":ticker,"name":name_map.get(ticker,ticker),
                                          "price":price,"change":chg,"change_pct":pct}
                    except Exception:
                        pass
            except Exception:
                pass
            return result

        try:
            r = await loop.run_in_executor(None, _batch_fetch)
            if r:
                for ticker, _ in COMMODITIES:
                    if ticker in r: commodity_q[ticker] = r[ticker]
                for ticker, _ in FX:
                    if ticker in r: fx_q[ticker] = r[ticker]
                for ticker, _ in BONDS:
                    if ticker in r: bond_q[ticker] = r[ticker]
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_history(interval: int = 90):
    """Fetch intraday chart history — all tickers in one batch call."""
    global price_history
    loop = asyncio.get_event_loop()
    chart_tickers = [t for t, _ in STOCKS[:10] + CRYPTO_TICKERS[:5]]

    while True:
        def _batch():
            result = {}
            try:
                df = yf.download(
                    chart_tickers, period="1d", interval="5m",
                    auto_adjust=True, progress=False, threads=True, group_by="ticker",
                )
                for t in chart_tickers:
                    try:
                        col = df[t]["Close"].dropna() if len(chart_tickers) > 1 else df["Close"].dropna()
                        if not col.empty:
                            result[t] = col.tolist()
                    except Exception:
                        pass
            except Exception:
                pass
            return result

        try:
            r = await loop.run_in_executor(None, _batch)
            if r:
                price_history.update(r)
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_aircraft(interval: int = 30):
    """
    Multi-region aircraft via airplanes.live (no key, 250nm radius per query).
    Falls back to OpenSky global if all region queries fail.
    """
    global aircraft_data
    # Strategic hub locations — 250nm radius each, covers major flight corridors
    REGIONS = [
        (40.6, -73.8),   # New York
        (33.9, -118.4),  # Los Angeles
        (41.9, -87.9),   # Chicago
        (51.5, -0.5),    # London
        (49.0,  2.5),    # Paris
        (50.0,  8.6),    # Frankfurt
        (35.8, 140.4),   # Tokyo
        ( 1.4, 103.9),   # Singapore
        (25.3,  55.4),   # Dubai
        (-33.9, 151.2),  # Sydney
        (-23.4, -46.5),  # São Paulo
        (55.9,  37.4),   # Moscow
        (19.4, -99.1),   # Mexico City
        (30.2, 120.4),   # Shanghai
    ]

    async def _fetch_region(session, lat, lon):
        try:
            url = f"https://api.airplanes.live/v2/point/{lat}/{lon}/250"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                if r.status == 200:
                    d = await r.json()
                    return d.get("ac", [])
        except Exception:
            pass
        return []

    def _normalize(raw: list) -> list:
        planes = []
        for p in raw:
            alt_raw = p.get("alt_baro", 0)
            on_ground = alt_raw == "ground" or p.get("on_ground", False)
            alt_ft = 0 if on_ground else (int(alt_raw) if isinstance(alt_raw, (int, float)) else 0)
            planes.append({
                "icao24":    p.get("hex", ""),
                "callsign":  (p.get("flight") or p.get("r") or "—").strip() or "—",
                "country":   p.get("r", "")[:2] if p.get("r") else "",
                "lon":       p.get("lon"),
                "lat":       p.get("lat"),
                "altitude":  alt_ft,
                "speed":     int(p.get("gs", 0) or 0),
                "heading":   int(p.get("track", 0) or 0),
                "on_ground": on_ground,
                "vert_rate": p.get("baro_rate"),
                "last_seen": 0,
            })
        return planes

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [_fetch_region(session, lat, lon) for lat, lon in REGIONS]
                results = await asyncio.gather(*tasks)
                seen, planes = set(), []
                for batch in results:
                    for p in batch:
                        h = p.get("hex", "")
                        if h and h not in seen:
                            seen.add(h)
                            planes.append(p)

                if planes:
                    normalized = _normalize(planes)
                    aircraft_data = sorted(normalized, key=lambda x: x["altitude"], reverse=True)
                else:
                    # Fallback: try OpenSky global (slower, often rate-limited)
                    try:
                        async with session.get(
                            "https://opensky-network.org/api/states/all",
                            timeout=aiohttp.ClientTimeout(total=20)
                        ) as resp:
                            if resp.status == 200:
                                raw = await resp.json()
                                fallback = []
                                for s in (raw.get("states") or []):
                                    if len(s) < 11: continue
                                    fallback.append({
                                        "icao24": s[0] or "", "callsign": (s[1] or "").strip() or "—",
                                        "country": s[2] or "", "lon": s[5], "lat": s[6],
                                        "altitude": round(s[7] * 3.28084) if s[7] else 0,
                                        "speed": round(s[9] * 1.94384) if s[9] else 0,
                                        "heading": round(s[10]) if s[10] else 0,
                                        "on_ground": bool(s[8]), "vert_rate": s[11], "last_seen": 0,
                                    })
                                if fallback:
                                    aircraft_data = sorted(fallback, key=lambda x: x["altitude"], reverse=True)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_ships(interval: int = 60):
    """
    Ship tracking via Digitraffic Finnish Maritime Authority AIS API.
    Free, no key required. Returns ~18k vessels (Baltic, North Sea, global via AIS sharing).
    """
    global ships_data
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch positions and metadata concurrently
                pos_task = session.get(
                    "https://meri.digitraffic.fi/api/ais/v1/locations",
                    timeout=aiohttp.ClientTimeout(total=25)
                )
                meta_task = session.get(
                    "https://meri.digitraffic.fi/api/ais/v1/vessels",
                    timeout=aiohttp.ClientTimeout(total=25)
                )
                async with pos_task as pos_resp, meta_task as meta_resp:
                    pos_data = await pos_resp.json() if pos_resp.status == 200 else {}
                    meta_raw = await meta_resp.json() if meta_resp.status == 200 else []

                # Build metadata lookup by MMSI
                meta = {}
                for v in (meta_raw if isinstance(meta_raw, list) else []):
                    mmsi = str(v.get("mmsi", ""))
                    if mmsi:
                        meta[mmsi] = v

                # Parse GeoJSON feature collection
                vessels = []
                for feat in (pos_data.get("features") or []):
                    try:
                        mmsi = str(feat.get("mmsi", ""))
                        coords = feat.get("geometry", {}).get("coordinates", [None, None])
                        props = feat.get("properties", {})
                        lon, lat = coords[0], coords[1]
                        if lon is None or lat is None:
                            continue
                        nav = int(props.get("navStat", 15))
                        spd = float(props.get("sog", 0) or 0)
                        crs = float(props.get("cog", 0) or 0)
                        m = meta.get(mmsi, {})
                        stype = int(m.get("shipType", 0) or 0)
                        vessels.append({
                            "mmsi":        mmsi,
                            "name":        (m.get("name") or f"MMSI {mmsi}")[:30],
                            "flag":        "",
                            "type":        stype,
                            "type_name":   _ship_type_name(stype),
                            "dest":        (m.get("destination") or "")[:20],
                            "length":      int((m.get("referencePointA") or 0) + (m.get("referencePointB") or 0)),
                            "lat":         lat,
                            "lon":         lon,
                            "speed":       spd,
                            "course":      crs,
                            "nav_status":  nav,
                            "status_name": NAV_STATUS.get(nav, "Unknown"),
                        })
                    except Exception:
                        continue

                if vessels:
                    ships_data = sorted(vessels, key=lambda v: v.get("speed", 0), reverse=True)[:500]
        except Exception:
            pass
        await asyncio.sleep(interval)


async def _fetch_one_city(session, city, lat, lon):
    """Fetch weather for a single city — called concurrently."""
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "weather_code,wind_speed_10m,wind_direction_10m,precipitation",
        "timezone": "UTC",
    }
    try:
        async with session.get("https://api.open-meteo.com/v1/forecast",
                               params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                d = await r.json()
                c = d["current"]
                dirs = ["N","NE","E","SE","S","SW","W","NW"]
                return city, {
                    "temp_c":   c["temperature_2m"],
                    "temp_f":   c["temperature_2m"]*9/5+32,
                    "feels_c":  c["apparent_temperature"],
                    "humidity": c["relative_humidity_2m"],
                    "wind":     c["wind_speed_10m"],
                    "wind_dir": dirs[round(c["wind_direction_10m"]/45)%8],
                    "precip":   c["precipitation"],
                    "code":     c["weather_code"],
                    "condition":WMO.get(c["weather_code"],"Unknown"),
                }
    except Exception:
        pass
    return city, None


async def poller_weather(interval: int = 300):
    """All 15 cities fetched in parallel — ~2s instead of ~30s."""
    global weather_data
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [_fetch_one_city(session, city, lat, lon)
                         for city, (lat, lon) in WEATHER_CITIES.items()]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, tuple):
                        city, data = result
                        if data:
                            weather_data[city] = data
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_earthquakes(interval: int = 60):
    global quake_data
    while True:
        for url in [
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        ]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                        if r.status == 200:
                            data = await r.json()
                            qs = []
                            for f in data.get("features",[]):
                                p,g = f["properties"],f["geometry"]["coordinates"]
                                t = datetime.fromtimestamp(p["time"]/1000, tz=timezone.utc)
                                qs.append({
                                    "mag":     float(p.get("mag") or 0),
                                    "place":   p.get("place","Unknown")[:50],
                                    "depth":   g[2],
                                    "lat":g[1],"lon":g[0],
                                    "time":t,
                                    "ago":     _time_ago(t),
                                    "tsunami": bool(p.get("tsunami")),
                                    "alert":   p.get("alert",""),
                                    "felt":    int(p.get("felt") or 0),
                                })
                            quake_data = sorted(qs, key=lambda q:q["mag"], reverse=True)
            except Exception:
                pass
        await asyncio.sleep(interval)


async def poller_news(interval: int = 120):
    """All RSS feeds fetched concurrently in thread executors — parallel, not sequential."""
    global news_data
    FEEDS = [
        ("Reuters",       "https://feeds.reuters.com/reuters/topNews"),
        ("Reuters Mkts",  "https://feeds.reuters.com/reuters/businessNews"),
        ("BBC World",     "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("BBC Business",  "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("CNBC",          "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch",   "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("WSJ Markets",   "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Ars Technica",  "https://feeds.arstechnica.com/arstechnica/index"),
        ("SpaceNews",     "https://spacenews.com/feed/"),
    ]
    loop = asyncio.get_event_loop()

    def _parse_feed(source, url):
        articles = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:7]:
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime.utcfromtimestamp(calendar.timegm(entry.published_parsed))
                articles.append({
                    "source": source,
                    "title":  entry.get("title", "")[:80],
                    "link":   entry.get("link", ""),
                    "ago":    _time_ago(pub) if pub else "?",
                })
        except Exception:
            pass
        return articles

    while True:
        tasks = [loop.run_in_executor(None, _parse_feed, src, url) for src, url in FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for r in results:
            if isinstance(r, list):
                articles.extend(r)
        if articles:
            news_data = articles
        await asyncio.sleep(interval)


async def poller_iss(interval: int = 10):
    """ISS position — tries wheretheiss.at first, falls back to open-notify."""
    global iss_data
    SOURCES = [
        ("https://api.wheretheiss.at/v1/satellites/25544", "wheretheiss"),
        ("http://api.open-notify.org/iss-now.json",        "open-notify"),
    ]
    while True:
        async with aiohttp.ClientSession() as session:
            for url, src in SOURCES:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        if r.status == 200:
                            d = await r.json()
                            if src == "open-notify":
                                pos = d.get("iss_position", {})
                                iss_data = {
                                    "latitude":  float(pos.get("latitude", 0)),
                                    "longitude": float(pos.get("longitude", 0)),
                                    "altitude":  408.0,
                                    "velocity":  27600.0,
                                    "visibility": "",
                                }
                            else:
                                iss_data = d
                            break
                except Exception:
                    continue
        await asyncio.sleep(interval)


async def poller_macro(interval: int = 3600):
    """World Bank open data — no API key required."""
    global macro_data
    indicators = {
        "US GDP Growth":       "https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrv=1",
        "US Inflation":        "https://api.worldbank.org/v2/country/US/indicator/FP.CPI.TOTL.ZG?format=json&mrv=1",
        "US Unemployment":     "https://api.worldbank.org/v2/country/US/indicator/SL.UEM.TOTL.ZS?format=json&mrv=1",
        "EU GDP Growth":       "https://api.worldbank.org/v2/country/EU/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrv=1",
        "China GDP Growth":    "https://api.worldbank.org/v2/country/CN/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrv=1",
        "World GDP Growth":    "https://api.worldbank.org/v2/country/WLD/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrv=1",
        "US Trade Balance":    "https://api.worldbank.org/v2/country/US/indicator/BN.CAB.XOKA.GD.ZS?format=json&mrv=1",
        "Global Inflation":    "https://api.worldbank.org/v2/country/WLD/indicator/FP.CPI.TOTL.ZG?format=json&mrv=1",
    }
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                for name, url in indicators.items():
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                            if r.status == 200:
                                d = await r.json()
                                records = d[1] if len(d) > 1 else []
                                for rec in records:
                                    if rec.get("value") is not None:
                                        macro_data[name] = {
                                            "value": rec["value"],
                                            "year":  rec.get("date",""),
                                            "unit":  "%",
                                        }
                                        break
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(interval)


async def poller_binance():
    """Real-time crypto prices from Binance WebSocket."""
    if not HAS_WS:
        return
    import websockets
    stream = "/".join(f"{s}@ticker" for s in BINANCE_SYMBOLS)
    url = f"wss://stream.binance.com:9443/stream?streams={stream}"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                async for msg in ws:
                    d = json.loads(msg).get("data", {})
                    sym = d.get("s","").lower()
                    if sym not in BINANCE_MAP:
                        continue
                    ticker = BINANCE_MAP[sym]
                    price  = float(d.get("c",0))
                    open_  = float(d.get("o",price))
                    chg    = price - open_
                    pct    = (chg/open_*100) if open_ else 0
                    name   = next((n for t,n in CRYPTO_TICKERS if t==ticker), ticker)
                    quotes[ticker] = {
                        "ticker":ticker,"name":name,"price":price,
                        "change":chg,"change_pct":pct,
                        "volume":float(d.get("v",0)),
                        "day_high":float(d.get("h",0)),
                        "day_low":float(d.get("l",0)),
                        "is_crypto":True,
                    }
        except Exception:
            await asyncio.sleep(5)


# ══════════════════════════════════════════════════════════════════════════════
# UI WIDGETS
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
Screen { background: #0a0e1a; color: #c8d8e8; }
TabbedContent { height: 1fr; }
Tabs { background: #0d1b2a; height: 3; border-bottom: solid #1e3a5f; }
Tab { color: #446688; background: #0d1b2a; }
Tab.-active { color: #00aaff; background: #0a1628; text-style: bold; }
TabPane { background: #0a0e1a; padding: 0; }
DataTable { background: #0a0e1a; height: 1fr; }
DataTable > .datatable--header { background: #0d1b2a; color: #00aaff; text-style: bold; }
DataTable > .datatable--cursor { background: #1e3a5f; }
DataTable > .datatable--even-row { background: #0c1220; }
.section-header { height: 1; background: #0d1b2a; color: #00aaff; text-style: bold; padding: 0 1; border-bottom: solid #1e3a5f; }
.stat-row { height: 1; background: #0d1b2a; color: #88aacc; padding: 0 1; }
RichLog { background: #0a0e1a; height: 1fr; padding: 0 1; }
.chart-area { height: 1fr; background: #0a0e1a; padding: 0 1; }
Horizontal { height: 1fr; }
.panel-left { width: 32; border-right: solid #1e3a5f; }
.panel-right { width: 1fr; }
.panel-mid { width: 1fr; border-right: solid #1e3a5f; }
.split-left { width: 1fr; border-right: solid #1e3a5f; }
.split-right { width: 1fr; }
#status-bar { dock: bottom; height: 1; background: #0d1b2a; color: #446688; }
"""

class SectionHeader(Static):
    DEFAULT_CSS = ".section-header { height: 1; }"
    def __init__(self, text: str, **kw):
        super().__init__(**kw)
        self._text = text
    def on_mount(self):
        self.update(Text(f" ▶ {self._text}", style="bold #00aaff"))

class StatRow(Static):
    DEFAULT_CSS = ".stat-row { height: 1; }"

# ── MARKETS ──────────────────────────────────────────────────────────────────

class MarketsWidget(Container):
    """Yahoo Finance–style layout: Watchlist | Chart | Key Stats."""

    selected: reactive[str] = reactive("^GSPC")

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(classes="panel-left"):
                yield SectionHeader("WATCHLIST")
                yield DataTable(id="watchlist-dt", zebra_stripes=True, cursor_type="row")
            with Vertical(classes="panel-mid"):
                yield SectionHeader("PRICE CHART  (intraday 5m)")
                yield Static(id="price-chart", classes="chart-area")
                yield SectionHeader("KEY STATISTICS")
                yield Static(id="key-stats")
            with Vertical(classes="panel-right"):
                yield SectionHeader("MARKET OVERVIEW")
                yield DataTable(id="market-overview-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        wl = self.query_one("#watchlist-dt", DataTable)
        for col, w in [("","3"),("Ticker","8"),("Price","14"),("Chg %","9"),("Spark","10")]:
            wl.add_column(col, width=int(w))

        ov = self.query_one("#market-overview-dt", DataTable)
        for col, w in [("Ticker","8"),("Name","22"),("Price","14"),("Change","18"),("Vol","10"),("Mkt Cap","12")]:
            ov.add_column(col, width=int(w))

    def refresh_watchlist(self):
        dt = self.query_one("#watchlist-dt", DataTable)
        dt.clear()
        watch_order = [t for t,_ in STOCKS[:12] + CRYPTO_TICKERS[:6]]
        for ticker in watch_order:
            q = quotes.get(ticker)
            if not q:
                continue
            color = _pct_color(q["change_pct"])
            arrow = _arrow(q["change_pct"])
            spark = make_sparkline(price_history.get(ticker, []), width=8)
            indicator = Text("●", style=color)
            dt.add_row(
                indicator,
                Text(ticker.replace("^","").replace("-USD","").replace("=X","")[:7], style="bold"),
                Text(f"{_fmt_price(q['price'])}", style="bold"),
                Text(f"{arrow}{abs(q['change_pct']):.1f}%", style=color),
                Text(spark, style=color),
                key=ticker,
            )

    def refresh_chart(self):
        ticker = self.selected
        prices = price_history.get(ticker, [])
        q = quotes.get(ticker)
        chart_w = self.query_one("#price-chart", Static)
        chart_w.update(Text.from_ansi(make_price_chart(prices, width=68, height=13, ticker=ticker)))

        stats_w = self.query_one("#key-stats", Static)
        if q:
            t = Text()
            t.append(f" {q['name']}  ", style="bold #00aaff")
            t.append(f"${_fmt_price(q['price'])}  ", style=f"bold {_pct_color(q['change_pct'])}")
            t.append(f"{_arrow(q['change_pct'])}{abs(q['change']):.2f}  ", style=_pct_color(q['change_pct']))
            t.append(f"({_arrow(q['change_pct'])}{abs(q['change_pct']):.2f}%)  ", style=_pct_color(q['change_pct']))
            t.append(f"  H:{_fmt_price(q['day_high'])}  L:{_fmt_price(q['day_low'])}  ", style="dim")
            t.append(f"Vol:{_fmt_vol(q.get('volume',0))}  ", style="dim")
            if q.get("market_cap"): t.append(f"Cap:{_fmt_vol(q['market_cap'])}", style="dim")
            stats_w.update(t)

    def refresh_overview(self):
        dt = self.query_one("#market-overview-dt", DataTable)
        dt.clear()
        all_q = [q for q in quotes.values() if q.get("price",0) > 0]
        all_q.sort(key=lambda q: abs(q.get("change_pct",0)), reverse=True)
        for q in all_q[:30]:
            color = _pct_color(q["change_pct"])
            arrow = _arrow(q["change_pct"])
            dt.add_row(
                Text(q["ticker"].replace("^","").replace("-USD","")[:7], style="bold"),
                Text(q["name"][:21], style="dim"),
                Text(_fmt_price(q["price"]), style="bold"),
                Text(f"{arrow}{abs(q['change']):.2f} ({arrow}{abs(q['change_pct']):.2f}%)", style=color),
                Text(_fmt_vol(q.get("volume",0)), style="dim"),
                Text(_fmt_vol(q.get("market_cap")) if q.get("market_cap") else "—", style="dim"),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "watchlist-dt" and event.row_key:
            self.selected = str(event.row_key.value)
            self.refresh_chart()

# ── CRYPTO ───────────────────────────────────────────────────────────────────

class CryptoWidget(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("CRYPTOCURRENCY  ·  Binance Real-Time WebSocket")
        yield DataTable(id="crypto-dt", zebra_stripes=True, cursor_type="row")
        yield SectionHeader("DEFI / ALTCOINS  ·  Yahoo Finance")
        yield DataTable(id="altcoin-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        for tid in ("crypto-dt","altcoin-dt"):
            dt = self.query_one(f"#{tid}", DataTable)
            for col, w in [("Coin","10"),("Name","16"),("Price $","18"),
                           ("24h Change","22"),("24h High","14"),("24h Low","14"),
                           ("Volume","16"),("Mkt Cap","14")]:
                dt.add_column(col, width=int(w))

    def draw(self):
        dt = self.query_one("#crypto-dt", DataTable)
        dt.clear()
        top = ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD"]
        for ticker in top:
            q = quotes.get(ticker)
            if not q: continue
            color = _pct_color(q["change_pct"])
            arr = _arrow(q["change_pct"])
            dt.add_row(
                Text(ticker.replace("-USD",""), style="bold #00d4aa"),
                Text(q["name"], style="dim"),
                Text(f"${q['price']:,.2f}", style="bold"),
                Text(f"{arr}{abs(q['change_pct']):.2f}%  ${abs(q['change']):,.2f}", style=color),
                Text(f"${_fmt_price(q.get('day_high',0))}", style="dim"),
                Text(f"${_fmt_price(q.get('day_low',0))}", style="dim"),
                Text(_fmt_vol(q.get("volume",0)), style="dim"),
                Text(_fmt_vol(q.get("market_cap")) if q.get("market_cap") else "—", style="dim"),
            )

        dt2 = self.query_one("#altcoin-dt", DataTable)
        dt2.clear()
        rest = ["ADA-USD","DOGE-USD","AVAX-USD","LINK-USD"]
        for ticker in rest:
            q = quotes.get(ticker)
            if not q: continue
            color = _pct_color(q["change_pct"])
            arr = _arrow(q["change_pct"])
            dt2.add_row(
                Text(ticker.replace("-USD",""), style="bold #00d4aa"),
                Text(q["name"], style="dim"),
                Text(f"${q['price']:,.4f}" if q["price"] < 1 else f"${q['price']:,.2f}", style="bold"),
                Text(f"{arr}{abs(q['change_pct']):.2f}%  ${abs(q['change']):,.4f}", style=color),
                Text(f"${_fmt_price(q.get('day_high',0))}", style="dim"),
                Text(f"${_fmt_price(q.get('day_low',0))}", style="dim"),
                Text(_fmt_vol(q.get("volume",0)), style="dim"),
                Text(_fmt_vol(q.get("market_cap")) if q.get("market_cap") else "—", style="dim"),
            )

# ── WORLD MAP ────────────────────────────────────────────────────────────────

class WorldMapWidget(Container):
    def compose(self) -> ComposeResult:
        yield StatRow(id="map-stats")
        yield Static(id="world-map-render", classes="chart-area")

    def draw(self):
        stats = self.query_one("#map-stats", StatRow)
        airborne = sum(1 for p in aircraft_data if not p.get("on_ground"))
        underway = sum(1 for s in ships_data if s.get("nav_status",15) == 0)
        t = Text()
        t.append(f" ✈ Aircraft: ", style="dim"); t.append(str(len(aircraft_data)), style="bold #00aaff")
        t.append(f"  Airborne: ", style="dim");  t.append(str(airborne), style="bold green")
        t.append(f"  ⚓ Ships: ", style="dim");   t.append(str(len(ships_data)), style="bold #00aaff")
        t.append(f"  Under Way: ", style="dim");  t.append(str(underway), style="bold green")
        t.append(f"  {datetime.utcnow().strftime('%H:%M:%S')} UTC", style="dim")
        stats.update(t)

        map_w = self.query_one("#world-map-render", Static)
        map_w.update(Text.from_ansi(make_world_map(aircraft_data, ships_data)))

# ── FLIGHTS ──────────────────────────────────────────────────────────────────

class FlightsWidget(Container):
    _airport: reactive[str] = reactive("JFK")

    def compose(self) -> ComposeResult:
        yield StatRow(id="flights-stats")
        yield SectionHeader("LIVE FLIGHTS BY AIRPORT  (OpenSky — click airport to filter)")
        with Horizontal():
            with Vertical(classes="panel-left"):
                yield SectionHeader("AIRPORTS")
                yield DataTable(id="airport-dt", cursor_type="row")
            with Vertical(classes="panel-right"):
                yield SectionHeader("FLIGHTS  (within ~220km radius)")
                yield DataTable(id="flights-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        ap = self.query_one("#airport-dt", DataTable)
        ap.add_column("IATA", width=6)
        ap.add_column("Airport", width=22)
        ap.add_column("Region", width=12)
        for iata, (lat,lon,name) in AIRPORTS.items():
            region = "US" if lon < -50 else ("EU" if lon < 40 else "Asia/ME")
            ap.add_row(Text(iata, style="bold #00d4aa"), name[:21], region, key=iata)

        fl = self.query_one("#flights-dt", DataTable)
        for col, w in [("Callsign","10"),("Country","14"),("Alt ft","9"),("Spd kts","8"),
                       ("Hdg°","6"),("FL","6"),("Status","10")]:
            fl.add_column(col, width=int(w))

    def draw(self):
        stats = self.query_one("#flights-stats", StatRow)
        _, _, ap_name = AIRPORTS.get(self._airport, (0,0,"Unknown"))
        flights = get_airport_flights(self._airport)
        t = Text()
        t.append(f" Airport: ", style="dim")
        t.append(f"{self._airport} — {ap_name}", style="bold #00aaff")
        t.append(f"  Flights near: ", style="dim")
        t.append(str(len(flights)), style="bold green")
        t.append(f"  Total tracked: ", style="dim")
        t.append(str(len(aircraft_data)), style="#00aaff")
        stats.update(t)

        fl = self.query_one("#flights-dt", DataTable)
        fl.clear()
        dirs = ["↑","↗","→","↘","↓","↙","←","↖"]
        for p in flights:
            status = "Ground" if p.get("on_ground") else "Airborne"
            color  = "dim" if p.get("on_ground") else "green"
            fl_str = f"FL{p['altitude']//100:03d}" if p["altitude"] and not p.get("on_ground") else "GND"
            hdg_arrow = dirs[round(p["heading"]/45)%8] if p.get("heading") else "·"
            fl.add_row(
                Text(p["callsign"], style="bold #00d4aa"),
                Text(p["country"][:13], style="dim"),
                Text(f"{p['altitude']:,}" if p["altitude"] else "—", style=color),
                Text(str(p["speed"]) if p["speed"] else "—", style=color),
                Text(f"{hdg_arrow} {p['heading']}°" if p.get("heading") else "—", style="dim"),
                Text(fl_str, style="bold" if not p.get("on_ground") else "dim"),
                Text(status, style=color),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "airport-dt" and event.row_key:
            self._airport = str(event.row_key.value)
            self.draw()

# ── SHIPS ────────────────────────────────────────────────────────────────────

class ShipsWidget(Container):
    def compose(self) -> ComposeResult:
        yield StatRow(id="ships-stats")
        yield SectionHeader("VESSEL TRAFFIC  (AIS — Norwegian Coastal Authority / Public AIS)")
        yield DataTable(id="ships-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        dt = self.query_one("#ships-dt", DataTable)
        for col, w in [("MMSI","11"),("Name","20"),("Flag","5"),("Type","12"),
                       ("Lat","8"),("Lon","9"),("Speed kts","10"),("Course","7"),
                       ("Status","22"),("Destination","18")]:
            dt.add_column(col, width=int(w))

    def draw(self):
        stats = self.query_one("#ships-stats", StatRow)
        underway = sum(1 for s in ships_data if s.get("nav_status",15) == 0)
        anchored = sum(1 for s in ships_data if s.get("nav_status",15) == 1)
        t = Text()
        t.append(f" ⚓ Vessels: ", style="dim"); t.append(str(len(ships_data)), style="bold #00aaff")
        t.append(f"  Under Way: ", style="dim"); t.append(str(underway), style="bold green")
        t.append(f"  Anchored: ", style="dim");  t.append(str(anchored), style="yellow")
        if not ships_data:
            t.append("  [fetching AIS — kystverket.no or public TCP stream…]", style="dim")
        stats.update(t)

        dt = self.query_one("#ships-dt", DataTable)
        dt.clear()
        dirs = ["↑","↗","→","↘","↓","↙","←","↖"]
        for v in ships_data[:200]:
            color = "green" if v.get("nav_status",15) == 0 else "dim"
            crs_arrow = dirs[round((v.get("course",0))/45)%8]
            dt.add_row(
                Text(v["mmsi"], style="dim"),
                Text(v["name"][:19], style="bold #00d4aa"),
                Text(v.get("flag","")[:4], style="dim"),
                Text(v["type_name"][:11], style="dim"),
                Text(f"{v['lat']:.3f}" if v.get("lat") else "—", style="dim"),
                Text(f"{v['lon']:.3f}" if v.get("lon") else "—", style="dim"),
                Text(f"{v['speed']:.1f}" if v.get("speed") is not None else "—", style=color),
                Text(f"{crs_arrow} {int(v.get('course',0))}°", style="dim"),
                Text(v["status_name"][:21], style=color),
                Text(v.get("dest","")[:17], style="dim"),
            )

# ── SPACE ────────────────────────────────────────────────────────────────────

class SpaceWidget(Container):
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(id="iss-card")
            yield Static(id="iss-map")
        yield SectionHeader("TRACKED SATELLITES  (AMSAT TLE catalog)")
        yield DataTable(id="space-dt", zebra_stripes=True, cursor_type="row")

    async def on_mount(self):
        dt = self.query_one("#space-dt", DataTable)
        for col, w in [("Object","24"),("NORAD","7"),("Orbit","5"),
                       ("Inc°","7"),("Apogee km","10"),("Perigee km","10"),("Period","8")]:
            dt.add_column(col, width=int(w))
        asyncio.create_task(self._load_sats())

    async def _load_sats(self):
        """Fetch TLE data from AMSAT (works, no auth required)."""
        TLE_SOURCES = [
            "https://www.amsat.org/tle/current/nasabare.txt",
            "http://www.celestrak.com/pub/TLE/visual.txt",   # HTTP fallback
        ]
        for url in TLE_SOURCES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                        if r.status != 200:
                            continue
                        text = await r.text()
                        lines = [l.strip() for l in text.splitlines() if l.strip()]
                        dt = self.query_one("#space-dt", DataTable)
                        i = 0
                        while i < len(lines) - 2:
                            name, l1, l2 = lines[i], lines[i+1], lines[i+2]
                            if l1.startswith("1 ") and l2.startswith("2 ") and len(l1) >= 69:
                                try:
                                    norad = l1[2:7].strip()
                                    inc   = float(l2[8:16].strip())
                                    ecc   = float("0." + l2[26:33].strip())
                                    mm    = float(l2[52:63].strip())
                                    per   = 1440.0 / mm
                                    a     = 331.25 * per ** (2/3)
                                    apo   = a * (1 + ecc) - 6371
                                    peri  = a * (1 - ecc) - 6371
                                    orbit = "LEO" if apo < 2000 else "MEO" if apo < 35000 else "GEO"
                                    orbit_color = {"LEO": "cyan", "MEO": "blue", "GEO": "green"}.get(orbit, "dim")
                                    dt.add_row(
                                        Text(name[:23], style="#00d4aa"),
                                        Text(norad, style="dim"),
                                        Text(orbit, style=orbit_color),
                                        Text(f"{inc:.1f}", style="dim"),
                                        Text(f"{apo:,.0f}", style="dim"),
                                        Text(f"{peri:,.0f}", style="dim"),
                                        Text(f"{per:.1f}m", style="dim"),
                                    )
                                    i += 3
                                    continue
                                except Exception:
                                    pass
                            i += 1
                        return  # success, stop trying sources
            except Exception:
                continue

    def draw(self):
        iss_card = self.query_one("#iss-card", Static)
        if iss_data:
            d = iss_data
            lat = d.get("latitude", 0)
            lon = d.get("longitude", 0)
            alt = d.get("altitude", 0)
            vel = d.get("velocity", 0)
            vis = d.get("visibility","")
            t = Text()
            t.append(" ◉ INTERNATIONAL SPACE STATION\n", style="bold #00aaff")
            t.append(f" Lat: {lat:+.4f}°  Lon: {lon:+.4f}°\n", style="#00d4aa")
            t.append(f" Alt: {alt:.1f} km  ({alt*0.621:.1f} mi)\n", style="#c8d8e8")
            t.append(f" Vel: {vel/3600:.2f} km/s  ({vel:.0f} km/h)\n", style="#c8d8e8")
            t.append(f" Visibility: {vis}\n", style="dim")
            t.append(f" Orbital period: ~92 min\n", style="dim")
            iss_card.update(t)

            # Mini ASCII path indicator
            iss_map = self.query_one("#iss-map", Static)
            if HAS_PLOTEXT:
                try:
                    plt.clf()
                    plt.plotsize(60, 12)
                    plt.theme("dark")
                    plt.scatter([lon], [lat], color="green", marker="★")
                    plt.xlim(-180,180); plt.ylim(-60,80)
                    plt.title("ISS Current Position")
                    iss_map.update(Text.from_ansi(plt.build()))
                except Exception:
                    pass

# ── COMMODITIES & FX ────────────────────────────────────────────────────────

class CommoditiesWidget(Container):
    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(classes="split-left"):
                yield SectionHeader("COMMODITIES  (NYMEX / COMEX futures)")
                yield DataTable(id="comm-dt", zebra_stripes=True, cursor_type="row")
            with Vertical():
                yield SectionHeader("FX — CURRENCY CROSSES")
                yield DataTable(id="fx-dt", zebra_stripes=True, cursor_type="row")
        yield SectionHeader("BONDS & FIXED INCOME")
        yield DataTable(id="bond-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        for tid in ("comm-dt","fx-dt","bond-dt"):
            dt = self.query_one(f"#{tid}", DataTable)
            for col, w in [("Symbol","8"),("Name","20"),("Price","14"),("Change","20")]:
                dt.add_column(col, width=int(w))

    def draw(self):
        for tid, src in [("comm-dt",commodity_q),("fx-dt",fx_q),("bond-dt",bond_q)]:
            dt = self.query_one(f"#{tid}", DataTable)
            dt.clear()
            for ticker, q in src.items():
                color = _pct_color(q["change_pct"])
                arr   = _arrow(q["change_pct"])
                dt.add_row(
                    Text(ticker.replace("=F","").replace("=X","")[:7], style="bold"),
                    Text(q["name"][:19], style="dim"),
                    Text(_fmt_price(q["price"]), style="bold"),
                    Text(f"{arr}{abs(q['change']):.4f}  ({arr}{abs(q['change_pct']):.2f}%)", style=color),
                )

# ── WEATHER ──────────────────────────────────────────────────────────────────

class WeatherWidget(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("GLOBAL WEATHER  (Open-Meteo — no API key)")
        yield DataTable(id="weather-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        dt = self.query_one("#weather-dt", DataTable)
        for col, w in [("City","16"),("Condition","26"),("Temp °C","9"),("Feels °C","9"),
                       ("Temp °F","9"),("Humidity","10"),("Wind km/h","10"),("Dir","5"),("Precip mm","10")]:
            dt.add_column(col, width=int(w))

    def draw(self):
        dt = self.query_one("#weather-dt", DataTable)
        dt.clear()
        for city, w in sorted(weather_data.items()):
            dt.add_row(
                Text(city, style="bold"),
                Text(w["condition"][:25], style=""),
                Text(f"{w['temp_c']:.1f}", style="red bold" if abs(w["temp_c"]) >= 35 else ""),
                Text(f"{w['feels_c']:.1f}", style="dim"),
                Text(f"{w['temp_f']:.1f}", style="dim"),
                Text(f"{w['humidity']:.0f}%", style="cyan" if w["humidity"]>80 else "dim"),
                Text(f"{w['wind']:.0f}", style="red" if w["wind"]>50 else "dim"),
                Text(w["wind_dir"], style="dim"),
                Text(f"{w['precip']:.1f}", style="cyan" if w["precip"]>0 else "dim"),
            )

# ── EARTHQUAKES ──────────────────────────────────────────────────────────────

class EarthquakesWidget(Container):
    def compose(self) -> ComposeResult:
        yield StatRow(id="eq-stats")
        yield SectionHeader("SIGNIFICANT (TODAY — sorted by magnitude)")
        yield DataTable(id="eq-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self):
        dt = self.query_one("#eq-dt", DataTable)
        for col, w in [("Mag","8"),("Location","44"),("Depth km","10"),
                       ("Lat","8"),("Lon","9"),("When","8"),("Tsunami","9"),("Alert","8"),("Felt","6")]:
            dt.add_column(col, width=int(w))

    def draw(self):
        stats = self.query_one("#eq-stats", StatRow)
        biggest = quake_data[0] if quake_data else None
        t = Text()
        t.append(f" Earthquakes today: ", style="dim"); t.append(str(len(quake_data)), style="bold #00aaff")
        if biggest:
            mc = "red" if biggest["mag"]>=6 else "yellow" if biggest["mag"]>=5 else "cyan"
            t.append(f"  Largest: ", style="dim"); t.append(f"M{biggest['mag']:.1f}", style=f"bold {mc}")
            t.append(f" — {biggest['place']}", style="")
        stats.update(t)

        dt = self.query_one("#eq-dt", DataTable)
        dt.clear()
        for q in quake_data[:40]:
            mag = q["mag"]
            mc  = "red bold" if mag>=7 else "red" if mag>=6 else "yellow" if mag>=5 else "cyan" if mag>=4 else "dim"
            dt.add_row(
                Text(f"M{mag:.1f}", style=mc),
                Text(q["place"][:43], style=""),
                Text(f"{q['depth']:.1f}", style="dim"),
                Text(f"{q['lat']:.2f}", style="dim"),
                Text(f"{q['lon']:.2f}", style="dim"),
                Text(q.get("ago","?"), style="dim"),
                Text("⚠ YES" if q["tsunami"] else "No", style="red bold" if q["tsunami"] else "dim"),
                Text(q.get("alert","") or "—", style="red" if q.get("alert")=="red" else "yellow" if q.get("alert")=="orange" else "dim"),
                Text(str(q["felt"]) if q["felt"] else "—", style="dim"),
            )

# ── MACRO ────────────────────────────────────────────────────────────────────

class MacroWidget(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("MACRO ECONOMIC INDICATORS  (World Bank open data — no API key)")
        yield DataTable(id="macro-dt", zebra_stripes=True, cursor_type="row")
        yield SectionHeader("MARKET BREADTH  (derived from live quotes)")
        yield Static(id="breadth-stats")

    def on_mount(self):
        dt = self.query_one("#macro-dt", DataTable)
        for col, w in [("Indicator","36"),("Value","12"),("Unit","8"),("Year","6")]:
            dt.add_column(col, width=int(w))

    def draw(self):
        dt = self.query_one("#macro-dt", DataTable)
        dt.clear()
        for name, info in macro_data.items():
            v = info["value"]
            color = "green" if v and v > 0 else "red" if v and v < 0 else "dim"
            dt.add_row(
                Text(name, style=""),
                Text(f"{v:.2f}" if v is not None else "—", style=f"bold {color}"),
                Text(info.get("unit",""), style="dim"),
                Text(info.get("year",""), style="dim"),
            )
        if not macro_data:
            dt.add_row("Loading World Bank data…", "—", "%", "")

        # Market breadth
        bw = self.query_one("#breadth-stats", Static)
        all_q = [q for q in quotes.values() if q.get("price",0) > 0]
        up   = sum(1 for q in all_q if q["change_pct"] > 0)
        down = sum(1 for q in all_q if q["change_pct"] < 0)
        flat = len(all_q) - up - down
        t = Text()
        t.append(f"\n  Advancing: ", style="dim"); t.append(str(up), style="bold green")
        t.append(f"   Declining: ", style="dim"); t.append(str(down), style="bold red")
        t.append(f"   Unchanged: ", style="dim"); t.append(str(flat), style="bold dim")
        if all_q:
            avg_chg = sum(q["change_pct"] for q in all_q) / len(all_q)
            t.append(f"\n  Avg Change: ", style="dim")
            t.append(f"{_arrow(avg_chg)}{abs(avg_chg):.2f}%", style=_pct_color(avg_chg))
        bw.update(t)

# ── NEWS ─────────────────────────────────────────────────────────────────────

class NewsWidget(Container):
    def compose(self) -> ComposeResult:
        yield StatRow(id="news-stats")
        yield RichLog(id="news-log", wrap=True, markup=False, highlight=False, auto_scroll=False)

    def draw(self):
        stats = self.query_one("#news-stats", StatRow)
        stats.update(Text(f" Articles: {len(news_data)}  "
                          f"Updated: {datetime.utcnow().strftime('%H:%M:%S')} UTC", style="dim"))
        log = self.query_one("#news-log", RichLog)
        log.clear()
        src_order = ["Reuters","Reuters Mkts","BBC World","BBC Business","CNBC","MarketWatch","WSJ Markets","Ars Technica","SpaceNews"]
        for src in src_order:
            articles = [a for a in news_data if a["source"] == src]
            if not articles:
                continue
            log.write(Text(f"\n── {src.upper()} {'─'*50}", style="bold #00aaff"))
            for a in articles[:6]:
                t = Text()
                t.append(f"  [{a['ago']:>3}] ", style="dim")
                t.append(a["title"], style="bold")
                log.write(t)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

class BloombergApp(App):
    CSS = CSS
    TITLE = "Open Bloomberg Terminal v2"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "force_refresh", "Refresh"),
        Binding("1","switch_tab('markets')","Markets"),
        Binding("2","switch_tab('crypto')","Crypto"),
        Binding("3","switch_tab('world')","World Map"),
        Binding("4","switch_tab('flights')","Flights"),
        Binding("5","switch_tab('ships')","Ships"),
        Binding("6","switch_tab('space')","Space"),
        Binding("7","switch_tab('commodities')","Commodities"),
        Binding("8","switch_tab('weather')","Weather"),
        Binding("9","switch_tab('quakes')","Earthquakes"),
        Binding("0","switch_tab('macro')","Macro"),
        Binding("n","switch_tab('news')","News"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="markets", id="tabs"):
            with TabPane("◈ Markets",    id="markets"):    yield MarketsWidget(id="w-markets")
            with TabPane("₿ Crypto",     id="crypto"):     yield CryptoWidget(id="w-crypto")
            with TabPane("🌍 World Map",  id="world"):      yield WorldMapWidget(id="w-world")
            with TabPane("✈ Flights",    id="flights"):    yield FlightsWidget(id="w-flights")
            with TabPane("⚓ Ships",     id="ships"):      yield ShipsWidget(id="w-ships")
            with TabPane("🛰 Space",     id="space"):      yield SpaceWidget(id="w-space")
            with TabPane("📊 Commod/FX", id="commodities"):yield CommoditiesWidget(id="w-commod")
            with TabPane("🌦 Weather",   id="weather"):    yield WeatherWidget(id="w-weather")
            with TabPane("🌍 Quakes",    id="quakes"):     yield EarthquakesWidget(id="w-quakes")
            with TabPane("📈 Macro",     id="macro"):      yield MacroWidget(id="w-macro")
            with TabPane("📰 News",      id="news"):       yield NewsWidget(id="w-news")
        yield Static(
            " Q:quit  R:refresh  1-9,0,N: switch panel  Tab: next  "
            "│ Markets·Crypto·WorldMap·Flights·Ships·Space·Commod·Weather·Quakes·Macro·News",
            id="status-bar"
        )

    async def on_mount(self) -> None:
        self.set_interval(5, self._repaint)
        self.set_interval(1, self._update_header)
        # Use asyncio.create_task so infinite async loops run properly
        for coro in [
            poller_markets(30),
            poller_commodities(60),
            poller_history(90),
            poller_aircraft(15),
            poller_ships(30),
            poller_weather(300),
            poller_earthquakes(60),
            poller_news(120),
            poller_iss(10),
            poller_macro(3600),
            poller_binance(),
        ]:
            asyncio.create_task(coro)

    def _update_header(self):
        # Update app subtitle with live ticker info
        btc = quotes.get("BTC-USD")
        spy = quotes.get("SPY")
        parts = []
        if spy:
            parts.append(f"SPY {_arrow(spy['change_pct'])}{spy['price']:.0f} ({spy['change_pct']:+.1f}%)")
        if btc:
            parts.append(f"BTC {_arrow(btc['change_pct'])}${btc['price']:,.0f} ({btc['change_pct']:+.1f}%)")
        parts.append(f"✈{len(aircraft_data)} ⚓{len(ships_data)}")
        self.sub_title = "  ·  ".join(parts)

    def _repaint(self):
        try:
            tabs = self.query_one("#tabs", TabbedContent)
            active = tabs.active
        except Exception:
            return
        try:
            if active == "markets":
                w = self.query_one("#w-markets", MarketsWidget)
                w.refresh_watchlist(); w.refresh_chart(); w.refresh_overview()
            elif active == "crypto":
                self.query_one("#w-crypto", CryptoWidget).draw()
            elif active == "world":
                self.query_one("#w-world", WorldMapWidget).draw()
            elif active == "flights":
                self.query_one("#w-flights", FlightsWidget).draw()
            elif active == "ships":
                self.query_one("#w-ships", ShipsWidget).draw()
            elif active == "space":
                self.query_one("#w-space", SpaceWidget).draw()
            elif active == "commodities":
                self.query_one("#w-commod", CommoditiesWidget).draw()
            elif active == "weather":
                self.query_one("#w-weather", WeatherWidget).draw()
            elif active == "quakes":
                self.query_one("#w-quakes", EarthquakesWidget).draw()
            elif active == "macro":
                self.query_one("#w-macro", MacroWidget).draw()
            elif active == "news":
                self.query_one("#w-news", NewsWidget).draw()
        except Exception:
            pass

    def action_force_refresh(self):
        asyncio.create_task(poller_aircraft(15))
        asyncio.create_task(poller_markets(30))
        self.notify("Refreshing all feeds…", title="Bloomberg")

    def action_switch_tab(self, tab_id: str):
        try:
            self.query_one("#tabs", TabbedContent).active = tab_id
        except Exception:
            pass


if __name__ == "__main__":
    BloombergApp().run()
