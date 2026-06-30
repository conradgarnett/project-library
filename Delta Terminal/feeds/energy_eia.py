"""US Energy data via EIA Open Data API v2 — free key from eia.gov/developer.
Covers: crude oil, natural gas, electricity, nuclear, renewables, petroleum inventories.
"""
import asyncio, aiohttp, os, time
from dataclasses import dataclass, field
from typing import Optional

EIA_KEY  = os.environ.get("EIA_API_KEY", "")
EIA_BASE = "https://api.eia.gov/v2"


@dataclass
class EnergyState:
    oil:         dict = field(default_factory=dict)
    gas:         dict = field(default_factory=dict)
    electricity: dict = field(default_factory=dict)
    nuclear:     dict = field(default_factory=dict)
    renewables:  dict = field(default_factory=dict)
    petroleum:   dict = field(default_factory=dict)
    updated:     float = 0.0
    error:       Optional[str] = None


_state = EnergyState()


def get_energy():
    return _state


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> Optional[dict]:
    try:
        params["api_key"] = EIA_KEY
        async with session.get(
            EIA_BASE + path,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception:
        pass
    return None


def _latest(resp, key="value") -> Optional[dict]:
    """Extract the most recent data point from an EIA v2 response."""
    try:
        data = resp["response"]["data"]
        if data:
            row = data[0]
            return row
    except Exception:
        pass
    return None


def _series(resp) -> list:
    """Return list of {period, value} from an EIA v2 response."""
    try:
        return [{"period": r.get("period"), "value": r.get("value")} for r in resp["response"]["data"]]
    except Exception:
        return []


async def _fetch_oil(session) -> dict:
    results = {}
    # WTI crude spot price
    r = await _get(session, "/petroleum/pri/spt/data/", {
        "frequency": "daily", "data[0]": "value",
        "facets[series][]": "RWTC", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "30",
    })
    if r:
        row = _latest(r)
        if row:
            results["wti_price"] = row.get("value")
            results["wti_date"]  = row.get("period")
        results["wti_history"] = _series(r)

    # Brent crude spot price
    r = await _get(session, "/petroleum/pri/spt/data/", {
        "frequency": "daily", "data[0]": "value",
        "facets[series][]": "RBRTE", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "30",
    })
    if r:
        row = _latest(r)
        if row:
            results["brent_price"] = row.get("value")
            results["brent_date"]  = row.get("period")
        results["brent_history"] = _series(r)

    # US crude production
    r = await _get(session, "/petroleum/sum/sndw/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "WCRFPUS2", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "4",
    })
    if r:
        row = _latest(r)
        if row:
            results["us_production_mbpd"] = row.get("value")

    # Commercial crude inventories (52 weeks for sparkline)
    r = await _get(session, "/petroleum/stoc/wstk/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "WCESTUS1", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "52",
    })
    if r:
        row = _latest(r)
        if row:
            results["us_inventory_mb"] = row.get("value")
            results["us_inventory_date"] = row.get("period")
        results["crude_history"] = _series(r)

    # Cushing, OK crude stocks
    r = await _get(session, "/petroleum/stoc/wstk/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "W_EPC0_SAX_YCUOK_MBBL", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "52",
    })
    if r:
        row = _latest(r)
        if row:
            results["cushing_inventory_mb"] = row.get("value")
        results["cushing_history"] = _series(r)

    # Total gasoline stocks
    r = await _get(session, "/petroleum/stoc/wstk/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "WGTSTUS1", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "52",
    })
    if r:
        row = _latest(r)
        if row:
            results["gasoline_inventory_mb"] = row.get("value")
        results["gasoline_history"] = _series(r)

    # Distillate fuel oil stocks
    r = await _get(session, "/petroleum/stoc/wstk/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "WDISTUS1", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "52",
    })
    if r:
        row = _latest(r)
        if row:
            results["distillate_inventory_mb"] = row.get("value")
        results["distillate_history"] = _series(r)

    return results


async def _fetch_gas(session) -> dict:
    results = {}
    # Henry Hub natural gas spot price
    r = await _get(session, "/natural-gas/pri/sum/data/", {
        "frequency": "daily", "data[0]": "value",
        "facets[series][]": "RNGWHHD", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "30",
    })
    if r:
        row = _latest(r)
        if row:
            results["henry_hub_price"] = row.get("value")
            results["henry_hub_date"]  = row.get("period")
        results["henry_hub_history"] = _series(r)

    # US dry gas production
    r = await _get(session, "/natural-gas/prod/sum/data/", {
        "frequency": "monthly", "data[0]": "value",
        "facets[series][]": "N9070US2", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "6",
    })
    if r:
        row = _latest(r)
        if row:
            results["us_production_bcf"] = row.get("value")

    # Natural gas underground working storage (L48 weekly)
    r = await _get(session, "/natural-gas/stor/wkly/data/", {
        "frequency": "weekly", "data[0]": "value",
        "facets[series][]": "NW2_EPG0_SWO_R48_BCF", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "52",
    })
    if r:
        row = _latest(r)
        if row:
            results["gas_storage_bcf"] = row.get("value")
            results["gas_storage_date"] = row.get("period")
        results["gas_storage_history"] = _series(r)

    return results


async def _fetch_electricity(session) -> dict:
    results = {}
    # US retail electricity price (cents/kWh, residential)
    r = await _get(session, "/electricity/retail-sales/data/", {
        "frequency": "monthly", "data[0]": "price",
        "facets[sectorName][]": "residential",
        "facets[stateid][]": "US",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "12",
    })
    if r:
        try:
            data = r["response"]["data"]
            if data:
                results["retail_price_cents_kwh"] = data[0].get("price")
                results["price_date"] = data[0].get("period")
                results["price_history"] = [{"period": d.get("period"), "value": d.get("price")} for d in data]
        except Exception:
            pass

    # US net electricity generation by source (most recent month)
    r = await _get(session, "/electricity/electric-power-operational-data/data/", {
        "frequency": "monthly", "data[0]": "generation",
        "facets[location][]": "US",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "50",
    })
    if r:
        try:
            data = r["response"]["data"]
            by_fuel = {}
            for row in data:
                fuel = row.get("fueltypeid") or row.get("fuelTypeDescription", "")
                val  = row.get("generation")
                if fuel and val and fuel not in by_fuel:
                    by_fuel[fuel] = {"generation_gwh": val, "period": row.get("period")}
            results["by_source"] = by_fuel
        except Exception:
            pass

    return results


async def _fetch_nuclear(session) -> dict:
    results = {}
    # Nuclear generating capacity / output
    r = await _get(session, "/electricity/electric-power-operational-data/data/", {
        "frequency": "monthly", "data[0]": "generation",
        "facets[location][]": "US",
        "facets[fueltypeid][]": "NUC",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": "12",
    })
    if r:
        row = _latest(r)
        if row:
            results["generation_gwh"] = row.get("generation")
            results["period"] = row.get("period")
        results["history"] = _series(r)
    return results


async def _fetch_renewables(session) -> dict:
    results = {}
    for fuel_id, fuel_name in [("SUN", "solar"), ("WND", "wind"), ("HYC", "hydro")]:
        r = await _get(session, "/electricity/electric-power-operational-data/data/", {
            "frequency": "monthly", "data[0]": "generation",
            "facets[location][]": "US",
            "facets[fueltypeid][]": fuel_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc", "length": "12",
        })
        if r:
            row = _latest(r)
            if row:
                results[fuel_name] = {
                    "generation_gwh": row.get("generation"),
                    "period": row.get("period"),
                }
    return results


async def run_poller(interval: int = 3600):
    global _state
    while True:
        if not EIA_KEY:
            _state.error = "Set EIA_API_KEY in .env (free at eia.gov/developer)"
            await asyncio.sleep(3600)
            continue
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloomberg/1.0"}
            ) as session:
                oil, gas, elec, nuc, ren = await asyncio.gather(
                    _fetch_oil(session),
                    _fetch_gas(session),
                    _fetch_electricity(session),
                    _fetch_nuclear(session),
                    _fetch_renewables(session),
                    return_exceptions=True,
                )
                _state.oil         = oil         if isinstance(oil, dict)  else {}
                _state.gas         = gas         if isinstance(gas, dict)  else {}
                _state.electricity = elec        if isinstance(elec, dict) else {}
                _state.nuclear     = nuc         if isinstance(nuc, dict)  else {}
                _state.renewables  = ren         if isinstance(ren, dict)  else {}
                _state.updated     = time.time()
                _state.error       = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
