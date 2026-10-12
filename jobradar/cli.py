from __future__ import annotations

import argparse
import time

from .config import load_config
from .db import DB
from .rank import rank_all
from .sources import REGISTRY


def cmd_scan(cfg: dict, args: argparse.Namespace) -> None:
    db = DB(cfg["db_path"])
    sources = args.sources or cfg.get("sources", list(REGISTRY))
    keywords = args.keywords or cfg.get("keywords", [])
    delay = cfg.get("request_delay", 1.0)
    total_new = 0
    for source in sources:
        mod = REGISTRY.get(source)
        if not mod:
            print(f"  ! unbekannte Quelle: {source}")
            continue
        for kw in keywords:
            try:
                jobs = mod.search(kw, cfg)
            except Exception as exc:
                print(f"  ! {source}/{kw}: {exc}")
                continue
            new = sum(1 for j in jobs if db.upsert(j))
            db.log_scan(source, kw, len(jobs), new)
            db.commit()
            total_new += new
            print(f"  {source:9} {kw:20} {len(jobs):3} gefunden, {new:3} neu")
            time.sleep(delay)
    rank_all(db, cfg)
    print(f"\nGesamt: {total_new} neue Jobs. Ranking aktualisiert.")
    if getattr(args, "check", False):
        from .liveness import check_all
        counts = check_all(db, only_missing=True, delay=0.3)
        print(f"Live-Check: {counts['live']} live, {counts['expired']} abgelaufen, "
              f"{counts['unknown']} unpruefbar")


def cmd_rank(cfg: dict, args: argparse.Namespace) -> None:
    db = DB(cfg["db_path"])
    n = rank_all(db, cfg)
    print(f"Ranking für {n} Jobs neu berechnet.")


def cmd_list(cfg: dict, args: argparse.Namespace) -> None:
    db = DB(cfg["db_path"])
    rows = db.all_jobs()
    if not getattr(args, "show_expired", False):
        rows = [r for r in rows if r.get("live") != 0]
    if args.teilzeit:
        rows = [r for r in rows if r["employment"] in ("teilzeit", "beide")]
    for r in rows[:args.limit]:
        mark = " " if r.get("live") != 0 else "x"
        print(f"{r['score']:4}{mark} [{r['employment']:9}] {r['source']:9} "
              f"{r['title'][:48]:48} | {r['company'][:22]}")


def cmd_check(cfg: dict, args: argparse.Namespace) -> None:
    from .liveness import check_all
    db = DB(cfg["db_path"])
    sources = set(args.sources) if args.sources else None
    counts = check_all(db, sources=sources, min_score=args.min_score,
                       limit=args.limit, delay=args.delay,
                       only_missing=args.only_missing)
    print(f"\nErgebnis: {counts['live']} live, {counts['expired']} abgelaufen, "
          f"{counts['unknown']} unpruefbar")


def cmd_serve(cfg: dict, args: argparse.Namespace) -> None:
    from .server import serve
    serve(cfg, host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobradar", description="Lokaler Job-Radar Graz")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Quellen abfragen und in die DB schreiben")
    s.add_argument("--sources", nargs="*", help="nur diese Quellen")
    s.add_argument("--keywords", nargs="*", help="nur diese Keywords")
    s.add_argument("--check", action="store_true",
                   help="danach neue Jobs auf Live-Status pruefen")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("rank", help="Scoring neu berechnen")
    r.set_defaults(func=cmd_rank)

    l = sub.add_parser("list", help="Jobs in der Konsole anzeigen")
    l.add_argument("--limit", type=int, default=25)
    l.add_argument("--teilzeit", action="store_true")
    l.add_argument("--show-expired", action="store_true",
                   help="auch als abgelaufen markierte Jobs zeigen")
    l.set_defaults(func=cmd_list)

    c = sub.add_parser("check", help="Inserate auf Live-Status pruefen")
    c.add_argument("--sources", nargs="*", help="nur diese Quellen")
    c.add_argument("--min-score", type=int, default=0)
    c.add_argument("--limit", type=int, default=0)
    c.add_argument("--delay", type=float, default=0.4)
    c.add_argument("--only-missing", action="store_true",
                   help="nur noch nie gepruefte Jobs")
    c.set_defaults(func=cmd_check)

    v = sub.add_parser("serve", help="Dashboard starten")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8765)
    v.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = load_config()
    args.func(cfg, args)
