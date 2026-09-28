"""Semantic Scholar Graph API: second citation count, abstracts, TLDRs, open-access PDFs."""

from __future__ import annotations

import os

from ..http import get, today

SOURCE = "Semantic Scholar"
BASE = "https://api.semanticscholar.org/graph/v1"
PAPER_FIELDS = "title,year,venue,citationCount,abstract,tldr,openAccessPdf,externalIds,url,publicationTypes"


def _headers():
    key = os.environ.get("S2_API_KEY")
    return {"x-api-key": key} if key else None


def search_authors(name: str, limit: int = 10) -> dict:
    data = get(
        SOURCE,
        f"{BASE}/author/search",
        params={"query": name, "limit": limit, "fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds,url"},
        headers=_headers(),
    )
    return {"source": SOURCE, "retrieved": today(), "candidates": data.get("data", [])}


def paper(doi: str | None = None, s2_id: str | None = None) -> dict:
    pid = f"DOI:{doi.replace('https://doi.org/', '')}" if doi else s2_id
    p = get(SOURCE, f"{BASE}/paper/{pid}", params={"fields": PAPER_FIELDS}, headers=_headers())
    return {
        "source": SOURCE,
        "retrieved": today(),
        "title": p.get("title"),
        "year": p.get("year"),
        "venue": p.get("venue"),
        "citations_s2": p.get("citationCount"),
        "abstract": p.get("abstract"),
        "tldr": (p.get("tldr") or {}).get("text"),
        "oa_pdf": (p.get("openAccessPdf") or {}).get("url"),
        "external_ids": p.get("externalIds"),
        "url": p.get("url"),
    }
