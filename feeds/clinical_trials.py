"""ClinicalTrials.gov API v2 — free, no auth required.

Fetches top 100 most recently updated RECRUITING studies.
Uses requests (not aiohttp) in a thread executor — CT blocks HTTP/2 clients.
"""
import asyncio
import requests
import time
from dataclasses import dataclass, field
from typing import Optional

CT_BASE = "https://clinicaltrials.gov/api/v2"

# requests session is shared and reused across polls
_session = requests.Session()
_session.headers.update({
    "User-Agent": "python-requests/2.31.0",
    "Accept": "application/json",
})

PHASE_LABEL = {
    "EARLY_PHASE1": "Early Ph1",
    "PHASE1":       "Ph1",
    "PHASE2":       "Ph2",
    "PHASE3":       "Ph3",
    "PHASE4":       "Ph4",
    "NA":           "N/A",
}


@dataclass
class ClinicalTrialsState:
    studies:      list = field(default_factory=list)
    by_condition: dict = field(default_factory=dict)
    total:        int  = 0
    updated:      float = 0.0
    error:        Optional[str] = None


_state = ClinicalTrialsState()


def get_clinical_trials():
    return _state


def _extract(s: dict) -> dict:
    pm  = s.get("protocolSection", {})
    im  = pm.get("identificationModule", {})
    sm  = pm.get("statusModule", {})
    cm  = pm.get("conditionsModule", {})
    dm  = pm.get("designModule", {})
    spm = pm.get("sponsorCollaboratorsModule", {})
    aim = pm.get("armsInterventionsModule", {})

    nct_id = im.get("nctId", "")
    phases = dm.get("phases", [])
    phase_labels = [PHASE_LABEL.get(p, p) for p in phases]

    interventions = [
        i.get("name", "") for i in aim.get("interventions", [])[:3]
        if i.get("name")
    ]

    return {
        "nct_id":        nct_id,
        "title":         im.get("briefTitle", ""),
        "status":        sm.get("overallStatus", ""),
        "conditions":    cm.get("conditions", [])[:3],
        "phases":        phase_labels,
        "phase_label":   "/".join(phase_labels) if phase_labels else "N/A",
        "sponsor":       spm.get("leadSponsor", {}).get("name", ""),
        "sponsor_class": spm.get("leadSponsor", {}).get("class", ""),
        "interventions": interventions,
        "updated":       sm.get("lastUpdatePostDateStruct", {}).get("date", ""),
        "start_date":    sm.get("startDateStruct", {}).get("date", ""),
        "url":           f"https://clinicaltrials.gov/study/{nct_id}",
    }


def _fetch_blocking() -> dict:
    params = {
        "pageSize": 100,
        "sort": "LastUpdatePostDate:desc",
        "filter.overallStatus": "RECRUITING",
    }
    r = _session.get(f"{CT_BASE}/studies", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


async def run_poller(interval: int = 3600):
    global _state
    loop = asyncio.get_event_loop()
    while True:
        try:
            data = await loop.run_in_executor(None, _fetch_blocking)

            studies = [_extract(s) for s in data.get("studies", [])]

            by_condition: dict[str, int] = {}
            for s in studies:
                for cond in s["conditions"][:1]:
                    key = cond[:40]
                    by_condition[key] = by_condition.get(key, 0) + 1
            by_condition = dict(
                sorted(by_condition.items(), key=lambda x: -x[1])[:25]
            )

            _state.studies      = studies
            _state.by_condition = by_condition
            _state.total        = len(studies)
            _state.updated      = time.time()
            _state.error        = None

        except Exception as exc:
            _state.error = str(exc)

        await asyncio.sleep(interval)
