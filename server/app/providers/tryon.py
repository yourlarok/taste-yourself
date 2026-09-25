from __future__ import annotations

import base64
import binascii
import time
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


class FashnApiTryOnProvider:
    """Calls FASHN's hosted API and persists the result in our own media storage."""

    name = "fashn-api-v1.6"

    def __init__(
        self,
        api_key: str,
        storage: LocalImageStorage,
        base_url: str = "https://api.fashn.ai/v1",
        timeout_seconds: float = 120,
        poll_interval_seconds: float = 1,
    ) -> None:
        if not api_key:
            raise ValueError("FASHN_API_KEY is required")
        self.api_key = api_key
        self.storage = storage
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

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

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model_name": "tryon-v1.6",
            "inputs": {
                "model_image": self._as_data_uri(person_path),
                "garment_image": self._as_data_uri(garment_path),
                "category": self._normalize_category(category),
                "segmentation_free": True,
                "moderation_level": "conservative",
                "mode": "balanced",
                "num_samples": 1,
                "output_format": "jpeg",
                "return_base64": True,
            },
        }
        run_response = httpx.post(
            f"{self.base_url}/run",
            headers=headers,
            json=payload,
            timeout=min(self.timeout_seconds, 30),
        )
        run_response.raise_for_status()
        run_data = run_response.json()
        job_id = run_data.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("FASHN API did not return a job id")

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            status_response = httpx.get(
                f"{self.base_url}/status/{job_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=min(self.timeout_seconds, 30),
            )
            status_response.raise_for_status()
            status_data = status_response.json()
            status = status_data.get("status")
            if status == "completed":
                output = status_data.get("output")
                if not isinstance(output, list) or not output or not isinstance(output[0], str):
                    raise ValueError("FASHN API completed without an image")
                stored = self.storage.save_generated(self._read_output(output[0]))
                return StaticTryOnResult(
                    job_id=job_id,
                    experience_session_id=experience_session_id,
                    garment_id=garment_id,
                    status="completed",
                    provider=self.name,
                    result_url=f"/api/v1/media/{stored.relative_path}",
                    notice="AI 生成试穿效果仅供视觉体验，不代表真实合身或面料物理效果。",
                )
            if status == "failed":
                return StaticTryOnResult(
                    job_id=job_id,
                    experience_session_id=experience_session_id,
                    garment_id=garment_id,
                    status="failed",
                    provider=self.name,
                    notice="本次生成未完成，额度不会计入成功结果，请稍后重试。",
                )
            if status not in {"starting", "in_queue", "processing"}:
                raise ValueError("FASHN API returned an unknown job status")
            time.sleep(self.poll_interval_seconds)

        raise httpx.TimeoutException("FASHN API job timed out")

    def create_realtime(self, experience_session_id: str) -> RealtimeSessionResult:
        return RealtimeSessionResult(
            id=str(uuid4()),
            experience_session_id=experience_session_id,
            status="unavailable",
            provider=self.name,
            max_duration_seconds=15,
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
            notice="当前 FASHN API 提供静态生成；15 秒动态试衣需使用独立的视频服务。",
        )

    @staticmethod
    def _as_data_uri(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def _normalize_category(category: str) -> str:
        aliases = {
            "top": "tops",
            "outerwear": "tops",
            "bottom": "bottoms",
            "dress": "one-pieces",
        }
        normalized = aliases.get(category, category)
        return normalized if normalized in {"tops", "bottoms", "one-pieces"} else "auto"

    def _read_output(self, output: str) -> bytes:
        if output.startswith("data:image/"):
            try:
                metadata, encoded = output.split(",", maxsplit=1)
                if ";base64" not in metadata:
                    raise ValueError("FASHN API returned a non-base64 data URI")
                return base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as error:
                raise ValueError("FASHN API returned invalid image data") from error

        response = httpx.get(output, timeout=min(self.timeout_seconds, 30))
        response.raise_for_status()
        return response.content
