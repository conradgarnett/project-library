"""Global yfinance throttle — enforces max 1 concurrent Yahoo Finance request
with 350ms minimum gap between calls, shared across all feeds.

Without this every feed hammers yfinance at startup in parallel, triggering
Yahoo's IP-level rate limit (YFRateLimitError) that can last 30-60 minutes.
When a rate limit IS hit, backs off 90 seconds before retrying.
"""
import asyncio
import time

_lock: asyncio.Lock | None = None
_last_call: float = 0.0
_rate_limited_until: float = 0.0
_MIN_GAP = 0.35          # seconds between yfinance requests
_RATE_LIMIT_BACKOFF = 90 # seconds to wait after a Yahoo rate-limit response


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _is_rate_limit(exc: Exception) -> bool:
    name = type(exc).__name__
    msg  = str(exc).lower()
    return (
        "RateLimit" in name
        or "ratelimit" in msg
        or "too many requests" in msg
        or "rate limit" in msg
    )


async def run(fn, *args):
    """Await this instead of loop.run_in_executor(None, fn, *args).
    Serialises all yfinance calls, enforces minimum inter-call gap, and
    automatically backs off on Yahoo rate-limit responses."""
    global _last_call, _rate_limited_until
    lock = _get_lock()
    async with lock:
        # Honour any active rate-limit cooldown period
        now = time.time()
        if now < _rate_limited_until:
            await asyncio.sleep(_rate_limited_until - now)

        # Minimum gap between successive calls
        now = time.time()
        gap = _last_call + _MIN_GAP - now
        if gap > 0:
            await asyncio.sleep(gap)

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, fn, *args)
            _last_call = time.time()
            return result
        except Exception as e:
            _last_call = time.time()
            if _is_rate_limit(e):
                _rate_limited_until = time.time() + _RATE_LIMIT_BACKOFF
            raise
