"""SEC EDGAR — insider trades (Form 4), material events (8-K), and earnings filings.
Free, no API key required. Rate limit: 10 req/sec per SEC fair-use policy.
"""
import asyncio, aiohttp, time, re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

SEC_BASE    = "https://data.sec.gov"
EFTS_BASE   = "https://efts.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
UA          = {"User-Agent": "OpenBloomberg terminal@openbloomberg.dev"}

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META",
    "AMZN", "TSLA", "AMD",  "NFLX",  "AVGO",
    "ORCL", "CRM",  "JPM",  "GS",    "BAC",
    "XOM",  "CVX",  "UNH",  "LLY",   "V",
]

# Hardcoded CIKs for watchlist — fallback if company_tickers.json is unreachable at startup
FALLBACK_CIKS = {
    "AAPL": "0000320193", "MSFT": "0000789019", "NVDA": "0001045810",
    "GOOGL":"0001652044", "META": "0001326801", "AMZN": "0001018724",
    "TSLA": "0001318605", "AMD":  "0000002488", "NFLX": "0001065280",
    "AVGO": "0001730168", "ORCL": "0001341439", "CRM":  "0001108524",
    "JPM":  "0000019617", "GS":   "0000886982", "BAC":  "0000070858",
    "XOM":  "0000034088", "CVX":  "0000093410", "UNH":  "0000731766",
    "LLY":  "0000059478", "V":    "0001403161",
}

TRANSACTION_CODES = {
    "P": "BUY",  "S": "SELL", "A": "AWARD", "D": "DISPOSE",
    "F": "TAX",  "M": "EXERCISE", "C": "CONVERT", "G": "GIFT",
    "I": "INHERIT", "J": "OTHER",
}


@dataclass
class InsiderTrade:
    ticker:       str
    company:      str
    insider_name: str
    role:         str
    action:       str        # BUY / SELL / AWARD / …
    shares:       float
    price:        Optional[float]
    value_usd:    Optional[float]
    date:         str
    filing_url:   str


@dataclass
class Filing:
    ticker:    str
    company:   str
    form:      str
    date:      str
    title:     str
    url:       str


@dataclass
class EdgarState:
    insider_trades: list  = field(default_factory=list)  # recent Form 4
    filings_8k:     list  = field(default_factory=list)  # recent 8-K
    filings_10q:    list  = field(default_factory=list)  # recent 10-Q/10-K
    cik_map:        dict  = field(default_factory=dict)  # ticker → CIK str
    updated:        float = 0.0
    error:          Optional[str] = None


_state = EdgarState()


def get_edgar():
    return _state


# ── CIK lookup ────────────────────────────────────────────────────────────────

async def _load_cik_map(session: aiohttp.ClientSession) -> dict:
    try:
        async with session.get(TICKERS_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return {}
            data = await r.json(content_type=None)
            return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}
    except Exception:
        return {}


# ── Submissions (Form 4, 8-K, 10-Q) ──────────────────────────────────────────

async def _fetch_submissions(session: aiohttp.ClientSession, cik: str) -> dict:
    try:
        url = f"{SEC_BASE}/submissions/CIK{cik}.json"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return {}
            return await r.json(content_type=None)
    except Exception:
        return {}


def _parse_submissions(ticker: str, data: dict, cutoff_days: int = 60) -> tuple:
    """Extract recent 8-K and 10-Q/K filings. Returns (eightk_list, earnings_list)."""
    recent   = data.get("filings", {}).get("recent", {})
    forms    = recent.get("form", [])
    dates    = recent.get("filingDate", [])
    accns    = recent.get("accessionNumber", [])
    descs    = recent.get("primaryDocDescription", [])
    docs     = recent.get("primaryDocument", [])
    company  = data.get("name", ticker)
    cik_raw  = str(data.get("cik", "")).zfill(10)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=cutoff_days)).strftime("%Y-%m-%d")
    eightks, earnings = [], []

    for i, (form, date, accn) in enumerate(zip(forms, dates, accns)):
        if date < cutoff:
            continue
        accn_clean = accn.replace("-", "")
        doc = docs[i] if i < len(docs) else ""
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_raw)}/{accn_clean}/{doc}"

        if form == "8-K":
            desc = descs[i] if i < len(descs) else ""
            eightks.append(Filing(
                ticker=ticker, company=company, form="8-K",
                date=date, title=desc or "Material Event", url=url,
            ))

        elif form in ("10-Q", "10-K"):
            earnings.append(Filing(
                ticker=ticker, company=company, form=form,
                date=date, title=f"{form} — {company}", url=url,
            ))

    return eightks, earnings


# ── Form 4 discovery via EDGAR company Atom feed ──────────────────────────────
# Form 4 filings are filed by INSIDERS under their own CIK, not the company's.
# The company submissions endpoint only shows company-filed documents.
# The Atom feed endpoint returns Form 4 filings where the company is the ISSUER.

async def _form4_atom(session: aiohttp.ClientSession, cik_int: int, ticker: str,
                       company: str, cutoff: str) -> list[dict]:
    """Fetch recent Form 4 filings for a company (as issuer) via EDGAR Atom feed."""
    url = (f"https://www.sec.gov/cgi-bin/browse-edgar"
           f"?action=getcompany&CIK={cik_int}&type=4"
           f"&dateb=&owner=include&count=5&output=atom")
    metas = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return metas
            text = await r.text()

        for entry in re.findall(r'<content[^>]*>(.*?)</content>', text, re.DOTALL):
            accn_m = re.search(r'<accession-number>(.*?)</accession-number>', entry)
            date_m = re.search(r'<filing-date>([\d-]+)</filing-date>', entry)
            href_m = re.search(r'<filing-href>(.*?)</filing-href>', entry)
            if not accn_m or not date_m:
                continue
            date = date_m.group(1)
            if date < cutoff:
                continue
            accn = accn_m.group(1).strip()
            accn_clean = accn.replace("-", "")
            # CIK in filing path is the COMPANY's CIK (files stored under issuer, not insider)
            href = href_m.group(1).strip() if href_m else ""
            cik_m = re.search(r'/data/(\d+)/', href)
            file_cik = cik_m.group(1) if cik_m else str(cik_int)
            metas.append({
                "ticker":  ticker,
                "company": company,
                "cik":     str(file_cik).zfill(10),
                "accn":    accn,
                "date":    date,
                "url":     f"https://www.sec.gov/Archives/edgar/data/{file_cik}/{accn_clean}/",
            })
    except Exception:
        pass
    return metas


# ── Form 4 XML parsing ────────────────────────────────────────────────────────

def _xml_val(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


async def _parse_form4(session: aiohttp.ClientSession, meta: dict) -> list[InsiderTrade]:
    """Fetch and parse a Form 4 XML filing, returning insider transaction records."""
    trades = []
    try:
        cik_int = int(meta["cik"])
        accn = meta["accn"]          # e.g. "0001140361-26-020871"
        accn_clean = accn.replace("-", "")  # "000114036126020871"
        # Full submission text is at {CIK}/{accn_clean}/{accn}.txt (subdirectory form)
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_clean}/{accn}.txt"

        async with session.get(xml_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return trades
            text = await r.text()

        # Extract issuer info
        company  = _xml_val(text, "issuerName")   or meta["company"]
        symbol   = _xml_val(text, "issuerTradingSymbol") or meta["ticker"]

        # Extract reporter info
        insider  = _xml_val(text, "rptOwnerName")
        role_raw = _xml_val(text, "officerTitle") or _xml_val(text, "isDirector")
        def _is_true(tag): return _xml_val(text, tag) in ("1", "true")
        if _is_true("isOfficer"):
            role = _xml_val(text, "officerTitle") or "Officer"
        elif _is_true("isDirector"):
            role = "Director"
        elif _is_true("isTenPercentOwner"):
            role = "10% Owner"
        else:
            role = "Insider"

        # Extract all non-derivative transactions
        tx_blocks = re.findall(
            r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>",
            text, re.DOTALL | re.IGNORECASE
        )
        for block in tx_blocks:
            code   = _xml_val(block, "transactionCode")
            shares_s = _xml_val(block, "transactionShares")
            price_s  = _xml_val(block, "transactionPricePerShare")
            tx_date_raw = _xml_val(block, "transactionDate") or meta["date"]
            # date is nested: <transactionDate><value>2026-05-11</value></transactionDate>
            tx_date_v = re.search(r"<value>([\d-]+)</value>", tx_date_raw)
            tx_date = tx_date_v.group(1) if tx_date_v else tx_date_raw[:10]
            # value tags sometimes nested
            shares_v = re.search(r"<value>([\d.]+)</value>", shares_s)
            price_v  = re.search(r"<value>([\d.]+)</value>", price_s)
            try:
                shares = float(shares_v.group(1)) if shares_v else float(shares_s)
            except Exception:
                continue
            try:
                price  = float(price_v.group(1)) if price_v else (float(price_s) if price_s else None)
            except Exception:
                price = None

            action = TRANSACTION_CODES.get(code, code or "UNKNOWN")
            if action not in ("BUY", "SELL"):   # skip awards, disposals, etc. for noise
                continue
            if shares < 1:
                continue

            trades.append(InsiderTrade(
                ticker=symbol or meta["ticker"],
                company=company,
                insider_name=insider,
                role=role,
                action=action,
                shares=shares,
                price=price,
                value_usd=round(shares * price, 0) if price else None,
                date=tx_date,
                filing_url=meta["url"],
            ))
    except Exception:
        pass
    return trades


# ── Main poller ───────────────────────────────────────────────────────────────

async def run_poller(interval: int = 3600):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(headers=UA) as session:
                # Load CIK map
                cik_map = await _load_cik_map(session)
                if not cik_map:
                    cik_map = _state.cik_map if _state.cik_map else dict(FALLBACK_CIKS)

                all_form4_meta = []
                all_8k:  list[Filing] = []
                all_10q: list[Filing] = []
                cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

                for ticker in WATCHLIST:
                    cik = cik_map.get(ticker)
                    if not cik:
                        continue
                    cik_int = int(cik)

                    # 8-K / 10-Q from company submissions
                    subs = await _fetch_submissions(session, cik)
                    if subs:
                        company_name = subs.get("name", ticker)
                        eightks, earnings = _parse_submissions(ticker, subs, cutoff_days=60)
                        all_8k.extend(eightks)
                        all_10q.extend(earnings)
                    else:
                        company_name = ticker
                    await asyncio.sleep(0.12)

                    # Form 4 from Atom feed (insider trades by issuer)
                    f4s = await _form4_atom(session, cik_int, ticker, company_name, cutoff)
                    all_form4_meta.extend(f4s)
                    await asyncio.sleep(0.12)

                # Parse Form 4 XMLs sequentially to stay under SEC's 10 req/sec limit
                # 5 per company × 20 companies = 100 max, ~12s at 0.12s spacing
                all_form4_meta.sort(key=lambda x: x["date"], reverse=True)
                all_trades = []
                for m in all_form4_meta:
                    trades = await _parse_form4(session, m)
                    all_trades.extend(trades)
                    await asyncio.sleep(0.12)

                # Keep only trades for our watchlist tickers (filters stale CIK reuse)
                watchlist_set = set(WATCHLIST)
                all_trades = [t for t in all_trades if t.ticker in watchlist_set]

                # Sort: most recent first
                all_trades.sort(key=lambda t: t.date, reverse=True)
                all_8k.sort(key=lambda f: f.date, reverse=True)
                all_10q.sort(key=lambda f: f.date, reverse=True)

                _state.cik_map        = cik_map
                _state.insider_trades = all_trades[:200]
                _state.filings_8k     = all_8k[:50]
                _state.filings_10q    = all_10q[:30]
                _state.updated        = time.time()
                _state.error          = None

        except Exception as e:
            _state.error = str(e)

        await asyncio.sleep(interval)
