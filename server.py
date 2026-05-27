#!/usr/bin/env python3
"""
Open Bloomberg Terminal — FastAPI backend
Serves all data feeds as REST JSON + WebSocket live stream.

Run:
    python server.py
    # then open http://localhost:8000 in a browser
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))
from feeds import aircraft, ships, space, weather, earthquakes, news, parking
from feeds import market, crypto
from feeds import bonds, forex, fred, cve, launches, space_weather, wildfires, cameras
from feeds import conflicts, sanctions, population, options_flow, outages

# ── refresh intervals ────────────────────────────────────────────────────────
REFRESH_MARKET        = 30
REFRESH_AIRCRAFT      = 15
REFRESH_SHIPS         = 30
REFRESH_SPACE         = 60
REFRESH_WEATHER       = 300
REFRESH_EQ            = 60
REFRESH_NEWS          = 120
REFRESH_BONDS         = 3600
REFRESH_FOREX         = 60
REFRESH_FRED          = 3600
REFRESH_CVE           = 900
REFRESH_LAUNCHES      = 1800
REFRESH_SPACE_WEATHER = 300
REFRESH_WILDFIRES     = 10800
REFRESH_PARKING       = 300
REFRESH_CAMERAS       = 300
REFRESH_CONFLICTS     = 900
REFRESH_SANCTIONS     = 86400
REFRESH_POPULATION    = 86400
REFRESH_OPTIONS_FLOW  = 900
REFRESH_OUTAGES       = 300

# ── WebSocket connection manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws) if hasattr(self.active, "discard") else (
            self.active.remove(ws) if ws in self.active else None
        )

    async def broadcast(self, event: str, data: dict):
        msg = json.dumps({"event": event, "data": data, "ts": time.time()})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)


mgr = ConnectionManager()

# ── serialisers ──────────────────────────────────────────────────────────────

def _ser_quote(q) -> dict:
    return {
        "ticker": q.ticker, "name": q.name,
        "price": q.price, "change": q.change, "change_pct": q.change_pct,
        "volume": q.volume, "day_high": q.day_high, "day_low": q.day_low,
        "arrow": q.arrow, "color": q.color,
    }


def _ser_crypto(t) -> dict:
    return {
        "symbol": t.symbol, "name": t.name,
        "price": t.price, "change_24h": t.change_24h,
        "change_pct_24h": t.change_pct_24h,
        "volume_24h": t.volume_24h, "high_24h": t.high_24h, "low_24h": t.low_24h,
        "color": t.color, "arrow": t.arrow,
    }


def _ser_aircraft(p) -> dict:
    return {
        "icao24": p.icao24, "callsign": p.callsign,
        "country": p.origin_country,
        "lat": p.latitude, "lon": p.longitude,
        "altitude_ft": p.altitude_ft, "speed_kts": p.speed_kts,
        "heading": p.heading, "heading_arrow": p.heading_arrow,
        "fl": p.fl, "on_ground": p.on_ground,
        "vertical_rate": p.vertical_rate,
    }


def _ser_vessel(v) -> dict:
    return {
        "mmsi": v.mmsi, "name": v.name, "callsign": v.callsign,
        "vessel_type": v.vessel_type, "type_name": v.type_name,
        "lat": v.lat, "lon": v.lon,
        "speed_kts": v.speed_kts, "course": v.course,
        "heading": v.heading, "heading_arrow": v.heading_arrow,
        "nav_status": v.nav_status, "status_name": v.status_name,
        "destination": v.destination, "flag": v.flag,
    }


def _ser_station(s) -> dict | None:
    if not s:
        return None
    return {
        "name": s.name, "norad_id": s.norad_id,
        "lat": s.lat, "lon": s.lon,
        "altitude_km": s.altitude_km, "velocity_kms": s.velocity_kms,
        "visibility": s.visibility, "ground_track": s.ground_track,
        "altitude_mi": s.altitude_mi,
    }


def _ser_tle(o) -> dict:
    return {
        "name": o.name, "norad_id": o.norad_id,
        "orbit_type": o.orbit_type, "inclination": o.inclination,
        "apogee_km": o.apogee_km, "perigee_km": o.perigee_km,
        "period_min": o.period_min, "eccentricity": o.eccentricity,
    }


def _ser_weather(w) -> dict:
    return {
        "city": w.city, "lat": w.lat, "lon": w.lon,
        "temp_c": w.temp_c, "temp_f": w.temp_f,
        "feels_like_c": w.feels_like_c, "humidity": w.humidity,
        "wind_speed_kph": w.wind_speed_kph, "wind_dir": w.wind_dir,
        "wind_direction_str": w.wind_direction_str,
        "precipitation_mm": w.precipitation_mm,
        "weather_code": w.weather_code,
        "condition": w.condition, "icon": w.icon, "is_day": w.is_day,
    }


def _ser_quake(q) -> dict:
    return {
        "event_id": q.event_id,
        "magnitude": q.magnitude, "magnitude_str": q.magnitude_str,
        "mag_type": q.mag_type, "place": q.place,
        "lat": q.lat, "lon": q.lon, "depth_km": q.depth_km,
        "time_utc": q.time_utc.isoformat(),
        "time_ago": q.time_ago,
        "felt": q.felt, "alert": q.alert,
        "tsunami": q.tsunami, "sig": q.sig,
        "severity_color": q.severity_color,
    }


def _ser_article(a) -> dict:
    return {
        "id": a.id, "source": a.source, "title": a.title,
        "summary": a.summary, "link": a.link,
        "published": a.published.isoformat() if a.published else None,
        "time_ago": a.time_ago, "category": a.category,
    }


def _ser_parking_lot(l) -> dict:
    return {
        "id": l.id, "name": l.name, "city": l.city, "country": l.country,
        "total": l.total, "occupied": l.occupied, "free": l.free,
        "occ_pct": l.occ_pct, "lat": l.lat, "lon": l.lon,
        "type": l.type, "status": l.status,
    }


# ── lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start all pollers as background tasks
    tasks = [
        asyncio.create_task(_market_loop()),
        asyncio.create_task(crypto.run_stream(_on_crypto)),
        asyncio.create_task(aircraft.run_poller(REFRESH_AIRCRAFT)),
        asyncio.create_task(ships.run_poller(REFRESH_SHIPS)),
        asyncio.create_task(space.run_poller(REFRESH_SPACE)),
        asyncio.create_task(weather.run_poller(REFRESH_WEATHER)),
        asyncio.create_task(earthquakes.run_poller(REFRESH_EQ)),
        asyncio.create_task(news.run_poller(REFRESH_NEWS)),
        asyncio.create_task(parking.run_poller(REFRESH_PARKING)),
        asyncio.create_task(bonds.run_poller(REFRESH_BONDS)),
        asyncio.create_task(forex.run_poller(REFRESH_FOREX)),
        asyncio.create_task(fred.run_poller(REFRESH_FRED)),
        asyncio.create_task(cve.run_poller(REFRESH_CVE)),
        asyncio.create_task(launches.run_poller(REFRESH_LAUNCHES)),
        asyncio.create_task(space_weather.run_poller(REFRESH_SPACE_WEATHER)),
        asyncio.create_task(wildfires.run_poller(REFRESH_WILDFIRES)),
        asyncio.create_task(cameras.run_poller(REFRESH_CAMERAS)),
        asyncio.create_task(conflicts.run_poller(REFRESH_CONFLICTS)),
        asyncio.create_task(sanctions.run_poller(REFRESH_SANCTIONS)),
        asyncio.create_task(population.run_poller(REFRESH_POPULATION)),
        asyncio.create_task(options_flow.run_poller(REFRESH_OPTIONS_FLOW)),
        asyncio.create_task(outages.run_poller(REFRESH_OUTAGES)),
        asyncio.create_task(_broadcast_loop()),
    ]
    yield
    for t in tasks:
        t.cancel()


_market_quotes: dict = {}
_crypto_ticks: dict  = {}


async def _market_loop():
    while True:
        global _market_quotes
        quotes = await market.fetch_quotes(market.ALL_TICKERS)
        if quotes:
            _market_quotes = quotes
            await mgr.broadcast("markets", {
                "quotes": {k: _ser_quote(v) for k, v in quotes.items()},
                "groups": market.WATCHLIST,
            })
        await asyncio.sleep(REFRESH_MARKET)


def _on_crypto(ticks: dict):
    global _crypto_ticks
    _crypto_ticks = ticks
    asyncio.get_event_loop().call_soon_threadsafe(
        lambda: asyncio.ensure_future(mgr.broadcast("crypto", {
            "ticks": {k: _ser_crypto(v) for k, v in ticks.items()}
        }))
    )


async def _broadcast_loop():
    """Push non-market updates to WebSocket clients on a schedule."""
    while True:
        await asyncio.sleep(15)
        s = aircraft.get_aircraft()
        await mgr.broadcast("aircraft", {
            "total": s.total, "airborne": s.airborne,
            "planes": [_ser_aircraft(p) for p in s.aircraft[:300]],
            "error": s.error,
        })

        await asyncio.sleep(5)
        sh = ships.get_ships()
        await mgr.broadcast("ships", {
            "total": sh.total, "underway": sh.underway,
            "vessels": [_ser_vessel(v) for v in sh.vessels[:200]],
            "source": sh.source, "error": sh.error,
        })

        await asyncio.sleep(5)
        sp = space.get_space()
        await mgr.broadcast("space", {
            "iss": _ser_station(sp.iss),
            "tiangong": _ser_station(sp.tiangong),
            "active_count": sp.active_count,
            "starlink_count": sp.starlink_count,
            "notable": [_ser_tle(o) for o in sp.notable[:60]],
        })

        await asyncio.sleep(5)
        eq = earthquakes.get_earthquakes()
        await mgr.broadcast("earthquakes", {
            "hourly_count": eq.hourly_count,
            "daily_count": eq.daily_count,
            "recent": [_ser_quake(q) for q in eq.recent[:30]],
            "significant": [_ser_quake(q) for q in eq.significant[:20]],
            "largest_today": _ser_quake(eq.largest_today) if eq.largest_today else None,
        })


# ── app ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Open Bloomberg Terminal API", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ── static files + root redirect ─────────────────────────────────────────────

_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    idx = _static / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text())
    return HTMLResponse("<h1>Place index.html in ~/bloomberg/static/</h1>")

@app.get("/agora", response_class=HTMLResponse)
async def agora():
    idx = _static / "agora" / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text())
    return HTMLResponse("<h1>agora/index.html not found</h1>")


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/api/markets")
async def get_markets():
    return {
        "quotes": {k: _ser_quote(v) for k, v in _market_quotes.items()},
        "groups": market.WATCHLIST,
        "updated": time.time(),
    }


@app.get("/api/crypto")
async def get_crypto():
    return {
        "ticks": {k: _ser_crypto(v) for k, v in _crypto_ticks.items()},
        "updated": time.time(),
    }


@app.get("/api/aircraft")
async def get_aircraft():
    s = aircraft.get_aircraft()
    return {
        "total": s.total, "airborne": s.airborne,
        "planes": [_ser_aircraft(p) for p in s.aircraft[:500]],
        "error": s.error, "updated": s.updated,
    }


@app.get("/api/ships")
async def get_ships():
    s = ships.get_ships()
    return {
        "total": s.total, "underway": s.underway,
        "vessels": [_ser_vessel(v) for v in s.vessels],
        "source": s.source, "error": s.error, "updated": s.updated,
    }


@app.get("/api/space")
async def get_space():
    s = space.get_space()
    return {
        "iss": _ser_station(s.iss),
        "tiangong": _ser_station(s.tiangong),
        "active_count": s.active_count,
        "starlink_count": s.starlink_count,
        "notable": [_ser_tle(o) for o in s.notable],
        "updated": s.updated,
    }


@app.get("/api/weather")
async def get_weather():
    s = weather.get_weather()
    return {
        "cities": {k: _ser_weather(v) for k, v in s.cities.items()},
        "updated": s.updated,
    }


@app.get("/api/earthquakes")
async def get_earthquakes():
    s = earthquakes.get_earthquakes()
    return {
        "hourly_count": s.hourly_count, "daily_count": s.daily_count,
        "recent": [_ser_quake(q) for q in s.recent],
        "significant": [_ser_quake(q) for q in s.significant],
        "largest_today": _ser_quake(s.largest_today) if s.largest_today else None,
        "updated": s.updated,
    }


@app.get("/api/news")
async def get_news():
    s = news.get_news()
    return {
        "articles": [_ser_article(a) for a in s.articles[:100]],
        "by_category": {cat: [_ser_article(a) for a in arts[:15]]
                        for cat, arts in s.by_category.items()},
        "sources_ok": s.sources_ok, "sources_fail": s.sources_fail,
        "updated": s.updated,
    }




@app.get("/api/status")
async def get_status():
    return {
        "server": "Open Bloomberg Terminal",
        "version": "1.0.0",
        "uptime": time.time(),
        "feeds": {
            "markets":     len(_market_quotes) > 0,
            "crypto":      len(_crypto_ticks) > 0,
            "aircraft":    aircraft.get_aircraft().total > 0,
            "ships":       ships.get_ships().total > 0,
            "space":       space.get_space().iss is not None,
            "weather":     len(weather.get_weather().cities) > 0,
            "earthquakes": earthquakes.get_earthquakes().hourly_count >= 0,
            "news":        len(news.get_news().articles) > 0,
            "parking":     len(parking.get_parking().lots) > 0,
        },
        "ws_clients": len(mgr.active),
    }


# ── New endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/bonds")
async def get_bonds():
    s = bonds.get_bonds()
    return {"maturities": s.maturities, "spread_10y2y": s.spread_10y2y,
            "updated": s.updated, "error": s.error}

@app.get("/api/forex")
async def get_forex():
    s = forex.get_forex()
    return {"rates": s.rates, "updated": s.updated, "error": s.error}

@app.get("/api/fred")
async def get_fred():
    s = fred.get_fred()
    return {"series": s.series, "updated": s.updated, "error": s.error}

@app.get("/api/fred/history/{series_id}")
async def get_fred_history(series_id: str, limit: int = 60):
    data = await fred.fetch_series_history(series_id, limit=limit)
    return {"series_id": series_id, "data": data}

@app.get("/api/cve")
async def get_cve():
    s = cve.get_cve()
    return {"recent": s.recent, "kev": s.kev, "ransomware": s.ransomware,
            "updated": s.updated, "error": s.error}

@app.get("/api/launches")
async def get_launches():
    s = launches.get_launches()
    return {"upcoming": s.upcoming, "recent": s.recent,
            "updated": s.updated, "error": s.error}

@app.get("/api/space-weather")
async def get_space_weather():
    s = space_weather.get_space_weather()
    return {
        "kp_index": s.kp_index, "kp_24h": s.kp_24h,
        "solar_wind": s.solar_wind, "x_ray_flux": s.x_ray_flux,
        "alerts": s.alerts, "solar_regions": s.solar_regions,
        "storm_level": s.storm_level,
        "updated": s.updated, "error": s.error,
    }

@app.get("/api/wildfires")
async def get_wildfires():
    s = wildfires.get_wildfires()
    return {"hotspots": s.hotspots, "count": s.count,
            "updated": s.updated, "error": s.error}

@app.get("/api/equity/{symbol}")
async def get_equity_chart(symbol: str, interval: str = "5m", range_: str = "1d"):
    """Proxy Yahoo Finance chart data — avoids CORS from browser."""
    import aiohttp
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={range_}&includeAdjustedClose=true")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12),
                                   headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    return await r.json()
        return {"error": f"Yahoo returned non-200"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/equity/summary/{symbol}")
async def get_equity_summary(symbol: str):
    """Proxy Yahoo Finance quote summary."""
    import aiohttp
    url = (f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
           f"?modules=summaryDetail,price,defaultKeyStatistics,financialData")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12),
                                   headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    return await r.json()
        return {"error": "not found"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/options/{symbol}")
async def get_options(symbol: str, date: str = ""):
    """Proxy Yahoo Finance options chain."""
    import aiohttp
    url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}"
    if date:
        url += f"?date={date}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12),
                                   headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    return await r.json()
        return {"error": "not found"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/neo")
async def get_neo(days: int = 7):
    """NASA Near-Earth Objects — free key from api.nasa.gov."""
    import aiohttp, os
    from datetime import datetime, timedelta
    key = os.environ.get("NASA_API_KEY", "DEMO_KEY")
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end   = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    url   = f"https://api.nasa.gov/neo/rest/v1/feed?start_date={start}&end_date={end}&api_key={key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    raw = await r.json()
                    objects = []
                    for date_str, neos in raw.get("near_earth_objects", {}).items():
                        for n in neos:
                            ca = n.get("close_approach_data", [{}])[0]
                            objects.append({
                                "name":       n.get("name",""),
                                "id":         n.get("id",""),
                                "hazardous":  n.get("is_potentially_hazardous_asteroid", False),
                                "diam_min_m": n.get("estimated_diameter",{}).get("meters",{}).get("estimated_diameter_min",0),
                                "diam_max_m": n.get("estimated_diameter",{}).get("meters",{}).get("estimated_diameter_max",0),
                                "miss_km":    float(ca.get("miss_distance",{}).get("kilometers",0)),
                                "miss_lunar": float(ca.get("miss_distance",{}).get("lunar",0)),
                                "velocity_kph": float(ca.get("relative_velocity",{}).get("kilometers_per_hour",0)),
                                "approach_date": ca.get("close_approach_date",""),
                            })
                    objects.sort(key=lambda x: x["miss_km"])
                    return {"objects": objects, "count": raw.get("element_count",0)}
    except Exception as e:
        return {"error": str(e), "objects": []}


@app.get("/api/conflicts")
async def get_conflicts():
    s = conflicts.get_conflicts()
    return {"events": s.events, "updated": s.updated, "error": s.error}

@app.get("/api/sanctions")
async def get_sanctions(q: str = "", program: str = "", limit: int = 100):
    s = sanctions.get_sanctions()
    entries = s.entries
    if q:
        ql = q.lower()
        entries = [e for e in entries if ql in e.get("name","").lower() or ql in e.get("country","").lower()]
    if program:
        entries = [e for e in entries if e.get("program","") == program]
    return {
        "entries":  entries[:limit],
        "count":    s.count,
        "programs": s.programs,
        "matched":  len(entries),
        "updated":  s.updated,
        "error":    s.error,
    }

@app.get("/api/population")
async def get_population():
    s = population.get_population()
    return {"countries": s.countries, "indicators": s.indicators, "updated": s.updated, "error": s.error}


@app.get("/api/options-flow")
async def get_options_flow(ticker: str = "", type: str = ""):
    s = options_flow.get_options_flow()
    rows = s.unusual
    if ticker: rows = [r for r in rows if r["ticker"] == ticker.upper()]
    if type:   rows = [r for r in rows if r["type"] == type.upper()]
    return {"unusual": rows[:100], "summary": s.summary, "updated": s.updated, "error": s.error}

@app.get("/api/outages")
async def get_outages():
    s = outages.get_outages()
    return {"alerts": s.alerts, "countries": s.countries, "bgp": s.bgp[:30],
            "updated": s.updated, "error": s.error}

@app.get("/api/parking")
async def get_parking_detail(city: str = ""):
    s = parking.get_parking()
    lots = s.lots
    if city: lots = [l for l in lots if l.city.lower() == city.lower()]
    return {
        "lots":    [_ser_parking_lot(l) for l in lots],
        "by_city": {c: [_ser_parking_lot(l) for l in ll] for c, ll in s.by_city.items()},
        "summary": s.summary,
        "updated": s.updated,
        "error":   s.error,
    }

@app.get("/api/cameras")
async def get_cameras():
    s = cameras.get_cameras()
    return {"cameras": s.cameras, "updated": s.updated, "error": s.error}

@app.get("/api/camera-proxy")
async def camera_proxy(url: str):
    """Proxy a camera image to avoid CORS issues in the browser."""
    import aiohttp
    from fastapi.responses import Response
    # only allow http/https image URLs
    if not url.startswith(("http://", "https://")):
        return Response(status_code=400)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8),
                                   headers={"User-Agent": "OpenBloombergTerminal/2.0"}) as r:
                if r.status == 200:
                    content = await r.read()
                    ct = r.headers.get("Content-Type", "image/jpeg")
                    return Response(content=content, media_type=ct,
                                    headers={"Cache-Control": "max-age=30"})
    except Exception:
        pass
    return Response(status_code=502)

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await mgr.connect(ws)
    # Send full current state immediately on connect
    await ws.send_text(json.dumps({
        "event": "init",
        "data": {
            "markets": {
                "quotes": {k: _ser_quote(v) for k, v in _market_quotes.items()},
                "groups": market.WATCHLIST,
            },
            "crypto": {"ticks": {k: _ser_crypto(v) for k, v in _crypto_ticks.items()}},
        },
        "ts": time.time(),
    }))
    try:
        while True:
            await ws.receive_text()  # keep alive, client can send pings
    except WebSocketDisconnect:
        mgr.disconnect(ws)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  Open Bloomberg Terminal")
    print("  API:       http://localhost:8000/api/status")
    print("  Docs:      http://localhost:8000/docs")
    print("  WebSocket: ws://localhost:8000/ws\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, log_level="warning")
