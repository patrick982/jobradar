from __future__ import annotations

from dataclasses import dataclass, field


def normalize_employment(text: str) -> str:
    t = (text or "").lower()
    has_tz = "teilzeit" in t or "geringf" in t
    has_vz = "vollzeit" in t
    if has_tz and has_vz:
        return "beide"
    if has_tz:
        return "teilzeit"
    if has_vz:
        return "vollzeit"
    return "unbekannt"


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str = ""
    location: str = ""
    employment: str = "unbekannt"
    salary: str = ""
    url: str = ""
    summary: str = ""
    posted: str = ""
    homeoffice: bool = False
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    def searchable_text(self) -> str:
        return " ".join(
            [self.title, self.company, self.summary, self.location,
             self.employment, self.salary]
        ).lower()
