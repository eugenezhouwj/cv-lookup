"""OpenAlex: author search, works, citation counts and co-author network.

API docs: https://docs.openalex.org
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from ..http import get, today

SOURCE = "OpenAlex"
BASE = "https://api.openalex.org"


def short_id(openalex_id: str) -> str:
    """'https://openalex.org/A123' -> 'A123'."""
    return openalex_id.rstrip("/").rsplit("/", 1)[-1]


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    if not inverted_index:
        return None
    positions = [(pos, word) for word, poss in inverted_index.items() for pos in poss]
    return " ".join(word for _, word in sorted(positions))


def _author_card(a: dict) -> dict:
    insts = a.get("last_known_institutions") or []
    return {
        "openalex_id": short_id(a["id"]),
        "name": a.get("display_name"),
        "orcid": (a.get("orcid") or "").replace("https://orcid.org/", "") or None,
        "institutions": [
            {"name": i.get("display_name"), "country": i.get("country_code")} for i in insts
        ],
        "affiliation_history": [
            {"name": af["institution"].get("display_name"), "years": sorted(af.get("years") or [])}
            for af in a.get("affiliations") or []
        ],
        "works_count": a.get("works_count"),
        "cited_by_count": a.get("cited_by_count"),
        "h_index": (a.get("summary_stats") or {}).get("h_index"),
        "topics": [t.get("display_name") for t in (a.get("topics") or [])[:8]],
    }


def search_authors(name: str, affiliation: str | None = None, limit: int = 10) -> dict:
    data = get(SOURCE, f"{BASE}/authors", params={"search": name, "per-page": limit})
    cards = [_author_card(a) for a in data.get("results", [])]
    if affiliation:
        needle = affiliation.lower()

        def matches(c):
            names = [i["name"] or "" for i in c["institutions"]]
            names += [h["name"] or "" for h in c["affiliation_history"]]
            return any(needle in n.lower() for n in names)

        for c in cards:
            c["affiliation_match"] = matches(c)
        cards.sort(key=lambda c: (not c["affiliation_match"], -(c["works_count"] or 0)))
    return {"source": SOURCE, "retrieved": today(), "query": name, "candidates": cards}


def get_author(author_id: str) -> dict:
    a = get(SOURCE, f"{BASE}/authors/{short_id(author_id)}")
    return {"source": SOURCE, "retrieved": today(), "author": _author_card(a)}


def _work(w: dict, author_id: str | None = None) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    authorships = w.get("authorships") or []
    return {
        "openalex_id": short_id(w["id"]),
        "title": w.get("display_name") or w.get("title"),
        "year": w.get("publication_year"),
        "date": w.get("publication_date"),
        "type": w.get("type"),
        "venue": src.get("display_name"),
        "venue_type": src.get("type"),
        "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
        "url": w.get("doi") or loc.get("landing_page_url"),
        "oa_url": (w.get("open_access") or {}).get("oa_url"),
        "cited_by_count": w.get("cited_by_count"),
        "authors": [
            {
                "name": au["author"].get("display_name"),
                "openalex_id": short_id(au["author"]["id"]) if au["author"].get("id") else None,
                "institutions": [
                    {"name": i.get("display_name"), "country": i.get("country_code")}
                    for i in au.get("institutions") or []
                ],
            }
            for au in authorships
        ],
        "funders": sorted(
            {f.get("funder_display_name") or f.get("display_name") for f in (w.get("grants") or []) + (w.get("funders") or [])}
            - {None}
        ),
        "abstract": reconstruct_abstract(w.get("abstract_inverted_index")),
    }


def _works(filter_: str, sort: str, max_results: int) -> list[dict]:
    out, cursor = [], "*"
    while cursor and len(out) < max_results:
        data = get(
            SOURCE,
            f"{BASE}/works",
            params={"filter": filter_, "sort": sort, "per-page": min(200, max_results), "cursor": cursor},
        )
        out.extend(data.get("results", []))
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not data.get("results"):
            break
    return out[:max_results]


def recent_works(author_id: str, years: int = 3, max_results: int = 200) -> dict:
    since = dt.date(dt.date.today().year - years + 1, 1, 1).isoformat()
    aid = short_id(author_id)
    raw = _works(f"author.id:{aid},from_publication_date:{since}", "publication_date:desc", max_results)
    return {
        "source": SOURCE,
        "retrieved": today(),
        "author_id": aid,
        "since": since,
        "works": [_work(w) for w in raw],
    }


def top_cited(author_id: str, n: int = 5) -> dict:
    aid = short_id(author_id)
    raw = _works(f"author.id:{aid}", "cited_by_count:desc", n)
    return {"source": SOURCE, "retrieved": today(), "author_id": aid, "works": [_work(w) for w in raw]}


def all_works(author_id: str, max_results: int = 1000) -> list[dict]:
    return [_work(w) for w in _works(f"author.id:{short_id(author_id)}", "publication_date:desc", max_results)]


def coauthors(author_id: str, top: int = 15, max_works: int = 1000) -> dict:
    aid = short_id(author_id)
    works = all_works(aid, max_works)
    counts: Counter = Counter()
    info: dict = {}
    for w in works:
        seen = set()
        for au in w["authors"]:
            cid = au["openalex_id"]
            if not cid or cid == aid or cid in seen:
                continue
            seen.add(cid)
            counts[cid] += 1
            entry = info.setdefault(cid, {"name": au["name"], "institutions": set(), "years": set()})
            entry["institutions"].update(i["name"] for i in au["institutions"] if i["name"])
            entry["sg"] = entry.get("sg", False) or any(i["country"] == "SG" for i in au["institutions"])
            if w["year"]:
                entry["years"].add(w["year"])
    ranked = []
    for cid, n in counts.most_common(top):
        e = info[cid]
        ranked.append(
            {
                "openalex_id": cid,
                "name": e["name"],
                "joint_works": n,
                "institutions": sorted(e["institutions"]),
                "first_year": min(e["years"]) if e["years"] else None,
                "last_year": max(e["years"]) if e["years"] else None,
                "singapore_affiliated": e["sg"],
            }
        )
    return {
        "source": SOURCE,
        "retrieved": today(),
        "author_id": aid,
        "works_scanned": len(works),
        "coauthors": ranked,
        "note": "Institutions are those listed on the joint works, not necessarily current affiliations.",
    }
