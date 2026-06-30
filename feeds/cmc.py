"""CoinMarketCap — top 100 cryptocurrencies with full market data."""

import asyncio
import aiohttp
import time
import os
from dataclasses import dataclass, field
from typing import Optional

CMC_KEY = os.environ.get("CMC_KEY", "")
BASE = "https://pro-api.coinmarketcap.com"


@dataclass
class CmcState:
    coins:   list = field(default_factory=list)
    updated: float = 0.0
    error:   Optional[str] = None


_state = CmcState()


def get_cmc() -> CmcState:
    return _state


async def _fetch(session: aiohttp.ClientSession) -> None:
    global _state
    url = f"{BASE}/v1/cryptocurrency/listings/latest?limit=100&convert=USD"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
        if r.status != 200:
            _state.error = f"CMC HTTP {r.status}"
            return
        d = await r.json()
        coins = []
        for c in d.get("data", []):
            q = c["quote"]["USD"]
            coins.append({
                "rank":       c["cmc_rank"],
                "symbol":     c["symbol"],
                "name":       c["name"],
                "price":      q.get("price"),
                "change_1h":  q.get("percent_change_1h"),
                "change_24h": q.get("percent_change_24h"),
                "change_7d":  q.get("percent_change_7d"),
                "market_cap": q.get("market_cap"),
                "volume_24h": q.get("volume_24h"),
                "dominance":  q.get("market_cap_dominance"),
                "supply":     c.get("circulating_supply"),
                "max_supply": c.get("max_supply"),
            })
        _state.coins = coins
        _state.updated = time.time()
        _state.error = None


async def run_poller(interval: int = 300):
    if not CMC_KEY:
        _state.error = "No CMC_KEY"
        return
    headers = {"X-CMC_PRO_API_KEY": CMC_KEY, "Accept": "application/json"}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            try:
                await _fetch(session)
            except Exception as e:
                _state.error = str(e)
            await asyncio.sleep(interval)
