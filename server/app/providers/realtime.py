from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import httpx

from app.domain.experience import RealtimeSessionResult


class RealtimeProvider(Protocol):
    name: str

    def create(self, experience_session_id: str, garment_id: str) -> RealtimeSessionResult: ...


class MockRealtimeProvider:
    """A timer-only session used by DevTools without consuming a live service."""

    name = "mock"

    def create(self, experience_session_id: str, garment_id: str) -> RealtimeSessionResult:
        return RealtimeSessionResult(
            id=str(uuid4()),
            experience_session_id=experience_session_id,
            status="ready",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=20),
            notice="开发环境模拟会话；不会上传视频流，前端执行 15 秒倒计时。",
        )


class DisabledRealtimeProvider:
    name = "disabled"

    def create(self, experience_session_id: str, garment_id: str) -> RealtimeSessionResult:
        return RealtimeSessionResult(
            id=str(uuid4()),
            experience_session_id=experience_session_id,
            status="unavailable",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=20),
            notice="实时试穿暂未配置，静态试穿和尺码差异仍可继续使用。",
        )


class HttpRealtimeProvider:
    """Creates a short-lived RTC publish/play pair through a trusted relay service."""

    name = "http-relay"

    def __init__(self, session_url: str, token: str, timeout_seconds: float = 10) -> None:
        self.session_url = session_url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def create(self, experience_session_id: str, garment_id: str) -> RealtimeSessionResult:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = httpx.post(
            self.session_url,
            headers=headers,
            json={
                "experience_session_id": experience_session_id,
                "garment_id": garment_id,
                "max_duration_seconds": 15,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        publish_url = body.get("publish_url")
        play_url = body.get("play_url")
        if not publish_url or not play_url:
            raise ValueError("realtime relay did not return publish_url and play_url")
        return RealtimeSessionResult(
            id=str(body.get("id") or uuid4()),
            experience_session_id=experience_session_id,
            status="ready",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=20),
            client_token=body.get("client_token"),
            publish_url=str(publish_url),
            play_url=str(play_url),
            notice="实时效果由生成模型提供，可能出现衣物边缘或动作不一致。",
        )


class DecartRealtimeProvider(HttpRealtimeProvider):
    """Lucy VTON adapter exposed through a trusted media gateway.

    The Decart realtime SDK is browser/LiveKit based. The gateway terminates
    the mini-program media leg and the Decart leg, so the Decart secret never
    reaches the mini-program.
    """

    name = "decart-lucy-vton"

    def __init__(self, session_url: str, relay_token: str, decart_api_key: str = "", timeout_seconds: float = 10) -> None:
        super().__init__(session_url, relay_token, timeout_seconds)
        self.decart_api_key = decart_api_key

    def create(self, experience_session_id: str, garment_id: str) -> RealtimeSessionResult:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if self.decart_api_key:
            headers["X-Decart-Api-Key"] = self.decart_api_key
        response = httpx.post(
            self.session_url,
            headers=headers,
            json={
                "experience_session_id": experience_session_id,
                "garment_id": garment_id,
                "model": "lucy-vton-latest",
                "max_duration_seconds": 15,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        publish_url = body.get("publish_url")
        play_url = body.get("play_url")
        if not publish_url or not play_url:
            raise ValueError("decart relay did not return publish_url and play_url")
        return RealtimeSessionResult(
            id=str(body.get("id") or uuid4()),
            experience_session_id=experience_session_id,
            status="ready",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=20),
            client_token=body.get("client_token"),
            publish_url=str(publish_url),
            play_url=str(play_url),
            notice="实时画面由 Decart Lucy VTON 生成，最长 15 秒；仅用于体验，不作为尺码或购买决策依据。",
        )
