from __future__ import annotations

import random
import time

import requests

UA = "jobradar/0.1 (private job search; see project README)"
DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
}

_session = requests.Session()


class FetchError(RuntimeError):
    pass


def get(url: str, params=None, headers=None, timeout: int = 25,
        retries: int = 3) -> requests.Response:
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1) + random.random())
    raise FetchError(f"GET {url} fehlgeschlagen: {last}")
