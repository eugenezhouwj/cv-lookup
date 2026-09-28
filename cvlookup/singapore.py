"""Heuristic pre-screen for Singapore relevance (SPEC step 2.6).

This only *nominates* candidates. Claude must read each candidate and confirm the
tier, the criterion met, and (for Tier 2) why the context is comparable and where
it differs from Singapore.
"""

from __future__ import annotations

import re

SG_TERMS = [
    r"singapore\w*",
    r"housing and development board",
    r"\bHDB\b",
    r"central provident fund",
    r"\bCPF\b",
    r"urban redevelopment authority",
    r"monetary authority of singapore",
    r"jurong|tampines|punggol",
]

CASE_SENSITIVE = {r"\bHDB\b", r"\bCPF\b"}

SG_FUNDER_TERMS = ["singapore", "national research foundation", "a*star", "ministry of education, singapore"]

# Mirrors the default comparator table in docs/SPEC.md. Keys are policy domains.
COMPARATORS: dict[str, list[str]] = {
    "housing": ["Hong Kong", "Vienna", "Austria", "Netherlands", "Amsterdam", "Tokyo", "Seoul", "Monaco", "Macau", "public housing", "social housing", "land supply", "leasehold"],
    "trade": ["Hong Kong", "Switzerland", "Netherlands", "Ireland", "Denmark", "Israel", "small open economy", "small open economies"],
    "education": ["Hong Kong", "South Korea", "Korea", "Taiwan", "Japan", "Shanghai", "Finland", "East Asia"],
    "labour": ["Japan", "South Korea", "Korea", "Hong Kong", "ageing", "aging", "foreign workers", "migrant workers"],
    "urban": ["Hong Kong", "Tokyo", "Seoul", "London", "congestion pricing", "road pricing", "density", "mass transit"],
    "macro": ["Hong Kong", "small open economy", "small open economies", "currency board", "exchange rate policy"],
}
DOMAIN_ALIASES = {
    "land": "housing", "real estate": "housing", "property": "housing",
    "industry": "trade", "fdi": "trade",
    "human capital": "education", "schooling": "education",
    "labor": "labour", "ageing": "labour", "social policy": "labour", "population": "labour",
    "transport": "urban", "infrastructure": "urban", "planning": "urban",
    "general": "macro", "monetary": "macro", "fiscal": "macro",
}


def normalise_domain(domain: str) -> str | None:
    d = domain.strip().lower()
    if d in COMPARATORS:
        return d
    return DOMAIN_ALIASES.get(d)


def screen(works: list[dict], domains: list[str] | None = None) -> dict:
    """Return Tier 1 and Tier 2 *candidates* from OpenAlex-style work dicts."""
    comparator_terms: list[str] = []
    unknown = []
    for d in domains or []:
        key = normalise_domain(d)
        if key:
            comparator_terms += COMPARATORS[key]
        else:
            unknown.append(d)
    comparator_terms = sorted(set(comparator_terms))

    tier1, tier2 = [], []
    for w in works:
        text = f"{w.get('title') or ''} {w.get('abstract') or ''}"
        reasons = []
        # Acronyms are matched case-sensitively to avoid e.g. "cpf" in unrelated words.
        text_hits = [h for p in SG_TERMS for h in re.findall(p, text, flags=0 if p in CASE_SENSITIVE else re.I)]
        if text_hits:
            reasons.append(f"mentions: {', '.join(sorted(set(text_hits), key=str.lower))}")
        sg_authors = [
            a["name"] for a in w.get("authors") or [] if any(i.get("country") == "SG" for i in a.get("institutions") or [])
        ]
        if sg_authors:
            reasons.append(f"Singapore-affiliated co-author(s): {', '.join(sg_authors)}")
        sg_funders = [f for f in w.get("funders") or [] if any(t in f.lower() for t in SG_FUNDER_TERMS)]
        if sg_funders:
            reasons.append(f"Singapore funder(s): {', '.join(sg_funders)}")
        base = {k: w.get(k) for k in ("openalex_id", "title", "year", "venue", "doi", "cited_by_count")}
        if reasons:
            tier1.append({**base, "candidate_tier": 1, "reasons": reasons})
            continue
        comp_hits = sorted({t for t in comparator_terms if re.search(rf"\b{re.escape(t)}\b", text, flags=re.I)})
        if comp_hits:
            tier2.append({**base, "candidate_tier": 2, "comparator_terms": comp_hits})
    return {
        "tier1_candidates": tier1,
        "tier2_candidates": tier2,
        "domains_used": [d for d in domains or [] if d not in unknown],
        "unrecognised_domains": unknown,
        "note": "Heuristic screen on title/abstract/affiliations/funders only. Confirm each candidate "
        "by reading the paper; abstracts may be missing, so absence here is not proof of irrelevance.",
    }
