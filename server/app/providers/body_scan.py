from __future__ import annotations

from pathlib import Path
from typing import Protocol

import httpx

from app.domain.experience import BodyScanResult


class BodyScanProvider(Protocol):
    name: str

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
    ) -> BodyScanResult: ...


class MockBodyScanProvider:
    """Fixed test profile; camera frames are stored but never presented as measured data."""

    name = "mock"

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
    ) -> BodyScanResult:
        required = ["front", "side"]
        missing = [angle for angle in required if angle not in frames]
        if missing:
            return BodyScanResult(
                id=scan_id,
                experience_session_id=experience_session_id,
                status="needs_retake",
                provider=self.name,
                captured_angles=sorted(frames),
                required_angles=missing,
                notice=f"缺少采集角度：{', '.join(missing)}。",
            )
        return BodyScanResult(
            id=scan_id,
            experience_session_id=experience_session_id,
            status="completed",
            provider=self.name,
            measurements_cm={"chest_cm": 92.0, "waist_cm": 76.0, "hip_cm": 94.0},
            measurement_uncertainty_cm={"chest_cm": 0.0, "waist_cm": 0.0, "hip_cm": 0.0},
            captured_angles=sorted(frames),
            required_angles=required,
            notice="开发环境固定测试画像；上传画面仅用于验证采集链路，未据此推断尺寸。",
        )


class HttpBodyScanProvider:
    """Contract adapter for a calibrated body-measurement service."""

    name = "body-measurement-http"

    def __init__(self, base_url: str, token: str, timeout_seconds: float = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
    ) -> BodyScanResult:
        required = ["front", "side"]
        missing = [angle for angle in required if angle not in frames]
        if missing:
            return BodyScanResult(
                id=scan_id,
                experience_session_id=experience_session_id,
                status="needs_retake",
                provider=self.name,
                captured_angles=sorted(frames),
                required_angles=missing,
                notice=f"缺少采集角度：{', '.join(missing)}。",
            )

        headers = {"X-Worker-Token": self.token} if self.token else {}
        with frames["front"].open("rb") as front, frames["side"].open("rb") as side:
            response = httpx.post(
                f"{self.base_url}/v1/measure",
                headers=headers,
                files={
                    "front": (frames["front"].name, front, "image/jpeg"),
                    "side": (frames["side"].name, side, "image/jpeg"),
                },
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "needs_retake":
            requested = [str(item) for item in data.get("required_angles", required)]
            return BodyScanResult(
                id=scan_id,
                experience_session_id=experience_session_id,
                status="needs_retake",
                provider=self.name,
                captured_angles=sorted(frames),
                required_angles=requested,
                notice=str(data.get("notice", "画面质量不足，需要补拍。")),
            )

        measurements = self._validated_values(data.get("measurements_cm", {}))
        uncertainty = self._validated_values(data.get("measurement_uncertainty_cm", {}))
        if not measurements or any(name not in uncertainty for name in measurements):
            raise ValueError("measurement_service_returned_unverifiable_values")
        return BodyScanResult(
            id=scan_id,
            experience_session_id=experience_session_id,
            status="completed",
            provider=self.name,
            measurements_cm=measurements,
            measurement_uncertainty_cm=uncertainty,
            captured_angles=sorted(frames),
            required_angles=required,
            notice="自动测量包含误差范围，只作为尺码差异分析输入。",
        )

    @staticmethod
    def _validated_values(values: dict) -> dict[str, float]:
        result: dict[str, float] = {}
        for name, value in values.items():
            number = float(value)
            if number < 0 or number > 300:
                raise ValueError("measurement_value_out_of_range")
            result[str(name)] = round(number, 1)
        return result
