from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Protocol

import httpx


class ContentSafetyProvider(Protocol):
    name: str

    def is_allowed(self, image_path: Path, scene: str) -> bool: ...


class DisabledContentSafetyProvider:
    """Fail closed when no real moderation service is configured."""

    name = "disabled"

    def is_allowed(self, image_path: Path, scene: str) -> bool:
        raise RuntimeError("content_safety_not_configured")


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

    def is_allowed_video(self, video_path: Path, scene: str) -> bool:
        headers = {"X-Worker-Token": self.token} if self.token else {}
        with video_path.open("rb") as video:
            response = httpx.post(
                f"{self.base_url}/v1/check-video",
                headers=headers,
                files={"video": (video_path.name, video, "video/mp4")},
                data={"scene": scene},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("action") not in {"allow", "reject"}:
            raise ValueError("content_safety_returned_invalid_action")
        return data["action"] == "allow"


class BailianContentSafetyProvider:
    """Image moderation backed by Bailian vision plus its AI safety guardrail."""

    name = "bailian-content-safety"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def is_allowed(self, image_path: Path, scene: str) -> bool:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-DataInspection": json.dumps(
                    {"input": "cip", "output": "cip"}, separators=(",", ":")
                ),
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是上传图片安全审核器。拒绝色情或裸露、性化未成年人、"
                            "血腥暴力、仇恨标志、违法物品、明显个人证件或支付信息。"
                            "普通人像和普通服装允许。只输出JSON。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"场景：{scene}。输出 action 和 categories。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("content_safety_returned_invalid_action") from error
        if data.get("action") not in {"allow", "reject"}:
            raise ValueError("content_safety_returned_invalid_action")
        return data["action"] == "allow"
