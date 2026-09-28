"""Brief JSON model helpers: validation, verification filtering and reference numbering.

The brief format is documented in docs/BRIEF_FORMAT.md; examples/sample_brief.json is a
complete worked example.
"""

from __future__ import annotations

STATUSES = {"verified", "partial", "unverified"}
STATUS_LABEL = {"verified": "Verified", "partial": "Partially verified", "unverified": "Unverified"}
DEFAULT_CLASSIFICATION = "OFFICIAL (OPEN)"
DEFAULT_UNVERIFIED_REASON = "Not supported by a primary source or two independent secondary sources."
SUMMARY_FIELDS = ["research_question", "data", "methodology", "main_findings", "sub_findings", "relevance"]
PUB_LISTS = ["recent", "top_cited", "singapore_relevant"]


class BriefError(ValueError):
    pass


def is_shown(item: dict) -> bool:
    """Unverified items are excluded from the main body (SPEC step 3)."""
    return item.get("status", "unverified") != "unverified"


def validate(brief: dict) -> list[str]:
    """Return warnings; raise BriefError for problems that make rendering impossible."""
    errors, warnings = [], []
    meta = brief.get("meta") or {}
    for key in ("subject", "meeting_purpose", "date_prepared"):
        if not meta.get(key):
            errors.append(f"meta.{key} is required")
    persons = brief.get("persons") or []
    if not persons:
        errors.append("persons must contain at least one person")

    for p in persons:
        who = p.get("name") or "<unnamed person>"
        if not (p.get("identity") or {}).get("confirmed"):
            warnings.append(f"{who}: identity.confirmed is not true — confirm identity with the user (SPEC step 1)")
        pubs = p.get("publications") or {}
        for section in ("background", "research_interests", "network"):
            for i, item in enumerate(p.get(section) or []):
                _check_item(item, f"{who}.{section}[{i}]", errors, warnings)
        for pid, pub in pubs.items():
            _check_item(pub, f"{who}.publications.{pid}", errors, warnings)
            if pub.get("status") != "unverified" and any(pid in (p.get(l) or []) for l in PUB_LISTS):
                s = pub.get("summary")
                if not s:
                    warnings.append(f"{who}.publications.{pid}: no summary (required for SPEC items 3, 4, 6)")
                else:
                    missing = [f for f in SUMMARY_FIELDS if not s.get(f)]
                    if missing:
                        warnings.append(f"{who}.publications.{pid}: summary missing {missing} (use 'not stated')")
                    if s.get("basis") not in ("full_text", "abstract"):
                        warnings.append(f"{who}.publications.{pid}: summary.basis must be 'full_text' or 'abstract'")
            sg = pub.get("singapore")
            if sg and sg.get("tier") == 2 and not (sg.get("comparability") and sg.get("differences")):
                warnings.append(f"{who}.publications.{pid}: Tier 2 needs 'comparability' and 'differences'")
        for key in PUB_LISTS + ["key_papers"]:
            for pid in p.get(key) or []:
                if pid not in pubs:
                    errors.append(f"{who}.{key} references unknown publication '{pid}'")
        for tp in p.get("talking_points") or []:
            for ref in tp.get("refs") or []:
                if ref not in pubs:
                    errors.append(f"{who}.talking_points references unknown publication '{ref}'")
        n_tp = len(p.get("talking_points") or [])
        if not 5 <= n_tp <= 8:
            warnings.append(f"{who}: {n_tp} talking points (SPEC asks for 5–8)")
        if len(p.get("key_message") or []) != 3:
            warnings.append(f"{who}: key_message should be exactly 3 lines")
    if errors:
        raise BriefError("Brief is invalid:\n  - " + "\n  - ".join(errors))
    return warnings


def _check_item(item: dict, where: str, errors: list, warnings: list) -> None:
    status = item.get("status")
    if status not in STATUSES:
        errors.append(f"{where}: status must be one of {sorted(STATUSES)} (got {status!r})")
        return
    if status != "unverified" and not item.get("sources"):
        warnings.append(f"{where}: marked {status} but has no sources")
    if status == "verified" and len(item.get("sources") or []) < 2 and not any(
        s.get("primary") for s in item.get("sources") or []
    ):
        warnings.append(f"{where}: 'verified' needs one primary source or two independent sources")


def assign_refs(person: dict) -> dict[str, str]:
    """Number shown publications P1, P2, ... in order of first appearance."""
    pubs = person.get("publications") or {}
    order: list[str] = []
    for key in PUB_LISTS + ["key_papers"]:
        for pid in person.get(key) or []:
            if pid not in order and is_shown(pubs.get(pid, {})):
                order.append(pid)
    for pid, pub in pubs.items():
        if pid not in order and is_shown(pub):
            order.append(pid)
    return {pid: f"P{i}" for i, pid in enumerate(order, 1)}


def collect_unverified(brief: dict) -> list[dict]:
    out = list(brief.get("unverified") or [])
    labels = {"background": "Background", "research_interests": "Research interest", "network": "Network"}
    for p in brief.get("persons") or []:
        for section, label in labels.items():
            for item in p.get(section) or []:
                if not is_shown(item):
                    out.append(
                        {
                            "person": p.get("name"),
                            "section": label,
                            "item": item.get("text") or item.get("theme") or item.get("name"),
                            "reason": item.get("reason") or DEFAULT_UNVERIFIED_REASON,
                        }
                    )
        for pub in (p.get("publications") or {}).values():
            if not is_shown(pub):
                out.append(
                    {
                        "person": p.get("name"),
                        "section": "Publication",
                        "item": f"{pub.get('title')} ({pub.get('year') or 'n.d.'})",
                        "reason": pub.get("reason") or DEFAULT_UNVERIFIED_REASON,
                    }
                )
    return out
