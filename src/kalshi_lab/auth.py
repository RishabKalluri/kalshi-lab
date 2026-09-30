"""Kalshi API key auth: RSA-PSS(SHA256) signature over timestamp + method + path."""

import base64
import os
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com/trade-api/v2")
WS_URL = os.environ.get("KALSHI_WS_URL", "wss://api.elections.kalshi.com/trade-api/ws/v2")


class KalshiAuth:
    def __init__(self, key_id: str | None = None, key_path: str | None = None):
        self.key_id = key_id or os.environ["KALSHI_KEY_ID"]
        path = Path(key_path or os.environ["KALSHI_PRIVATE_KEY_PATH"]).expanduser()
        self._key = serialization.load_pem_private_key(path.read_bytes(), password=None)

    def headers(self, method: str, path: str) -> dict[str, str]:
        """`path` is the full URL path (e.g. /trade-api/v2/portfolio/balance), no query string."""
        ts = str(int(time.time() * 1000))
        msg = (ts + method.upper() + path.split("?")[0]).encode()
        sig = self._key.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        }
