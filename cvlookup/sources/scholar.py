"""Google Scholar profile pages (user-supplied URL only).

Google Scholar has no API and often serves CAPTCHAs to automated clients. Used only
to cross-check and to report its citation counts alongside other sources — never as
the sole source for a fact.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup

from ..http import SourceUnavailable, get, today

SOURCE = "Google Scholar"
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def profile_url(url_or_id: str, sort_by_date: bool = False) -> str:
    user = url_or_id
    if url_or_id.startswith("http"):
        user = parse_qs(urlparse(url_or_id).query).get("user", [""])[0]
    params = {"user": user, "hl": "en", "cstart": 0, "pagesize": 100}
    if sort_by_date:
        params["sortby"] = "pubdate"
    return "https://scholar.google.com/citations?" + urlencode(params)


def parse_profile(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    name = soup.find(id="gsc_prf_in")
    if not name:
        raise SourceUnavailable(SOURCE, "profile not returned (likely CAPTCHA or blocked)")
    stats = [td.get_text(strip=True) for td in soup.select("#gsc_rsb_st td.gsc_rsb_std")]
    pubs = []
    for tr in soup.select("tr.gsc_a_tr"):
        a = tr.select_one("a.gsc_a_at")
        grays = [g.get_text(" ", strip=True) for g in tr.select("div.gs_gray")]
        cites = tr.select_one("a.gsc_a_ac")
        year = tr.select_one("span.gsc_a_h")
        cites_txt = cites.get_text(strip=True) if cites else ""
        year_txt = year.get_text(strip=True) if year else ""
        pubs.append(
            {
                "title": a.get_text(" ", strip=True) if a else None,
                "authors": grays[0] if grays else None,
                "venue": grays[1] if len(grays) > 1 else None,
                "citations_scholar": int(cites_txt) if cites_txt.isdigit() else 0,
                "year": int(year_txt) if re.fullmatch(r"\d{4}", year_txt) else None,
            }
        )
    affil = soup.select_one("div.gsc_prf_il")
    return {
        "source": SOURCE,
        "retrieved": today(),
        "url": url,
        "name": name.get_text(strip=True),
        "affiliation": affil.get_text(" ", strip=True) if affil else None,
        "interests": [a.get_text(strip=True) for a in soup.select("#gsc_prf_int a")],
        "citations_total": stats[0] if stats else None,
        "h_index": stats[2] if len(stats) > 2 else None,
        "publications": pubs,
    }


def profile(url_or_id: str, sort_by_date: bool = False) -> dict:
    url = profile_url(url_or_id, sort_by_date)
    return parse_profile(get(SOURCE, url, headers=BROWSER_UA, as_json=False, retries=1), url)
