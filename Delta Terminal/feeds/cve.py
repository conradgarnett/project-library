"""CVE feed: NIST NVD (no key) + CISA KEV (no key) + Ransomware.live (no key)."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CveState:
    recent:     list = field(default_factory=list)   # latest NVD CVEs
    kev:        list = field(default_factory=list)   # CISA known exploited
    ransomware: list = field(default_factory=list)   # recent ransomware victims
    updated:    float = 0.0
    error:      Optional[str] = None

_state = CveState()

def get_cve():
    return _state

def _severity(score):
    if score is None: return "UNKNOWN"
    if score >= 9.0: return "CRITICAL"
    if score >= 7.0: return "HIGH"
    if score >= 4.0: return "MEDIUM"
    return "LOW"

def _sev_color(score):
    if score is None: return "#446688"
    if score >= 9.0: return "#ff4466"
    if score >= 7.0: return "#ff8800"
    if score >= 4.0: return "#ffaa00"
    return "#00aaff"

async def run_poller(interval: int = 900):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                # NVD CVEs — date filter returns 404; use pagination to get most recent
                try:
                    NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"
                    NVD_HDR = {"User-Agent": "OpenBloombergTerminal/2.0"}
                    # Get total count first
                    async with session.get(f"{NVD}?resultsPerPage=1",
                        timeout=aiohttp.ClientTimeout(total=10), headers=NVD_HDR) as r0:
                        total = (await r0.json()).get("totalResults", 0) if r0.status == 200 else 0
                    start = max(0, total - 30)
                    async with session.get(
                        f"{NVD}?startIndex={start}&resultsPerPage=30",
                        timeout=aiohttp.ClientTimeout(total=20), headers=NVD_HDR
                    ) as r:
                        if r.status == 200:
                            d = await r.json()
                            cves = []
                            for item in reversed(d.get("vulnerabilities", [])):
                                cve = item.get("cve", {})
                                cve_id = cve.get("id", "")
                                desc = next(
                                    (x["value"] for x in cve.get("descriptions", []) if x.get("lang") == "en"),
                                    ""
                                )
                                score = None
                                metrics = cve.get("metrics", {})
                                for mkey in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                                    mlist = metrics.get(mkey, [])
                                    if mlist:
                                        score = mlist[0].get("cvssData", {}).get("baseScore")
                                        break
                                published = cve.get("published", "")[:10]
                                refs = [r2.get("url","") for r2 in cve.get("references", [])[:2]]
                                cves.append({
                                    "id":       cve_id,
                                    "desc":     desc[:160],
                                    "score":    score,
                                    "severity": _severity(score),
                                    "color":    _sev_color(score),
                                    "published":published,
                                    "refs":     refs,
                                })
                            _state.recent = cves
                except Exception:
                    pass

                # CISA KEV
                try:
                    async with session.get(
                        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as r:
                        if r.status == 200:
                            d = await r.json()
                            vulns = d.get("vulnerabilities", [])
                            _state.kev = [
                                {
                                    "id":          v.get("cveID",""),
                                    "vendor":      v.get("vendorProject",""),
                                    "product":     v.get("product",""),
                                    "name":        v.get("vulnerabilityName",""),
                                    "date_added":  v.get("dateAdded",""),
                                    "due_date":    v.get("dueDate",""),
                                    "ransomware":  v.get("knownRansomwareCampaignUse","Unknown"),
                                }
                                for v in sorted(vulns, key=lambda x: x.get("dateAdded",""), reverse=True)[:50]
                            ]
                except Exception:
                    pass

                # Ransomware.live
                try:
                    async with session.get(
                        "https://api.ransomware.live/recentvictims",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            d = await r.json()
                            _state.ransomware = [
                                {
                                    "victim":  v.get("post_title",""),
                                    "group":   v.get("group_name",""),
                                    "country": v.get("country",""),
                                    "date":    v.get("discovered",""),
                                    "website": v.get("website",""),
                                }
                                for v in (d[:30] if isinstance(d, list) else [])
                            ]
                except Exception:
                    pass

            _state.updated = time.time()
            _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
