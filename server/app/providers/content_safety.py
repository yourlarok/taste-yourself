from __future__ import annotations

from pathlib import Path
from typing import Protocol

import httpx


class ContentSafetyProvider(Protocol):
    name: str

    def is_allowed(self, image_path: Path, scene: str) -> bool: ...


class MockContentSafetyProvider:
    """Development-only provider; production preflight rejects this selection."""

    name = "mock-allow"

    def is_allowed(self, image_path: Path, scene: str) -> bool:
        return image_path.is_file()


class HttpContentSafetyProvider:
    """Adapter for a private moderation gateway with a stable allow/reject contract."""

    name = "content-safety-http"

    def __init__(self, base_url: str, token: str, timeout_seconds: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def is_allowed(self, image_path: Path, scene: str) -> bool:
        headers = {"X-Worker-Token": self.token} if self.token else {}
        with image_path.open("rb") as image:
            response = httpx.post(
                f"{self.base_url}/v1/check-image",
                headers=headers,
                files={"image": (image_path.name, image, "image/jpeg")},
                data={"scene": scene},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("action") not in {"allow", "reject"}:
            raise ValueError("content_safety_returned_invalid_action")
        return data["action"] == "allow"
