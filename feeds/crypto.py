"""Real-time crypto prices via Binance public WebSocket — no API key required."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
import websockets

SYMBOLS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt", "xrpusdt",
           "adausdt", "dogeusdt", "avaxusdt", "linkusdt", "maticusdt"]

NAMES = {
    "btcusdt": "Bitcoin", "ethusdt": "Ethereum", "solusdt": "Solana",
    "bnbusdt": "BNB", "xrpusdt": "XRP", "adausdt": "Cardano",
    "dogeusdt": "Dogecoin", "avaxusdt": "Avalanche", "linkusdt": "Chainlink",
    "maticusdt": "Polygon",
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


async def run_stream(on_update: Optional[Callable] = None):
    """Connect to Binance combined stream and keep it alive."""
    if on_update:
        subscribe(on_update)

    stream_names = "/".join(f"{s}@ticker" for s in SYMBOLS)
    url = f"wss://stream.binance.com:9443/stream?streams={stream_names}"

    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                async for msg in ws:
                    data = json.loads(msg)
                    tick = data.get("data", {})
                    sym  = tick.get("s", "").lower()
                    if sym not in NAMES:
                        continue
                    price  = float(tick.get("c", 0))
                    open_  = float(tick.get("o", price))
                    change = price - open_
                    pct    = (change / open_ * 100) if open_ else 0
                    _store[sym] = CryptoTick(
                        symbol=sym.upper(),
                        name=NAMES[sym],
                        price=price,
                        change_24h=change,
                        change_pct_24h=pct,
                        volume_24h=float(tick.get("v", 0)),
                        high_24h=float(tick.get("h", 0)),
                        low_24h=float(tick.get("l", 0)),
                    )
                    _notify()
        except Exception:
            await asyncio.sleep(5)
