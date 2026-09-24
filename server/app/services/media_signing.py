from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote


class MediaUrlSigner:
    def __init__(self, secret: str, ttl_seconds: int = 10 * 60) -> None:
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def _signature(self, relative_path: str, expires: int) -> str:
        message = f"{relative_path}|{expires}".encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def sign(self, relative_path: str) -> str:
        expires = int(time.time()) + self.ttl_seconds
        signature = self._signature(relative_path, expires)
        encoded_path = quote(relative_path, safe="/")
        return f"/api/v1/media/{encoded_path}?expires={expires}&signature={signature}"

    def verify(self, relative_path: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = self._signature(relative_path, expires)
        return hmac.compare_digest(expected, signature)
