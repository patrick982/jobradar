"""willhaben.at - offene JSON-API publicapi.willhaben.at/jobs/v2/adverts."""
from __future__ import annotations

from ..models import Job, normalize_employment
from ..net import get

NAME = "willhaben"
BASE = "https://publicapi.willhaben.at/jobs/v2/adverts"
ROWS = 90


def _attr(attrs: dict, name: str) -> list[str]:
    return attrs.get(name, []) or []


def search(keyword: str, cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    max_pages = cfg.get("max_pages", 5)
    for page in range(1, max_pages + 1):
        r = get(BASE, params={
            "keyword": keyword,
            "location": cfg["location"],
            "rows": ROWS,
            "page": page,
            "sort": "publish_date_desc",
        }, headers={"Accept": "application/json"})
        data = r.json()
        for ad in data.get("advertSummaryList", []):
            attrs = {a.get("name"): a.get("values", []) for a in ad.get("attributes", [])}
            jid = str(ad.get("id"))
            jobs.append(Job(
                source=NAME,
                source_id=jid,
                title=(ad.get("description") or "").strip(),
                company=" ".join(_attr(attrs, "ORGNAME")),
                location=", ".join(_attr(attrs, "LOCATION")),
                employment=normalize_employment(" ".join(_attr(attrs, "EMPLOYMENT_TYPE"))),
                salary="",
                url=f"https://www.willhaben.at/jobs/job/{jid}",
                summary="",
                posted=" ".join(_attr(attrs, "PUBLISHED_String")),
                homeoffice="Homeoffice" in " ".join(_attr(attrs, "EMPLOYMENT_TYPE"))
                or "HOME_OFFICE" in " ".join(_attr(attrs, "RESULT_LIST_TOPJOB")),
            ))
        if page * ROWS >= int(data.get("rowsFound", 0) or 0):
            break
    return jobs
