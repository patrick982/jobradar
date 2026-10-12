"""AMS 'alle jobs' (jobs.ams.at) - API mit HMAC-SHA512-signierten Headern.

Der Signatur-Key ist im JS-Bundle eingebettet und kann sich aendern; er steht
in config.json unter "ams.key". Signiert wird:
  GET + path + <sortierte Query> + X-AMS-ACCESS-TOKEN-RANDOM=<rnd>&X-AMS-ACCESS-TOKEN-TIMESTAMP=<ts>
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

from ..models import Job, normalize_employment
from ..net import get

NAME = "ams"
PAGE_SIZE = 50


def _sign(key: str, path: str, params: dict[str, str]) -> tuple[str, str, str, str]:
    items = sorted(params.items())
    sig_query = "&".join(f"{k}={v}" for k, v in items)  # roh -> Signatur
    req_query = urlencode(items)                       # encodiert -> Request
    rnd = secrets.token_hex(8)
    ts = str(int(time.time()))
    msg = (f"GET{path}{sig_query}"
           f"X-AMS-ACCESS-TOKEN-RANDOM={rnd}&X-AMS-ACCESS-TOKEN-TIMESTAMP={ts}")
    sig = hmac.new(key.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return rnd, ts, sig, req_query


def search(keyword: str, cfg: dict) -> list[Job]:
    ams = cfg["ams"]
    key, base, path = ams["key"], ams["base"], ams["path"]
    jobs: list[Job] = []
    max_pages = cfg.get("max_pages", 5)
    for page in range(1, max_pages + 1):
        params = {
            "location": cfg["location"],
            "page": str(page),
            "pageSize": str(PAGE_SIZE),
            "query": keyword,
            "sortField": "_SCORE",
        }
        rnd, ts, sig, query = _sign(key, path, params)
        r = get(f"{base}{path}?{query}", headers={
            "X-AMS-Access-Token-Random": rnd,
            "X-AMS-Access-Token-Timestamp": ts,
            "X-AMS-Access-Token": sig,
            "Accept": "application/json, text/plain, */*",
        })
        data = r.json()
        for it in data.get("results", []):
            loc = it.get("workingLocation") or {}
            wt = it.get("workingTime") or {}
            uid = it.get("uuid") or str(it.get("id"))
            jobs.append(Job(
                source=NAME,
                source_id=str(uid),
                title=(it.get("title") or "").strip(),
                company=(it.get("company") or {}).get("name", ""),
                location=loc.get("municipality") or loc.get("town") or "",
                employment=normalize_employment(
                    f"{wt.get('code', '')} {wt.get('description', '')}"
                ),
                salary="",
                url=f"https://jobs.ams.at/public/emps/jobs/{uid}",
                summary=(it.get("summary") or "").strip(),
                posted=it.get("lastUpdatedAt") or "",
                homeoffice=bool(it.get("homeOffice")),
            ))
        if page >= int(data.get("totalPages", 1) or 1):
            break
    return jobs
