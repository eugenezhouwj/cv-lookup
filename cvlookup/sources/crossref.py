"""Crossref: authoritative publisher metadata for a DOI (primary source for verification)."""

from __future__ import annotations

import re
from urllib.parse import quote

from ..http import get, today

SOURCE = "Crossref"
BASE = "https://api.crossref.org"


def _strip_jats(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _year(msg: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            return parts[0][0]
    return None


def work(doi: str) -> dict:
    doi = doi.replace("https://doi.org/", "").strip()
    msg = get(SOURCE, f"{BASE}/works/{quote(doi, safe='/')}")["message"]
    return {
        "source": SOURCE,
        "retrieved": today(),
        "doi": msg.get("DOI"),
        "url": f"https://doi.org/{msg.get('DOI')}",
        "title": (msg.get("title") or [None])[0],
        "authors": [
            {
                "name": " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name"),
                "orcid": (a.get("ORCID") or "").rsplit("/", 1)[-1] or None,
                "affiliations": [af.get("name") for af in a.get("affiliation") or []],
            }
            for a in msg.get("author") or []
        ],
        "venue": (msg.get("container-title") or [None])[0],
        "publisher": msg.get("publisher"),
        "type": msg.get("type"),
        "year": _year(msg),
        "citations_crossref": msg.get("is-referenced-by-count"),
        "funders": [f.get("name") for f in msg.get("funder") or []],
        "abstract": _strip_jats(msg.get("abstract")),
        "relations": {k: [r.get("id") for r in v] for k, v in (msg.get("relation") or {}).items()},
    }


def search(title: str, author: str | None = None, rows: int = 5) -> dict:
    params = {"query.bibliographic": title, "rows": rows}
    if author:
        params["query.author"] = author
    items = get(SOURCE, f"{BASE}/works", params=params)["message"].get("items", [])
    return {
        "source": SOURCE,
        "retrieved": today(),
        "results": [
            {
                "doi": it.get("DOI"),
                "title": (it.get("title") or [None])[0],
                "venue": (it.get("container-title") or [None])[0],
                "year": _year(it),
                "type": it.get("type"),
                "authors": [" ".join(p for p in (a.get("given"), a.get("family")) if p) for a in it.get("author") or []],
            }
            for it in items
        ],
    }
