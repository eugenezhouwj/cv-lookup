"""ORCID public API: self-/institution-asserted employment, education, distinctions, etc."""

from __future__ import annotations

from ..http import get, today

SOURCE = "ORCID"
BASE = "https://pub.orcid.org/v3.0"
JSON = {"Accept": "application/json"}

SECTIONS = [
    "employments",
    "educations",
    "qualifications",
    "distinctions",
    "invited-positions",
    "memberships",
    "services",
]


def _date(d: dict | None) -> str | None:
    if not d:
        return None
    parts = [(d.get(k) or {}).get("value") for k in ("year", "month", "day")]
    return "-".join(p for p in parts if p) or None


def _affiliations(section: dict | None) -> list[dict]:
    out = []
    for group in (section or {}).get("affiliation-group", []) or []:
        for summary in group.get("summaries", []) or []:
            s = next(iter(summary.values()))  # e.g. {"employment-summary": {...}}
            org = s.get("organization") or {}
            addr = org.get("address") or {}
            out.append(
                {
                    "organization": org.get("name"),
                    "department": s.get("department-name"),
                    "role": s.get("role-title"),
                    "start": _date(s.get("start-date")),
                    "end": _date(s.get("end-date")),
                    "city": addr.get("city"),
                    "country": addr.get("country"),
                    "asserted_by": ((s.get("source") or {}).get("source-name") or {}).get("value"),
                }
            )
    return out


def record(orcid: str) -> dict:
    orcid = orcid.replace("https://orcid.org/", "").strip()
    data = get(SOURCE, f"{BASE}/{orcid}/record", headers=JSON)
    person = data.get("person") or {}
    name = person.get("name") or {}
    acts = data.get("activities-summary") or {}
    urls = [
        {"name": u.get("url-name"), "url": (u.get("url") or {}).get("value")}
        for u in (person.get("researcher-urls") or {}).get("researcher-url", []) or []
    ]
    ext_ids = {
        e.get("external-id-type"): e.get("external-id-value")
        for e in (person.get("external-identifiers") or {}).get("external-identifier", []) or []
    }
    return {
        "source": SOURCE,
        "retrieved": today(),
        "orcid": orcid,
        "url": f"https://orcid.org/{orcid}",
        "name": " ".join(
            p for p in ((name.get("given-names") or {}).get("value"), (name.get("family-name") or {}).get("value")) if p
        ),
        "researcher_urls": urls,
        "external_ids": ext_ids,
        **{sec.replace("-", "_"): _affiliations(acts.get(sec)) for sec in SECTIONS},
        "works_count": len((acts.get("works") or {}).get("group", []) or []),
    }


def search(given: str, family: str, rows: int = 10) -> dict:
    q = f'given-names:"{given}" AND family-name:"{family}"'
    data = get(SOURCE, f"{BASE}/expanded-search/", params={"q": q, "rows": rows}, headers=JSON)
    return {
        "source": SOURCE,
        "retrieved": today(),
        "results": [
            {
                "orcid": r.get("orcid-id"),
                "name": f"{r.get('given-names') or ''} {r.get('family-names') or ''}".strip(),
                "institutions": r.get("institution-name") or [],
            }
            for r in data.get("expanded-result") or []
        ],
    }
