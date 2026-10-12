"""Live-Check für Stelleninserate.

karriere.at und willhaben.at lassen sich zuverlässig prüfen: eine abgelaufene
Anzeige wird auf eine Such-/Übersichtsseite umgeleitet bzw. enthält keine
Job-Detaildaten mehr. AMS (SPA) und jobs.at (hält alte Einträge) sind nicht
zuverlässig prüfbar und werden als ``None`` (unbekannt) gemeldet.
"""
from __future__ import annotations

import json
import re
import time

import requests

from .db import DB
from .net import DEFAULT_HEADERS

# Statuscodes, die eindeutig "weg" bedeuten
GONE = (404, 410)

# Quellen, deren Treffer beim Scan als "live" gelten (Live-Suchindex)
LIVE_SOURCES = {"karriere", "willhaben", "ams"}


def _id_token(url: str) -> str:
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url)
    if m:
        return m.group(1)
    m = re.search(r"/(\d{5,})", url)
    return m.group(1) if m else ""


def _karriere_live(html: str) -> bool:
    if "jobDetailContent" not in html:
        return False
    i = html.find("window.VUE_INITIAL_STATE")
    if i < 0:
        return False
    try:
        j = html.find("=", i) + 1
        state, _ = json.JSONDecoder().raw_decode(html[j:].lstrip())
        jd = state.get("jobDetailContent") or {}
        job = (jd.get("jobHeader") or {}).get("job") or {}
        return bool(job.get("id") or job.get("title"))
    except (ValueError, KeyError):
        return False


def _willhaben_live(html: str) -> bool:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return False
    try:
        data = (json.loads(m.group(1)).get("props", {}).get("pageProps", {})
                .get("jobAdvertDetailsRoot", {}).get("data", {}) or {})
        return bool(data.get("title"))
    except (ValueError, KeyError):
        return False


def check(job: dict) -> tuple[bool | None, str]:
    """Liefert (live, grund). True=live, False=abgelaufen, None=unbekannt."""
    url = (job.get("url") or "").strip()
    if not url:
        return None, "keine URL"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    except requests.RequestException as exc:
        return None, f"Netzfehler ({type(exc).__name__})"
    if r.status_code in GONE:
        return False, f"HTTP {r.status_code}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    tok = _id_token(url)
    if tok and tok not in r.url:
        return False, "weitergeleitet (weg)"
    if "karriere.at" in url:
        return _karriere_live(r.text), "karriere.at"
    if "willhaben.at" in url:
        return _willhaben_live(r.text), "willhaben.at"
    if "jobs.ams.at" in url:
        return None, "ams (SPA, kein Live-Check)"
    if "jobs.at" in url:
        return None, "jobs.at (haelt alte Eintraege)"
    return None, "unbekannte Quelle"


def check_all(db: DB, *, sources: set[str] | None = None, min_score: int = 0,
              limit: int | None = None, delay: float = 0.4,
              only_missing: bool = False, verbose: bool = True) -> dict:
    rows = db.all_jobs()
    rows = [r for r in rows if (r.get("score") or 0) >= min_score]
    if sources:
        rows = [r for r in rows if r.get("source") in sources]
    if only_missing:
        rows = [r for r in rows if r.get("live") is None]
    if limit:
        rows = rows[:limit]

    counts = {"live": 0, "expired": 0, "unknown": 0}
    for i, r in enumerate(rows, 1):
        live, reason = check(r)
        db.set_liveness(r["uid"], live, reason)
        if live is True:
            counts["live"] += 1
        elif live is False:
            counts["expired"] += 1
        else:
            counts["unknown"] += 1
        if verbose:
            label = "LIVE" if live is True else ("WEG " if live is False else "??  ")
            print(f"  [{i:4}/{len(rows)}] {label} {r['title'][:46]:46} | {reason}")
        time.sleep(delay)
    return counts
