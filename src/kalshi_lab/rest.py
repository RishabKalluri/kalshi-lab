"""Minimal Kalshi REST client."""

import logging
import time
from urllib.parse import urlparse

import httpx

from .auth import API_BASE, KalshiAuth

log = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


class KalshiREST:
    def __init__(self, auth: KalshiAuth | None = None, base: str = API_BASE, anonymous: bool = False):
        # anonymous: public market data only (backfill), e.g. on the research server, which has no Kalshi key
        self.auth = None if anonymous else (auth or KalshiAuth())
        self.base = base.rstrip("/")
        self._prefix = urlparse(self.base).path
        self.client = httpx.Client(timeout=10)

    def get(self, path: str, retries: int = 6, **params):
        """GET with retries on network errors, 429 and 5xx (reads are safe to repeat)."""
        for attempt in range(retries):
            try:
                headers = self.auth.headers("GET", self._prefix + path) if self.auth else {}  # fresh timestamp
                r = self.client.get(self.base + path, params=params or None, headers=headers)
                if r.status_code not in RETRY_STATUS or attempt == retries - 1:
                    r.raise_for_status()
                    return r.json()
            except httpx.TransportError as e:
                if attempt == retries - 1:
                    raise
                log.warning("GET %s: %r (attempt %d)", path, e, attempt + 1)
            time.sleep(min(30, 0.5 * 2 ** attempt))

    def post(self, path: str, body: dict):
        headers = self.auth.headers("POST", self._prefix + path)
        r = self.client.post(self.base + path, json=body, headers=headers)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str, **params):
        headers = self.auth.headers("DELETE", self._prefix + path)
        r = self.client.delete(self.base + path, params=params or None, headers=headers)
        r.raise_for_status()
        return r.json()

    def paginate(self, path: str, key: str, **params):
        cursor = None
        while True:
            page = self.get(path, **params, **({"cursor": cursor} if cursor else {}))
            yield from page.get(key, [])
            cursor = page.get("cursor")
            if not cursor:
                return

    def balance(self):
        return self.get("/portfolio/balance")

    def markets(self, **params):
        return self.paginate("/markets", "markets", limit=1000, **params)
