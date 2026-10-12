"""jobs.at - JSON-Antwort derselben URL, sobald X-Requested-With gesetzt ist."""
from __future__ import annotations

from ..models import Job, normalize_employment
from ..net import get

NAME = "jobsat"
BASE = "https://www.jobs.at/j"


def _salary(s: dict) -> str:
    if not s:
        return ""
    typ = s.get("salary-type") or ""
    lo, hi = s.get("salary-from"), s.get("salary-to")
    if lo and hi and lo != hi:
        return f"€ {lo} - {hi} {typ}".strip()
    if lo or hi:
        return f"€ {lo or hi} {typ}".strip()
    return ""


def search(keyword: str, cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    max_pages = cfg.get("max_pages", 5)
    headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    for page in range(1, max_pages + 1):
        r = get(BASE, params={
            "keyword": keyword,
            "location": cfg["location"],
            "page": page,
        }, headers=headers)
        data = r.json()
        jd = data.get("jobs", {})
        for j in jd.get("data", []):
            jid = str(j.get("id"))
            jobs.append(Job(
                source=NAME,
                source_id=jid,
                title=(j.get("title") or "").strip(),
                company=(j.get("company") or {}).get("name", ""),
                location=j.get("location") or "",
                employment=normalize_employment(" ".join(j.get("_employment_types", []) or [])),
                salary=_salary(j.get("salary") or {}),
                url=f"https://www.jobs.at/i/{jid}",
                summary=(j.get("snippet") or "").strip(),
                posted=str(j.get("show_date") or ""),
                homeoffice=bool(j.get("homeoffice")),
            ))
        if page >= int(jd.get("last_page", 1) or 1):
            break
    return jobs
