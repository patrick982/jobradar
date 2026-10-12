"""karriere.at - Daten stecken in window.VUE_INITIAL_STATE (SSR)."""
from __future__ import annotations

import json

from ..models import Job, normalize_employment
from ..net import get

NAME = "karriere"
BASE = "https://www.karriere.at/jobs"


def _state(html: str) -> dict:
    i = html.find("window.VUE_INITIAL_STATE")
    if i < 0:
        raise ValueError("VUE_INITIAL_STATE nicht gefunden")
    j = html.find("=", i) + 1
    state, _ = json.JSONDecoder().raw_decode(html[j:].lstrip())
    return state


def search(keyword: str, cfg: dict) -> list[Job]:
    r = get(BASE, params={
        "keywords": keyword,
        "locations": cfg["location"],
        "radius": cfg.get("radius_km", 20),
    })
    state = _state(r.text)
    items = state.get("jobsSearchList", {}).get("activeItems", {}).get("items", [])
    jobs: list[Job] = []
    for entry in items:
        jt = entry.get("jobsItem") or {}
        if not jt.get("id"):
            continue
        locations = ", ".join(
            loc.get("name", "") for loc in jt.get("locations", []) if loc.get("name")
        )
        jobs.append(Job(
            source=NAME,
            source_id=str(jt["id"]),
            title=jt.get("title", "").strip(),
            company=(jt.get("company") or {}).get("name", ""),
            location=locations,
            employment=normalize_employment(jt.get("employmentTypes", "")),
            salary=jt.get("salary") or "",
            url=jt.get("link") or f"https://www.karriere.at/jobs/{jt['id']}",
            summary=(jt.get("summary") or jt.get("snippet") or "").strip(),
            posted=jt.get("date") or "",
            homeoffice=bool(jt.get("isHomeOffice")),
        ))
    return jobs
