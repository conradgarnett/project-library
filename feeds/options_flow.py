"""
Unusual options activity — yfinance options chains, no API key.

Flags contracts where today's volume is unusually high relative to open interest,
which can signal institutional positioning or expected moves.
"""
import asyncio, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class OptionsFlowState:
    unusual:  list  = field(default_factory=list)   # sorted by vol/OI desc
    summary:  list  = field(default_factory=list)   # per-ticker aggregates
    updated:  float = 0.0
    error:    Optional[str] = None

_state = OptionsFlowState()

def get_options_flow():
    return _state

# Tickers to scan — large-cap + high-options-volume names
WATCHLIST = [
    "SPY","QQQ","IWM","DIA",                        # index ETFs
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA",  # mega-cap
    "AMD","INTC","AVGO","QCOM",                      # semis
    "JPM","GS","BAC","MS",                           # banks
    "COIN","MSTR","HOOD",                            # crypto proxies
    "PLTR","SOFI","RBLX",                            # high-IV names
    "GLD","SLV","USO","UNG",                         # commodities ETFs
    "VIX",                                           # volatility
]

MIN_VOLUME    = 500     # minimum contracts traded today
VOL_OI_RATIO  = 0.5     # volume must be ≥50% of open interest
MIN_PREMIUM   = 0.10    # contract price at least $0.10

def _scan_ticker(symbol: str) -> list:
    """Synchronous yfinance scan for one ticker."""
    rows = []
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        exps = t.options[:4]   # next 4 expirations
        for exp in exps:
            try:
                chain = t.option_chain(exp)
            except Exception:
                continue
            for flag, df in [("C", chain.calls), ("P", chain.puts)]:
                if df is None or df.empty:
                    continue
                for _, row in df.iterrows():
                    vol = row.get("volume", 0) or 0
                    oi  = row.get("openInterest", 0) or 0
                    bid = row.get("bid", 0) or 0
                    ask = row.get("ask", 0) or 0
                    mid = (bid + ask) / 2
                    iv  = row.get("impliedVolatility", 0) or 0

                    if vol < MIN_VOLUME:
                        continue
                    if oi > 0 and vol / oi < VOL_OI_RATIO:
                        continue
                    if mid < MIN_PREMIUM:
                        continue

                    rows.append({
                        "ticker":      symbol,
                        "type":        flag,
                        "expiry":      exp,
                        "strike":      float(row.get("strike", 0)),
                        "bid":         round(float(bid), 2),
                        "ask":         round(float(ask), 2),
                        "mid":         round(float(mid), 2),
                        "volume":      int(vol),
                        "open_int":    int(oi),
                        "vol_oi":      round(vol / oi, 2) if oi > 0 else 999,
                        "iv_pct":      round(float(iv) * 100, 1),
                        "itm":         bool(row.get("inTheMoney", False)),
                        "premium_k":   round(mid * 100 * int(vol) / 1000, 1),  # total $ premium in $k
                    })
    except Exception:
        pass
    return rows

async def run_poller(interval: int = 900):  # 15 min — options data is slow to change
    global _state
    while True:
        try:
            all_rows = []
            ticker_summary = {}

            loop = asyncio.get_event_loop()
            for sym in WATCHLIST:
                rows = await loop.run_in_executor(None, _scan_ticker, sym)
                all_rows.extend(rows)
                if rows:
                    calls = [r for r in rows if r["type"] == "C"]
                    puts  = [r for r in rows if r["type"] == "P"]
                    ticker_summary[sym] = {
                        "ticker":    sym,
                        "calls":     len(calls),
                        "puts":      len(puts),
                        "put_call":  round(len(puts) / len(calls), 2) if calls else 999,
                        "max_vol":   max((r["volume"] for r in rows), default=0),
                        "top_prem":  max((r["premium_k"] for r in rows), default=0),
                    }
                await asyncio.sleep(0.3)  # gentle rate limiting

            # sort by total premium descending — biggest money moves first
            all_rows.sort(key=lambda r: r["premium_k"], reverse=True)

            _state.unusual  = all_rows[:150]
            _state.summary  = sorted(ticker_summary.values(), key=lambda x: x["max_vol"], reverse=True)
            _state.updated  = time.time()
            _state.error    = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
