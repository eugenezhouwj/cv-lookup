"""Command-line entry point: `python -m cvlookup <command> ...`.

Every data command prints JSON to stdout. When a source cannot be reached the command
prints {"status": "unavailable", ...} and exits with code 3, so the caller can record the
gap in the report's sources note instead of guessing.
"""

from __future__ import annotations

import argparse
import json
import sys

from .http import SourceUnavailable, today
from .sources import crossref, openalex, orcid, repec, scholar, semantic_scholar


def _print(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def cmd_find_author(a):
    out = {"query": a.name, "affiliation": a.affiliation, "retrieved": today(), "results": {}, "unavailable": []}
    calls = [("OpenAlex", lambda: openalex.search_authors(a.name, a.affiliation))]
    parts = a.name.split()
    if len(parts) >= 2:
        calls.append(("ORCID", lambda: orcid.search(" ".join(parts[:-1]), parts[-1])))
    calls.append(("Semantic Scholar", lambda: semantic_scholar.search_authors(a.name)))
    for name, fn in calls:
        try:
            out["results"][name] = fn()
        except SourceUnavailable as e:
            out["unavailable"].append({"source": e.source, "error": e.message})
    if not out["results"]:
        out["status"] = "unavailable"
    return out


def cmd_author(a):
    return openalex.get_author(a.openalex_id)


def cmd_recent(a):
    return openalex.recent_works(a.openalex_id, a.years)


def cmd_top_cited(a):
    return openalex.top_cited(a.openalex_id, a.n)


def cmd_coauthors(a):
    return openalex.coauthors(a.openalex_id, a.top)


def cmd_sg_screen(a):
    from .singapore import screen

    works = openalex.all_works(a.openalex_id)
    return {"source": "OpenAlex", "retrieved": today(), "works_scanned": len(works), **screen(works, a.domain)}


def cmd_doi(a):
    return crossref.work(a.doi)


def cmd_crossref_search(a):
    return crossref.search(a.title, a.author)


def cmd_orcid(a):
    return orcid.record(a.orcid)


def cmd_s2_paper(a):
    return semantic_scholar.paper(doi=a.doi)


def cmd_repec(a):
    return repec.author(a.short_id)


def cmd_scholar(a):
    return scholar.profile(a.profile, a.by_date)


def cmd_validate(a):
    from .render.brief import validate

    with open(a.brief, encoding="utf-8") as f:
        warnings = validate(json.load(f))
    return {"status": "ok", "warnings": warnings}


def cmd_render(a):
    from .render.docx_report import render

    with open(a.brief, encoding="utf-8") as f:
        return render(json.load(f), a.out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cvlookup", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("find-author", help="Candidate identities from OpenAlex, ORCID and Semantic Scholar")
    s.add_argument("name")
    s.add_argument("--affiliation")
    s.set_defaults(fn=cmd_find_author)

    s = sub.add_parser("author", help="OpenAlex author profile")
    s.add_argument("openalex_id")
    s.set_defaults(fn=cmd_author)

    s = sub.add_parser("recent", help="Works in the recent window (OpenAlex)")
    s.add_argument("openalex_id")
    s.add_argument("--years", type=int, default=3)
    s.set_defaults(fn=cmd_recent)

    s = sub.add_parser("top-cited", help="Most-cited works (OpenAlex)")
    s.add_argument("openalex_id")
    s.add_argument("-n", type=int, default=5)
    s.set_defaults(fn=cmd_top_cited)

    s = sub.add_parser("coauthors", help="Co-authors ranked by joint works (OpenAlex)")
    s.add_argument("openalex_id")
    s.add_argument("--top", type=int, default=15)
    s.set_defaults(fn=cmd_coauthors)

    s = sub.add_parser("sg-screen", help="Nominate Tier 1 / Tier 2 Singapore-relevance candidates")
    s.add_argument("openalex_id")
    s.add_argument("--domain", action="append", default=[], help="Policy domain, repeatable (housing, trade, ...)")
    s.set_defaults(fn=cmd_sg_screen)

    s = sub.add_parser("doi", help="Publisher metadata for a DOI (Crossref)")
    s.add_argument("doi")
    s.set_defaults(fn=cmd_doi)

    s = sub.add_parser("crossref-search", help="Find a DOI from a title (Crossref)")
    s.add_argument("title")
    s.add_argument("--author")
    s.set_defaults(fn=cmd_crossref_search)

    s = sub.add_parser("orcid", help="ORCID record: employment, education, distinctions, ...")
    s.add_argument("orcid")
    s.set_defaults(fn=cmd_orcid)

    s = sub.add_parser("s2-paper", help="Semantic Scholar citation count, abstract, TLDR, OA PDF")
    s.add_argument("doi")
    s.set_defaults(fn=cmd_s2_paper)

    s = sub.add_parser("repec", help="RePEc/IDEAS author page (e.g. pab123)")
    s.add_argument("short_id")
    s.set_defaults(fn=cmd_repec)

    s = sub.add_parser("scholar", help="Google Scholar profile (user-supplied URL or user id)")
    s.add_argument("profile")
    s.add_argument("--by-date", action="store_true")
    s.set_defaults(fn=cmd_scholar)

    s = sub.add_parser("validate", help="Check a brief JSON against the spec")
    s.add_argument("brief")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("render", help="Render the detailed and summarised .docx reports")
    s.add_argument("brief")
    s.add_argument("--out", default="output")
    s.set_defaults(fn=cmd_render)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.fn(args)
    except SourceUnavailable as e:
        _print({"status": "unavailable", "source": e.source, "error": e.message, "retrieved": today()})
        return 3
    except ValueError as e:  # includes BriefError
        _print({"status": "error", "error": str(e)})
        return 2
    _print(result)
    return 3 if isinstance(result, dict) and result.get("status") == "unavailable" else 0


if __name__ == "__main__":
    sys.exit(main())
