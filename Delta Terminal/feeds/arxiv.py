"""arXiv preprint feed — free, no API key. Categories: AI/ML/NLP/CV/Bio."""

import asyncio
import aiohttp
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

ARXIV_BASE = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

CATEGORIES = {
    "ai":   "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV",
    "bio":  "cat:q-bio.BM OR cat:q-bio.GN OR cat:q-bio.NC OR cat:q-bio.PE",
    "quant":"cat:quant-ph OR cat:cond-mat.supr-con OR cat:cond-mat.mes-hall",
    "rob":  "cat:cs.RO OR cat:cs.SY OR cat:eess.SY",
    "sem":  "cat:cs.AR OR cat:eess.SP OR cat:physics.app-ph",
}


@dataclass
class Paper:
    arxiv_id:   str
    title:      str
    authors:    list
    summary:    str
    published:  str
    updated:    str
    categories: list
    pdf_url:    str


@dataclass
class ArxivState:
    ai:      list = field(default_factory=list)
    bio:     list = field(default_factory=list)
    quant:   list = field(default_factory=list)
    rob:     list = field(default_factory=list)
    sem:     list = field(default_factory=list)
    updated: float = 0.0
    error:   Optional[str] = None


_state = ArxivState()


def get_arxiv():
    return _state


def _parse_feed(xml_bytes: bytes) -> list[Paper]:
    root = ET.fromstring(xml_bytes)
    papers = []
    for entry in root.findall("atom:entry", NS):
        def txt(tag):
            el = entry.find(tag, NS)
            return (el.text or "").strip() if el is not None else ""

        arxiv_id = txt("atom:id").split("/abs/")[-1]
        title    = txt("atom:title").replace("\n", " ").strip()
        summary  = txt("atom:summary").replace("\n", " ").strip()[:400]
        published = txt("atom:published")[:10]
        updated   = txt("atom:updated")[:10]

        authors = [
            (a.find("atom:name", NS).text or "").strip()
            for a in entry.findall("atom:author", NS)
        ][:4]

        cats = [c.get("term", "") for c in entry.findall("atom:category", NS)]

        pdf_url = ""
        for link in entry.findall("atom:link", NS):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")

        if title and arxiv_id:
            papers.append(Paper(arxiv_id, title, authors, summary, published, updated, cats, pdf_url))
    return papers


async def _fetch(session: aiohttp.ClientSession, query: str, n: int = 50) -> list[Paper]:
    try:
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(n),
        }
        async with session.get(ARXIV_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return _parse_feed(await r.read())
    except Exception:
        pass
    return []


async def run_poller(interval: int = 21600):  # 6 hours
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            try:
                ai_papers, bio_papers, quant_papers, rob_papers, sem_papers = await asyncio.gather(
                    _fetch(session, CATEGORIES["ai"],    60),
                    _fetch(session, CATEGORIES["bio"],   30),
                    _fetch(session, CATEGORIES["quant"], 30),
                    _fetch(session, CATEGORIES["rob"],   30),
                    _fetch(session, CATEGORIES["sem"],   30),
                )
                _state.ai      = [vars(p) for p in ai_papers]
                _state.bio     = [vars(p) for p in bio_papers]
                _state.quant   = [vars(p) for p in quant_papers]
                _state.rob     = [vars(p) for p in rob_papers]
                _state.sem     = [vars(p) for p in sem_papers]
                _state.updated = time.time()
                _state.error   = None
            except Exception as e:
                _state.error = str(e)
            # Retry in 60s if empty (startup throttle), otherwise full 6h interval
            await asyncio.sleep(60 if not _state.ai else interval)
