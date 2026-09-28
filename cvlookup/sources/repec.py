"""RePEc/IDEAS author pages (best-effort HTML parsing).

IDEAS is the most complete index of economics working papers and articles. Pages
are parsed heuristically; always cross-check titles against Crossref/OpenAlex.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..http import SourceUnavailable, get, today

SOURCE = "RePEc/IDEAS"
BASE = "https://ideas.repec.org"
KINDS = {"p": "working_paper", "a": "article", "b": "book", "h": "chapter", "c": "software"}
ITEM_HREF = re.compile(r"^/([pabhc])/")


def author_url(short_id: str) -> list[str]:
    """IDEAS files author pages under /e/ or /f/ depending on the profile; try both."""
    sid = short_id.strip().removesuffix(".html")
    return [f"{BASE}/e/{sid}.html", f"{BASE}/f/{sid}.html"]


def parse_author_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    affiliation = soup.find(id="affiliation")
    items, seen = [], set()
    for li in soup.find_all("li"):
        a = li.find("a", href=ITEM_HREF)
        if not a or a["href"] in seen:
            continue
        seen.add(a["href"])
        text = " ".join(li.get_text(" ", strip=True).split())
        year = re.search(r"\b(19|20)\d{2}\b", text)
        items.append(
            {
                "title": a.get_text(" ", strip=True),
                "kind": KINDS[ITEM_HREF.match(a["href"]).group(1)],
                "year": int(year.group(0)) if year else None,
                "citation_text": text[:400],
                "url": BASE + a["href"],
                "is_other_version": li.find_parent("li") is not None,
            }
        )
    return {
        "source": SOURCE,
        "retrieved": today(),
        "url": url,
        "page_title": title.get_text(strip=True) if title else None,
        "affiliation": " ".join(affiliation.get_text(" ", strip=True).split()) if affiliation else None,
        "items": items,
    }


def author(short_id: str) -> dict:
    last = None
    for url in author_url(short_id):
        try:
            html = get(SOURCE, url, as_json=False)
        except SourceUnavailable as e:
            last = e
            continue
        return parse_author_page(html, url)
    raise last
