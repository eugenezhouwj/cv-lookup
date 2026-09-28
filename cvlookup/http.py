"""Shared HTTP session with polite defaults, retries and uniform error handling."""

from __future__ import annotations

import datetime as dt
import os
import time

import requests

USER_AGENT = "cv-lookup/0.1 (research meeting-brief tool)"
TIMEOUT = 30


class SourceUnavailable(Exception):
    """Raised when a data source cannot be reached or refuses the request."""

    def __init__(self, source: str, message: str):
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


def today() -> str:
    return dt.date.today().isoformat()


def _session() -> requests.Session:
    s = requests.Session()
    ua = USER_AGENT
    mailto = os.environ.get("CVLOOKUP_MAILTO")
    if mailto:
        # OpenAlex and Crossref route requests that carry a contact address to their "polite pool".
        ua += f" mailto:{mailto}"
    s.headers["User-Agent"] = ua
    return s


SESSION = _session()


def get(source: str, url: str, *, params=None, headers=None, retries: int = 3, as_json: bool = True):
    """GET a URL, retrying on 429/5xx. Raises SourceUnavailable on failure."""
    delay = 2.0
    last = ""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as e:
            last = f"network error: {e.__class__.__name__}: {e}"
        else:
            if r.status_code == 404:
                raise SourceUnavailable(source, f"not found (404): {r.url}")
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
            elif r.status_code >= 400:
                raise SourceUnavailable(source, f"HTTP {r.status_code}: {r.url}")
            else:
                if not as_json:
                    return r.text
                try:
                    return r.json()
                except ValueError:
                    raise SourceUnavailable(source, "response was not JSON")
        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 2
    raise SourceUnavailable(source, last or "unknown error")
