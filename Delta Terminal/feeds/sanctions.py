"""OFAC Consolidated Sanctions List — US Treasury, free, no key."""
import asyncio, aiohttp, time, csv, io
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SanctionsState:
    entries:  list  = field(default_factory=list)   # [{name, type, program, country}]
    count:    int   = 0
    programs: list  = field(default_factory=list)   # unique program codes
    updated:  float = 0.0
    error:    Optional[str] = None

_state = SanctionsState()

def get_sanctions():
    return _state

SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

async def run_poller(interval: int = 86400):  # once daily — list doesn't change often
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                async with session.get(
                    SDN_CSV_URL, timeout=aiohttp.ClientTimeout(total=60)
                ) as r:
                    if r.status == 200:
                        raw = await r.text(encoding="latin-1")
                        reader = csv.reader(io.StringIO(raw))
                        entries = []
                        programs_seen = set()
                        for row in reader:
                            if len(row) < 4:
                                continue
                            # cols: ent_num, sdn_name, sdn_type, program, ...remarks
                            name    = row[1].strip().strip('"') if len(row) > 1 else ""
                            stype   = row[2].strip().strip('"') if len(row) > 2 else ""
                            program = row[3].strip().strip('"') if len(row) > 3 else ""
                            remarks = row[11].strip().strip('"') if len(row) > 11 else ""
                            country = ""
                            # country often in remarks: "nationality: Iran"
                            for part in remarks.split(";"):
                                p = part.strip().lower()
                                if "nationality" in p or "citizenship" in p:
                                    country = part.split(":")[-1].strip().title()[:30]
                                    break
                            if not name:
                                continue
                            programs_seen.add(program)
                            entries.append({
                                "name":    name[:60],
                                "type":    stype,
                                "program": program,
                                "country": country,
                                "remarks": remarks[:120],
                            })
                        _state.entries  = entries
                        _state.count    = len(entries)
                        _state.programs = sorted(programs_seen - {""})
                        _state.updated  = time.time()
                        _state.error    = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
