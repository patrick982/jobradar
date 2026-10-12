from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config.json"


def load_config(path: str | Path | None = None) -> dict:
    if path is None and os.environ.get("JOBRADAR_CONFIG"):
        path = ROOT / os.environ["JOBRADAR_CONFIG"]
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        raise SystemExit(
            f"Config '{p.name}' fehlt. Kopiere config.example.json nach "
            f"{p.name} und passe die Suche an."
        )
    cfg = json.loads(p.read_text(encoding="utf-8"))
    db = cfg.get("db_path", "jobradar.db")
    if not Path(db).is_absolute():
        cfg["db_path"] = str(ROOT / db)
    # Secrets never live in the repo: the AMS API key comes from the env.
    ams = cfg.setdefault("ams", {})
    ams["key"] = os.environ.get("AMS_KEY", ams.get("key", ""))
    cfg["_root"] = str(ROOT)
    return cfg
