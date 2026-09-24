from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from app.domain.experience import RealtimeSessionResult, StaticTryOnResult
from app.services.image_storage import LocalImageStorage


class TryOnProvider(Protocol):
    name: str

    def generate_static(
        self,
        experience_session_id: str,
        garment_id: str,
        person_path: Path | None = None,
        garment_path: Path | None = None,
        category: str = "tops",
    ) -> StaticTryOnResult: ...

    def create_realtime(self, experience_session_id: str) -> RealtimeSessionResult: ...


class MockTryOnProvider:
    """Deterministic provider for WeChat DevTools and automated tests."""

    name = "mock"

    def generate_static(
        self,
        experience_session_id: str,
        garment_id: str,
        person_path: Path | None = None,
        garment_path: Path | None = None,
        category: str = "tops",
    ) -> StaticTryOnResult:
        return StaticTryOnResult(
            job_id=str(uuid4()),
            experience_session_id=experience_session_id,
            garment_id=garment_id,
            status="completed",
            provider=self.name,
            preview_token=f"mock:{garment_id}",
            notice="开发环境模拟结果；尚未调用真实生成模型。",
        )

    def create_realtime(self, experience_session_id: str) -> RealtimeSessionResult:
        return RealtimeSessionResult(
            id=str(uuid4()),
            experience_session_id=experience_session_id,
            status="ready",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
            notice="开发环境模拟会话；前端仍严格执行 15 秒上限。",
        )


class FashnHttpTryOnProvider:
    """Calls the self-hosted FASHN GPU worker and stores the generated image locally."""

    name = "fashn-vton-1.5"

    def __init__(
        self,
        base_url: str,
        token: str,
        storage: LocalImageStorage,
        timeout_seconds: float = 180,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.storage = storage
        self.timeout_seconds = timeout_seconds

    def generate_static(
        self,
        experience_session_id: str,
        garment_id: str,
        person_path: Path | None = None,
        garment_path: Path | None = None,
        category: str = "tops",
    ) -> StaticTryOnResult:
        if person_path is None or garment_path is None:
            return StaticTryOnResult(
                job_id=str(uuid4()),
                experience_session_id=experience_session_id,
                garment_id=garment_id,
                status="failed",
                provider=self.name,
                notice="真实静态试穿需要本人定格照片和已上传的衣服图片。",
            )

        headers = {"X-Worker-Token": self.token} if self.token else {}
        with person_path.open("rb") as person_file, garment_path.open("rb") as garment_file:
            response = httpx.post(
                f"{self.base_url}/v1/try-on",
                headers=headers,
                files={
                    "person": (person_path.name, person_file, "image/jpeg"),
                    "garment": (garment_path.name, garment_file, "image/jpeg"),
                },
                data={"category": category},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        stored = self.storage.save_generated(response.content)
        return StaticTryOnResult(
            job_id=str(uuid4()),
            experience_session_id=experience_session_id,
            garment_id=garment_id,
            status="completed",
            provider=self.name,
            result_url=f"/api/v1/media/{stored.relative_path}",
            notice="AI 生成试穿效果仅供视觉体验，不代表真实合身或面料物理效果。",
        )

    def create_realtime(self, experience_session_id: str) -> RealtimeSessionResult:
        return RealtimeSessionResult(
            id=str(uuid4()),
            experience_session_id=experience_session_id,
            status="unavailable",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
            notice="当前开源 FASHN Worker 仅支持静态图像；实时会话尚不可用。",
        )
