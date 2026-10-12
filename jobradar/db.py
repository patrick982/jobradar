from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid         TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT DEFAULT '',
    location    TEXT DEFAULT '',
    employment  TEXT DEFAULT 'unbekannt',
    salary      TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    summary     TEXT DEFAULT '',
    posted      TEXT DEFAULT '',
    homeoffice  INTEGER DEFAULT 0,
    score       INTEGER DEFAULT 0,
    reasons     TEXT DEFAULT '[]',
    status      TEXT DEFAULT 'neu',
    note        TEXT DEFAULT '',
    first_seen  TEXT,
    last_seen   TEXT,
    live        INTEGER,
    live_reason TEXT DEFAULT '',
    live_checked TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS scans (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT,
    source   TEXT,
    keyword  TEXT,
    found    INTEGER,
    new      INTEGER
);
"""

STATUSES = ["neu", "gemerkt", "beworben", "interview", "absage", "verworfen"]

# Quellen mit Live-Suchindex: ein Treffer beim Scan gilt als aktuell.
LIVE_SOURCES = {"karriere", "willhaben", "ams"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
            for name, decl in (("live", "INTEGER"),
                               ("live_reason", "TEXT DEFAULT ''"),
                               ("live_checked", "TEXT")):
                if name not in cols:
                    self.conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_live ON jobs(live)")
            self.conn.commit()

    def upsert(self, job: Job) -> bool:
        now = _now()
        with self._lock:
            exists = self.conn.execute(
                "SELECT 1 FROM jobs WHERE uid = ?", (job.uid,)
            ).fetchone() is not None
            if exists:
                self.conn.execute(
                    """UPDATE jobs SET title=?, company=?, location=?, employment=?,
                       salary=?, url=?, summary=?, posted=?, homeoffice=?,
                       last_seen=? WHERE uid=?""",
                    (job.title, job.company, job.location, job.employment,
                     job.salary, job.url, job.summary, job.posted,
                     int(job.homeoffice), now, job.uid),
                )
            else:
                self.conn.execute(
                    """INSERT INTO jobs (uid, source, source_id, title, company,
                       location, employment, salary, url, summary, posted,
                       homeoffice, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (job.uid, job.source, job.source_id, job.title, job.company,
                     job.location, job.employment, job.salary, job.url,
                     job.summary, job.posted, int(job.homeoffice), now, now),
                )
            if job.source in LIVE_SOURCES:
                self.conn.execute(
                    "UPDATE jobs SET live=1, live_reason=?, live_checked=? "
                    "WHERE uid=?",
                    (f"{job.source} (Live-Index)", now, job.uid),
                )
        return not exists

    def commit(self) -> None:
        with self._lock:
            self.conn.commit()

    def log_scan(self, source: str, keyword: str, found: int, new: int) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO scans (ts, source, keyword, found, new) VALUES (?,?,?,?,?)",
                (_now(), source, keyword, found, new),
            )

    def all_jobs(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM jobs ORDER BY score DESC, first_seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, uid: str) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM jobs WHERE uid=?", (uid,)
            ).fetchone()
        return dict(row) if row else None

    def set_liveness(self, uid: str, live: bool | None, reason: str = "") -> None:
        val = None if live is None else int(live)
        with self._lock:
            self.conn.execute(
                "UPDATE jobs SET live=?, live_reason=?, live_checked=? WHERE uid=?",
                (val, reason, _now(), uid),
            )
            self.conn.commit()

    def set_status(self, uid: str, status: str, note: str | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"unbekannter Status: {status}")
        with self._lock:
            if note is None:
                self.conn.execute(
                    "UPDATE jobs SET status=? WHERE uid=?", (status, uid)
                )
            else:
                self.conn.execute(
                    "UPDATE jobs SET status=?, note=? WHERE uid=?",
                    (status, note, uid),
                )
            self.conn.commit()

    def apply_scores(self, scored: list[tuple[str, int, list[str]]]) -> None:
        with self._lock:
            for uid, score, reasons in scored:
                self.conn.execute(
                    "UPDATE jobs SET score=?, reasons=? WHERE uid=?",
                    (score, json.dumps(reasons, ensure_ascii=False), uid),
                )
            self.conn.commit()
