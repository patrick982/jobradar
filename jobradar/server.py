from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import STATUSES, DB

WEB_DIR = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    db: DB
    cfg: dict

    def log_message(self, *args) -> None:  # ruhig halten
        pass

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path: Path) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._html(WEB_DIR / "index.html")
        if u.path == "/api/jobs":
            q = parse_qs(u.query)
            rows = self.db.all_jobs()
            if (q.get("show_expired") or ["0"])[0] != "1":
                rows = [r for r in rows if r.get("live") != 0]
            status = (q.get("status") or [""])[0]
            if status:
                rows = [r for r in rows if r["status"] == status]
            if (q.get("teilzeit") or ["0"])[0] == "1":
                rows = [r for r in rows if r["employment"] in ("teilzeit", "beide")]
            text = (q.get("q") or [""])[0].lower().strip()
            if text:
                rows = [r for r in rows
                        if text in f"{r['title']} {r['company']} {r['location']}".lower()]
            return self._json({"jobs": rows, "statuses": STATUSES})
        if u.path == "/api/stats":
            rows = self.db.all_jobs()
            by_status: dict[str, int] = {}
            for r in rows:
                by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            return self._json({
                "total": len(rows),
                "teilzeit": sum(1 for r in rows if r["employment"] in ("teilzeit", "beide")),
                "expired": sum(1 for r in rows if r.get("live") == 0),
                "by_status": by_status,
            })
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid json"}, 400)
        if u.path == "/api/status":
            uid, status = payload.get("uid"), payload.get("status")
            if not uid or status not in STATUSES:
                return self._json({"error": "uid/status fehlt"}, 400)
            self.db.set_status(uid, status, payload.get("note"))
            return self._json({"ok": True})
        if u.path == "/api/check":
            from .liveness import check_all
            counts = check_all(
                self.db,
                sources=set(payload["sources"]) if payload.get("sources") else None,
                min_score=int(payload.get("min_score") or 0),
                limit=int(payload.get("limit") or 0),
                only_missing=bool(payload.get("only_missing", True)),
                verbose=False,
            )
            return self._json({"ok": True, **counts})
        self._json({"error": "not found"}, 404)


def serve(cfg: dict, host: str = "127.0.0.1", port: int = 8765) -> None:
    Handler.db = DB(cfg["db_path"])
    Handler.cfg = cfg
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Job-Radar Dashboard: http://{host}:{port}  (Strg+C beendet)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet.")
