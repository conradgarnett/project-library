"""Real-time crypto prices via CoinGecko public API — no key required."""

import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

CG_BASE = "https://api.coingecko.com/api/v3"

COIN_IDS = [
    "bitcoin", "ethereum", "solana", "binancecoin", "ripple",
    "cardano", "dogecoin", "avalanche-2", "chainlink", "matic-network",
]

NAMES = {
    "bitcoin":     "Bitcoin",
    "ethereum":    "Ethereum",
    "solana":      "Solana",
    "binancecoin": "BNB",
    "ripple":      "XRP",
    "cardano":     "Cardano",
    "dogecoin":    "Dogecoin",
    "avalanche-2": "Avalanche",
    "chainlink":   "Chainlink",
    "matic-network": "Polygon",
}

SYMBOLS = {
    "bitcoin":     "BTC",
    "ethereum":    "ETH",
    "solana":      "SOL",
    "binancecoin": "BNB",
    "ripple":      "XRP",
    "cardano":     "ADA",
    "dogecoin":    "DOGE",
    "avalanche-2": "AVAX",
    "chainlink":   "LINK",
    "matic-network": "MATIC",
}


@dataclass
class CryptoTick:
    symbol: str
    name: str
    price: float
    change_24h: float
    change_pct_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float
    market_cap: float = 0.0
    updated: float = field(default_factory=time.time)

    @property
    def color(self) -> str:
        return "green" if self.change_pct_24h >= 0 else "red"

    @property
    def arrow(self) -> str:
        return "▲" if self.change_pct_24h >= 0 else "▼"


_store: dict[str, CryptoTick] = {}
_callbacks: list[Callable] = []


def get_crypto() -> dict[str, CryptoTick]:
    return dict(_store)


def subscribe(cb: Callable) -> None:
    _callbacks.append(cb)


def _notify():
    for cb in _callbacks:
        try:
            cb(dict(_store))
        except Exception:
            pass


async def _fetch_once(session: aiohttp.ClientSession):
    ids = ",".join(COIN_IDS)
    url = (
        f"{CG_BASE}/coins/markets"
        f"?vs_currency=usd&ids={ids}"
        f"&order=market_cap_desc&per_page=20&page=1"
        f"&sparkline=false&price_change_percentage=24h"
    )
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status != 200:
            return
        coins = await r.json()

    for coin in coins:
        cid = coin.get("id", "")
        if cid not in NAMES:
            continue
        price  = float(coin.get("current_price") or 0)
        change = float(coin.get("price_change_24h") or 0)
        pct    = float(coin.get("price_change_percentage_24h") or 0)
        _store[cid] = CryptoTick(
            symbol=SYMBOLS.get(cid, cid.upper()),
            name=NAMES[cid],
            price=price,
            change_24h=change,
            change_pct_24h=pct,
            volume_24h=float(coin.get("total_volume") or 0),
            high_24h=float(coin.get("high_24h") or 0),
            low_24h=float(coin.get("low_24h") or 0),
            market_cap=float(coin.get("market_cap") or 0),
        )
    _notify()


async def run_stream(on_update: Optional[Callable] = None):
    """Poll CoinGecko every 30 seconds."""
    if on_update:
        subscribe(on_update)

    async with aiohttp.ClientSession(
        headers={"User-Agent": "OpenBloomberg/1.0"}
    ) as session:
        while True:
            try:
                await _fetch_once(session)
            except Exception:
                pass
            await asyncio.sleep(30)
