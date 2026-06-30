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
import os
import logging
from pathlib import Path

# Suppress noisy FlightRadar24 gzip decode warning (harmless — library recovers fine)
logging.getLogger("FlightRadarAPI.request").setLevel(logging.ERROR)
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Load .env if present (before feeds read os.environ)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))
from feeds import aircraft, ships, space, weather, earthquakes, news, parking
from feeds import market, crypto
from feeds import bonds, forex, fred, cve, launches, space_weather, wildfires, cameras
from feeds import conflicts, sanctions, population, options_flow, outages
from feeds import options_mispricing as opt_mis_feed
from feeds import equity_alpha
from feeds import energy_eia
from feeds import arxiv as arxiv_feed
from feeds import who_gho
from feeds import unhcr as unhcr_feed
from feeds import threats as threats_feed
from feeds import ocean as ocean_feed
from feeds import trade as trade_feed
from feeds import elections as elections_feed
from feeds import leaks as leaks_feed
from feeds import cloudflare as cloudflare_feed
from feeds import recommendations
from feeds import sec_edgar
from feeds import charts as charts_feed
from feeds import earnings as earnings_feed
from feeds import darkpool as darkpool_feed
from feeds import econ_calendar as econ_feed
from feeds import climate as climate_feed
from feeds import polygon as polygon_feed
from feeds import cmc as cmc_feed
from feeds import gdelt as gdelt_feed
from feeds import hackernews as hn_feed
from feeds import clinical_trials as ct_feed

# ── refresh intervals ────────────────────────────────────────────────────────
REFRESH_MARKET        = 5
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
REFRESH_THREATS       = 1800
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
REFRESH_EQUITY_ALPHA  = 86400
REFRESH_ENERGY_EIA    = 3600
REFRESH_ARXIV         = 21600
REFRESH_WHO           = 86400
REFRESH_UNHCR         = 86400
REFRESH_EDGAR         = 3600
REFRESH_CHARTS        = 300
REFRESH_EARNINGS      = 3600
REFRESH_DARKPOOL      = 3600
REFRESH_ECON          = 21600
REFRESH_CLIMATE       = 86400
REFRESH_POLYGON       = 3600
REFRESH_CMC           = 300
REFRESH_OCEAN         = 21600
REFRESH_TRADE         = 86400
REFRESH_ELECTIONS     = 21600
REFRESH_LEAKS         = 21600
REFRESH_CLOUDFLARE    = 3600
REFRESH_GDELT         = 1800
REFRESH_HN            = 600
REFRESH_CT            = 3600

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
        "market_cap": getattr(t, "market_cap", 0),
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
        "aircraft_type": getattr(p, "aircraft_type", ""),
        "registration":  getattr(p, "registration", ""),
        "origin_airport": getattr(p, "origin_airport", ""),
        "destination_airport": getattr(p, "destination_airport", ""),
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
        asyncio.create_task(market.run_poller(REFRESH_MARKET)),
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
        asyncio.create_task(threats_feed.run_poller(REFRESH_THREATS)),
        asyncio.create_task(launches.run_poller(REFRESH_LAUNCHES)),
        asyncio.create_task(space_weather.run_poller(REFRESH_SPACE_WEATHER)),
        asyncio.create_task(wildfires.run_poller(REFRESH_WILDFIRES)),
        asyncio.create_task(cameras.run_poller(REFRESH_CAMERAS)),
        asyncio.create_task(conflicts.run_poller(REFRESH_CONFLICTS)),
        asyncio.create_task(sanctions.run_poller(REFRESH_SANCTIONS)),
        asyncio.create_task(population.run_poller(REFRESH_POPULATION)),
        asyncio.create_task(options_flow.run_poller(REFRESH_OPTIONS_FLOW)),
        asyncio.create_task(outages.run_poller(REFRESH_OUTAGES)),
        asyncio.create_task(equity_alpha.run_poller(REFRESH_EQUITY_ALPHA)),
        asyncio.create_task(energy_eia.run_poller(REFRESH_ENERGY_EIA)),
        asyncio.create_task(arxiv_feed.run_poller(REFRESH_ARXIV)),
        asyncio.create_task(who_gho.run_poller(REFRESH_WHO)),
        asyncio.create_task(unhcr_feed.run_poller(REFRESH_UNHCR)),
        asyncio.create_task(sec_edgar.run_poller(REFRESH_EDGAR)),
        asyncio.create_task(charts_feed.run_poller(REFRESH_CHARTS)),
        asyncio.create_task(earnings_feed.run_poller(REFRESH_EARNINGS)),
        asyncio.create_task(darkpool_feed.run_poller(REFRESH_DARKPOOL)),
        asyncio.create_task(econ_feed.run_poller(REFRESH_ECON)),
        asyncio.create_task(climate_feed.run_poller(REFRESH_CLIMATE)),
        asyncio.create_task(polygon_feed.run_poller(REFRESH_POLYGON)),
        asyncio.create_task(cmc_feed.run_poller(REFRESH_CMC)),
        asyncio.create_task(ocean_feed.run_poller(REFRESH_OCEAN)),
        asyncio.create_task(trade_feed.run_poller(REFRESH_TRADE)),
        asyncio.create_task(elections_feed.run_poller(REFRESH_ELECTIONS)),
        asyncio.create_task(leaks_feed.run_poller(REFRESH_LEAKS)),
        asyncio.create_task(cloudflare_feed.run_poller(REFRESH_CLOUDFLARE)),
        asyncio.create_task(gdelt_feed.run_poller(REFRESH_GDELT)),
        asyncio.create_task(hn_feed.run_poller(REFRESH_HN)),
        asyncio.create_task(ct_feed.run_poller(REFRESH_CT)),
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
        quotes = market.get_quotes()
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
    _delta_dir = _static / "delta"
    if _delta_dir.exists():
        app.mount("/delta/", StaticFiles(directory=str(_delta_dir)), name="delta-static")

@app.get("/", response_class=HTMLResponse)
async def root():
    idx = _static / "delta" / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text(), headers={"Cache-Control": "no-store, max-age=0"})
    return HTMLResponse("<h1>Place index.html in ~/bloomberg/static/</h1>")

@app.get("/delta", response_class=HTMLResponse)
async def delta():
    idx = _static / "delta" / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text(), headers={"Cache-Control": "no-store, max-age=0"})
    return HTMLResponse("<h1>delta/index.html not found</h1>")


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/api/markets")
async def get_markets():
    return {
        "quotes": {k: _ser_quote(v) for k, v in _market_quotes.items()},
        "groups": market.WATCHLIST,
        "updated": time.time(),
    }


@app.get("/api/markets/stream")
async def markets_stream(request: Request):
    async def _gen():
        q = market.subscribe_ticks()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    tick = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {json.dumps(tick)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            market.unsubscribe_ticks(q)
    return StreamingResponse(_gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    # Sort by DWT descending (largest vessels first), cap at 500 for performance
    top = sorted(s.vessels, key=lambda v: getattr(v, "dwt", 0) or 0, reverse=True)[:500]
    return {
        "total": s.total, "underway": s.underway,
        "vessels": [_ser_vessel(v) for v in top],
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
        "crew": s.crew,
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

@app.get("/api/threats")
async def get_threats():
    s = threats_feed.get_threats()
    return {"advisories": s.advisories, "updated": s.updated, "error": s.error}

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

@app.get("/api/energy")
async def get_energy():
    s = energy_eia.get_energy()
    return {
        "oil":         s.oil,
        "gas":         s.gas,
        "electricity": s.electricity,
        "nuclear":     s.nuclear,
        "renewables":  s.renewables,
        "updated":     s.updated,
        "error":       s.error,
    }

@app.get("/api/equity-fundamentals")
async def get_equity_fundamentals():
    s = equity_alpha.get_equity()
    return {
        "fundamentals": s.fundamentals,
        "updated": s.updated,
        "error": s.error,
    }

@app.get("/api/arxiv")
async def get_arxiv():
    s = arxiv_feed.get_arxiv()
    return {"ai": s.ai, "bio": s.bio, "quant": s.quant, "rob": s.rob, "sem": s.sem, "updated": s.updated, "error": s.error}

@app.get("/api/gdelt")
async def get_gdelt():
    s = gdelt_feed.get_gdelt()
    return {"pol": s.pol, "ter": s.ter, "dip": s.dip, "updated": s.updated, "error": s.error}

@app.get("/api/hackernews")
async def get_hackernews():
    s = hn_feed.get_hackernews()
    return {"stories": s.stories, "updated": s.updated, "error": s.error}

@app.get("/api/clinical-trials")
async def get_clinical_trials():
    s = ct_feed.get_clinical_trials()
    return {"studies": s.studies, "by_condition": s.by_condition,
            "total": s.total, "updated": s.updated, "error": s.error}

@app.get("/api/who")
async def get_who():
    s = who_gho.get_who()
    return {"by_country": s.by_country, "indicators": s.indicators, "updated": s.updated, "error": s.error}

@app.get("/api/unhcr")
async def get_unhcr():
    s = unhcr_feed.get_unhcr()
    return {"totals": s.totals, "by_origin": s.by_origin, "by_host": s.by_host, "updated": s.updated, "error": s.error}

@app.get("/api/recommendations")
async def get_recommendations():
    try:
        return recommendations.compute()
    except Exception as e:
        return {"stocks": [], "macro": {}, "updated": time.time(), "error": str(e)}

@app.get("/api/edgar")
async def get_edgar():
    s = sec_edgar.get_edgar()
    def _ser_trade(t):
        return {
            "ticker": t.ticker, "company": t.company,
            "insider_name": t.insider_name, "role": t.role,
            "action": t.action, "shares": t.shares,
            "price": t.price, "value_usd": t.value_usd,
            "date": t.date, "filing_url": t.filing_url,
        }
    def _ser_filing(f):
        return {
            "ticker": f.ticker, "company": f.company,
            "form": f.form, "date": f.date,
            "title": f.title, "url": f.url,
        }
    return {
        "insider_trades": [_ser_trade(t) for t in s.insider_trades],
        "filings_8k":     [_ser_filing(f) for f in s.filings_8k],
        "filings_10q":    [_ser_filing(f) for f in s.filings_10q],
        "updated":        s.updated,
        "error":          s.error,
    }

@app.get("/api/earnings")
async def get_earnings():
    s = earnings_feed.get_earnings()
    return {
        "upcoming": s.upcoming,
        "recent":   s.recent,
        "updated":  s.updated,
        "error":    s.error,
    }


@app.get("/api/charts")
async def get_charts():
    s = charts_feed.get_charts()
    return {
        "intraday": s.intraday,
        "daily":    s.daily,
        "updated":  s.updated,
        "error":    s.error,
    }


@app.get("/api/charts/{symbol}")
async def get_charts_symbol(symbol: str):
    sym = symbol.upper().strip()
    loop = asyncio.get_event_loop()
    intraday, daily = await loop.run_in_executor(
        None, charts_feed._fetch_one_blocking, sym
    )
    return {
        "symbol":   sym,
        "intraday": intraday,
        "daily":    daily,
    }


@app.get("/api/darkpool")
async def get_darkpool():
    s = darkpool_feed.get_darkpool()
    return {"prints": s.prints, "ats_vol": s.ats_vol, "updated": s.updated, "error": s.error}


@app.get("/api/climate")
async def get_climate():
    s = climate_feed.get_climate()
    return {"stations": s.stations, "updated": s.updated, "error": s.error}


@app.get("/api/econ-calendar")
async def get_econ_calendar():
    s = econ_feed.get_econ_calendar()
    return {"events": s.events, "updated": s.updated, "error": s.error}


@app.get("/api/ticker-news")
async def get_ticker_news(symbol: str, days: int = 5):
    """Fetch recent company news from Finnhub."""
    import aiohttp
    from datetime import date, timedelta
    key = os.environ.get("FINNHUB_KEY", "")
    if not key:
        return {"articles": [], "error": "No FINNHUB_KEY"}
    to_d = date.today()
    from_d = to_d - timedelta(days=max(1, min(days, 30)))
    url = (f"https://finnhub.io/api/v1/company-news"
           f"?symbol={symbol.upper()}&from={from_d}&to={to_d}&token={key}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return {"articles": [], "error": f"HTTP {r.status}"}
                data = await r.json()
                articles = [{
                    "headline": a.get("headline", ""),
                    "source":   a.get("source", ""),
                    "datetime": a.get("datetime", 0),
                    "url":      a.get("url", ""),
                    "summary":  a.get("summary", "")[:300],
                } for a in (data or [])[:30]]
                return {"articles": articles, "symbol": symbol.upper()}
    except Exception as e:
        return {"articles": [], "error": str(e)}


@app.get("/api/recommendations/analyze/{symbol}")
async def analyze_ticker(symbol: str):
    try:
        return await recommendations.compute_ticker(symbol.upper().strip())
    except Exception as e:
        return {"error": str(e), "symbol": symbol.upper()}

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

_ORDERFLOW_CACHE = {}

@app.get("/api/orderflow-surface")
async def orderflow_surface(symbol: str = "SPY", expiries: int = 6):
    """Strike x DTE x flow-intensity surface for the 3D order-flow chart.
    Built from multi-expiry option chains via yfinance (handles Yahoo auth).
    Returns z-matrices for gex/volume/netflow/oi on a common strike grid. Cached ~45s."""
    import math, time, asyncio
    symbol = (symbol or "SPY").upper().strip()
    expiries = max(1, min(int(expiries), 8))
    ckey = f"{symbol}:{expiries}"
    nowt = time.time()
    hit = _ORDERFLOW_CACHE.get(ckey)
    if hit and nowt - hit[0] < 45:
        return hit[1]

    def bs_gamma(S, K, T, sig):
        if S <= 0 or K <= 0 or T <= 0 or sig <= 0:
            return 0.0
        d1 = (math.log(S / K) + (0.05 + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
        return math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (S * sig * math.sqrt(T))

    def lin_interp(xq, xs, ys):
        out = []; n = len(xs)
        for x in xq:
            if n == 0 or x < xs[0] or x > xs[-1]:
                out.append(0.0); continue
            lo, hi = 0, n - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if xs[mid] <= x: lo = mid
                else: hi = mid
            x0, x1 = xs[lo], xs[hi]
            f = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
            out.append(ys[lo] * (1 - f) + ys[hi] * f)
        return out

    def fnum(v):
        try:
            v = float(v)
            return v if v == v else 0.0       # NaN -> 0
        except Exception:
            return 0.0

    def build():
        import yfinance as yf
        from datetime import date
        tk = yf.Ticker(symbol)
        try:
            exps = list(tk.options)[:expiries]
        except Exception as e:
            return {"error": f"options list failed: {e}"}
        if not exps:
            return {"error": "no expiries"}

        spot = 0.0
        try:
            fi = tk.fast_info
            spot = float(fi.get("last_price") or fi.get("lastPrice") or 0) or 0.0
        except Exception:
            spot = 0.0
        if spot <= 0:
            try:
                h = tk.history(period="1d")
                spot = float(h["Close"].iloc[-1]) if len(h) else 0.0
            except Exception:
                spot = 0.0
        if spot <= 0:
            return {"error": "no spot"}

        today = date.today()
        ngrid = 60
        lo, hi = spot * 0.7, spot * 1.3
        grid = [lo + (hi - lo) * i / (ngrid - 1) for i in range(ngrid)]
        dtes, z_gex, z_vol, z_net, z_oi = [], [], [], [], []
        agg_oi = {}

        for exp in exps:
            try:
                oc = tk.option_chain(exp)
            except Exception:
                continue
            try:
                dte = max((date.fromisoformat(exp) - today).days, 0)
            except Exception:
                dte = 0
            T = max(dte / 365.0, 1e-4)
            m = {}
            for _, c in oc.calls.iterrows():
                k = fnum(c.get("strike"))
                if k <= 0:
                    continue
                e = m.setdefault(k, {"cOI": 0, "cV": 0, "cIV": 0, "pOI": 0, "pV": 0, "pIV": 0})
                e["cOI"], e["cV"], e["cIV"] = fnum(c.get("openInterest")), fnum(c.get("volume")), fnum(c.get("impliedVolatility"))
            for _, p in oc.puts.iterrows():
                k = fnum(p.get("strike"))
                if k <= 0:
                    continue
                e = m.setdefault(k, {"cOI": 0, "cV": 0, "cIV": 0, "pOI": 0, "pV": 0, "pIV": 0})
                e["pOI"], e["pV"], e["pIV"] = fnum(p.get("openInterest")), fnum(p.get("volume")), fnum(p.get("impliedVolatility"))
            if not m:
                continue
            ks = sorted(m.keys())
            gex_n, vol_n, net_n, oi_n = [], [], [], []
            for k in ks:
                e = m[k]
                cg = bs_gamma(spot, k, T, e["cIV"] or 0.3)
                pg = bs_gamma(spot, k, T, e["pIV"] or 0.3)
                gex_n.append((cg * e["cOI"] - pg * e["pOI"]) * 100 * spot * spot * 0.01 / 1e6)
                vol_n.append(e["cV"] + e["pV"])
                net_n.append(e["cV"] - e["pV"])
                oi_n.append(e["cOI"] + e["pOI"])
                a = agg_oi.setdefault(k, [0, 0]); a[0] += e["cOI"]; a[1] += e["pOI"]
            dtes.append(dte)
            z_gex.append(lin_interp(grid, ks, gex_n))
            z_vol.append(lin_interp(grid, ks, vol_n))
            z_net.append(lin_interp(grid, ks, net_n))
            z_oi.append(lin_interp(grid, ks, oi_n))

        if not dtes:
            return {"error": "no usable chains"}
        order = sorted(range(len(dtes)), key=lambda i: dtes[i])
        def reorder(z):
            return [z[i] for i in order]
        call_wall = max(agg_oi.items(), key=lambda kv: kv[1][0])[0] if agg_oi else None
        put_wall = max(agg_oi.items(), key=lambda kv: kv[1][1])[0] if agg_oi else None
        return {
            "ticker": symbol, "spot": round(spot, 2), "asof": int(time.time()),
            "x": [round(g, 2) for g in grid], "y": [dtes[i] for i in order],
            "z": {"gex": reorder(z_gex), "volume": reorder(z_vol),
                  "netflow": reorder(z_net), "oi": reorder(z_oi)},
            "call_wall": call_wall, "put_wall": put_wall,
        }

    try:
        out = await asyncio.to_thread(build)
    except Exception as e:
        return {"error": str(e)}
    if isinstance(out, dict) and "error" not in out:
        _ORDERFLOW_CACHE[ckey] = (nowt, out)
    return out

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

@app.get("/api/options-mispricing/{ticker}")
async def get_options_mispricing(ticker: str):
    # Blocking yfinance + pricing work → run off the event loop.
    return await asyncio.to_thread(opt_mis_feed.analyze, ticker)

@app.get("/api/options-mc/{ticker}")
async def get_options_mc(ticker: str, horizon: int = 30, vol_source: str = "iv"):
    return await asyncio.to_thread(opt_mis_feed.simulate, ticker, horizon, vol_source)

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

@app.get("/api/polygon-data")
async def get_polygon_data():
    s = polygon_feed.get_polygon()
    return {"bars": s.bars, "fundamentals": s.fundamentals,
            "updated": s.updated, "error": s.error}


@app.get("/api/cmc-coins")
async def get_cmc_coins():
    s = cmc_feed.get_cmc()
    return {"coins": s.coins, "updated": s.updated, "error": s.error}


@app.get("/api/ocean")
async def get_ocean():
    s = ocean_feed.get_ocean()
    return {
        "arctic":    {
            "extent":  s.arctic.extent,
            "date":    s.arctic.date,
            "anomaly": s.arctic.anomaly,
            "trend":   s.arctic.trend,
        },
        "antarctic": {
            "extent":  s.antarctic.extent,
            "date":    s.antarctic.date,
            "anomaly": s.antarctic.anomaly,
            "trend":   s.antarctic.trend,
        },
        "updated": s.updated,
        "error":   s.error,
    }


@app.get("/api/trade")
async def get_trade():
    s = trade_feed.get_trade()
    return {"countries": s.countries, "updated": s.updated, "error": s.error}


@app.get("/api/elections")
async def get_elections():
    s = elections_feed.get_elections()
    return {"elections": s.elections, "updated": s.updated, "error": s.error}


@app.get("/api/leaks")
async def get_leaks():
    s = leaks_feed.get_leaks()
    return {
        "breaches":    s.breaches,
        "total_pwned": s.total_pwned,
        "by_class":    s.by_class,
        "updated":     s.updated,
        "error":       s.error,
    }


@app.get("/api/cloudflare")
async def get_cloudflare():
    s = cloudflare_feed.get_cloudflare()
    return {
        "bgp_leaks": s.bgp_leaks,
        "bgp_stats": s.bgp_stats,
        "updated":   s.updated,
        "error":     s.error,
    }


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

# Serve delta static files at root so relative .jsx paths resolve
from fastapi.staticfiles import StaticFiles as _SF
_delta = Path(__file__).parent / "static" / "delta"
if _delta.exists():
    app.mount("/", _SF(directory=str(_delta), html=True), name="delta-root")
