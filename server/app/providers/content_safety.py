from __future__ import annotations

import base64
import json
import threading
import time
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


class WechatImageSafetyProvider:
    """Synchronous image moderation using the official Mini Program security API."""

    name = "wechat-image-safety"
    TOKEN_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/token"
    CHECK_ENDPOINT = "https://api.weixin.qq.com/wxa/img_sec_check"
    TOKEN_ERRORS = {40001, 40014, 42001}

    def __init__(self, app_id: str, app_secret: str, timeout_seconds: float = 20) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout_seconds = timeout_seconds
        self._access_token = ""
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    def _token(self, force_refresh: bool = False) -> str:
        with self._token_lock:
            if (
                not force_refresh
                and self._access_token
                and time.monotonic() < self._token_expires_at
            ):
                return self._access_token
            response = httpx.get(
                self.TOKEN_ENDPOINT,
                params={
                    "grant_type": "client_credential",
                    "appid": self.app_id,
                    "secret": self.app_secret,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("wechat_content_safety_token_failed")
            expires_in = max(300, int(data.get("expires_in", 7200)))
            self._access_token = token
            self._token_expires_at = time.monotonic() + expires_in - 120
            return token

    def _check(self, image_path: Path, token: str) -> dict:
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = media_types.get(image_path.suffix.lower(), "application/octet-stream")
        with image_path.open("rb") as image:
            response = httpx.post(
                self.CHECK_ENDPOINT,
                params={"access_token": token},
                files={"media": (image_path.name, image, media_type)},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("wechat_content_safety_invalid_response")
        return data

    def is_allowed(self, image_path: Path, scene: str) -> bool:
        del scene
        data = self._check(image_path, self._token())
        errcode = int(data.get("errcode", -1))
        if errcode in self.TOKEN_ERRORS:
            data = self._check(image_path, self._token(force_refresh=True))
            errcode = int(data.get("errcode", -1))
        if errcode == 0:
            return True
        if errcode == 87014:
            return False
        raise ValueError(f"wechat_content_safety_error:{errcode}")


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
