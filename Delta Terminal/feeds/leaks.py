"""
Data breach & leak intelligence
Sources:
  - Have I Been Pwned public breach catalog (no key)
    https://haveibeenpwned.com/api/v3/breaches
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

HIBP_BASE = "https://haveibeenpwned.com/api/v3"


@dataclass
class LeaksState:
    breaches:      list          = field(default_factory=list)
    total_pwned:   int           = 0
    by_class:      dict          = field(default_factory=dict)  # data class → count
    updated:       float         = 0.0
    error:         Optional[str] = None


_state = LeaksState()


def get_leaks():
    return _state


async def run_poller(interval: int = 21600):
    global _state
    while True:
        try:
            headers = {
                "User-Agent": "OpenBloombergTerminal/2.0",
                "hibp-api-key": "",  # not required for /breaches catalog
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    f"{HIBP_BASE}/breaches",
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as r:
                    if r.status != 200:
                        raise RuntimeError(f"HTTP {r.status}")
                    raw = await r.json()

            breaches = []
            class_counts: dict = {}
            total_pwned = 0

            for b in raw:
                pwn = b.get("PwnCount", 0) or 0
                total_pwned += pwn
                classes = b.get("DataClasses", [])
                for c in classes:
                    class_counts[c] = class_counts.get(c, 0) + 1

                breaches.append({
                    "name":         b.get("Name", ""),
                    "title":        b.get("Title", ""),
                    "domain":       b.get("Domain", ""),
                    "breach_date":  b.get("BreachDate", ""),
                    "added_date":   (b.get("AddedDate", "") or "")[:10],
                    "pwn_count":    pwn,
                    "data_classes": classes,
                    "verified":     b.get("IsVerified", False),
                    "sensitive":    b.get("IsSensitive", False),
                    "fabricated":   b.get("IsFabricated", False),
                    "retired":      b.get("IsRetired", False),
                    "description":  (b.get("Description", "") or "")[:300],
                })

            # Most recent first
            breaches.sort(key=lambda x: x.get("added_date", ""), reverse=True)

            _state.breaches    = breaches
            _state.total_pwned = total_pwned
            _state.by_class    = dict(sorted(class_counts.items(), key=lambda x: -x[1])[:20])
            _state.updated     = time.time()
            _state.error       = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
