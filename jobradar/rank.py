from __future__ import annotations

import re

from .db import DB


def _match(text: str, term: str) -> bool:
    """Kurze Terme (<=3 Zeichen) nur als ganzes Wort, sonst als Teilstring.

    So trifft 'it' nicht in 'digital', 'ai' nicht in 'mail', aber
    'systemadmin' weiterhin im deutschen Kompositum 'Systemadministrator'.
    """
    term = term.lower()
    if len(term) <= 3:
        return re.search(
            rf"(?<![a-zäöüß]){re.escape(term)}(?![a-zäöüß])", text
        ) is not None
    return term in text


def _text(row: dict) -> str:
    return " ".join(str(row.get(k, "")) for k in (
        "title", "company", "summary", "location", "employment", "salary"
    )).lower()


def score_row(row: dict, rank: dict, location: str) -> tuple[int, list[str]]:
    text = _text(row)
    score = 0
    reasons: list[str] = []

    employment = (row.get("employment") or "").lower()
    for key, bonus in rank.get("employment", {}).items():
        if employment == key:
            score += bonus
            reasons.append(f"{key.capitalize()} (+{bonus})")
            break

    core = [kw for kw in rank.get("core", []) if _match(text, kw)]
    core_label = rank.get("core_label", "IT-Bezug")
    core_penalty = rank.get("core_penalty", 40)
    if core:
        add = min(len(core) * 5, 20)
        score += add
        reasons.append(f"{core_label}: {', '.join(core[:5])} (+{add})")
    elif core_penalty:
        score -= core_penalty
        reasons.append(f"kein {core_label} (-{core_penalty})")

    pos, neg = [], []
    for term, weight in rank.get("weights", {}).items():
        if _match(text, term):
            score += weight
            (pos if weight > 0 else neg).append((term, weight))
    if pos:
        add = sum(w for _, w in pos)
        reasons.append(
            f"Profil-Match: {', '.join(t for t, _ in pos[:6])} (+{add})")
    if neg:
        sub = sum(w for _, w in neg)
        reasons.append(
            f"Lücken/Abzüge: {', '.join(t for t, _ in neg[:6])} ({sub})")

    boosts = [kw for kw in rank.get("boost", []) if _match(text, kw)]
    if boosts:
        add = min(len(boosts) * 6, 18)
        score += add
        reasons.append(f"Signalwörter: {', '.join(boosts[:4])} (+{add})")

    if location.lower() in (row.get("location") or "").lower():
        score += rank.get("location", 10)
        reasons.append(f"Ort {location} (+{rank.get('location', 10)})")

    if row.get("homeoffice"):
        score += rank.get("homeoffice", 5)
        reasons.append(f"Homeoffice (+{rank.get('homeoffice', 5)})")

    return score, reasons


def rank_all(db: DB, cfg: dict) -> int:
    rank = cfg.get("rank", {})
    location = cfg.get("location", "")
    scored = []
    for row in db.all_jobs():
        s, reasons = score_row(row, rank, location)
        scored.append((row["uid"], s, reasons))
    db.apply_scores(scored)
    return len(scored)
