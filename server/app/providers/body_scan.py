from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx
from PIL import Image, ImageStat

from app.domain.experience import BodyScanResult


class BodyScanProvider(Protocol):
    name: str

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
        stats: dict[str, str | int | float],
    ) -> BodyScanResult: ...


class DisabledBodyScanProvider:
    """Fail closed when no real measurement provider has been configured."""

    name = "disabled"

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
        stats: dict[str, str | int | float],
    ) -> BodyScanResult:
        raise RuntimeError("body_measurement_provider_not_configured")


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
        stats: dict[str, str | int | float],
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
                data=stats,
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


class BodygramPlatformProvider:
    """Server-side adapter for Bodygram's photo-based measurement API."""

    name = "bodygram-platform"
    API_ROOT = "https://platform.bodygram.com/api/orgs"
    MEASUREMENT_MAP = {
        "bustGirth": "chest_cm",
        "chestGirth": "chest_cm",
        "waistGirth": "waist_cm",
        "hipGirth": "hip_cm",
    }

    def __init__(
        self,
        organization_id: str,
        api_key: str,
        timeout_seconds: float = 90,
    ) -> None:
        self.organization_id = organization_id
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.endpoint = f"{self.API_ROOT}/{quote(organization_id, safe='')}/scans"

    @staticmethod
    def normalize_frame(path: Path) -> None:
        """Contain a portrait capture in Bodygram's required 720x1280 JPEG frame."""
        with Image.open(path) as source:
            if source.width < 480 or source.height <= source.width:
                raise ValueError("body_scan_frame_must_be_full_length_portrait")
            image = source.convert("RGB")
        background = tuple(int(value) for value in ImageStat.Stat(image.resize((24, 24))).median)
        image.thumbnail((720, 1280), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (720, 1280), background)
        canvas.paste(image, ((720 - image.width) // 2, (1280 - image.height) // 2))
        for quality in (88, 82, 76, 70):
            output = io.BytesIO()
            canvas.save(output, format="JPEG", quality=quality, optimize=True)
            if output.tell() <= 3 * 1024 * 1024:
                path.write_bytes(output.getvalue())
                return
        raise ValueError("body_scan_frame_cannot_be_compressed")

    def process(
        self,
        scan_id: str,
        experience_session_id: str,
        frames: dict[str, Path],
        stats: dict[str, str | int | float],
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

        photo_scan = {
            "age": int(stats["age"]),
            "gender": str(stats["gender"]),
            "height": round(float(stats["height_cm"]) * 10),
            "weight": round(float(stats["weight_kg"]) * 1000),
            "frontPhoto": base64.b64encode(frames["front"].read_bytes()).decode("ascii"),
            "rightPhoto": base64.b64encode(frames["side"].read_bytes()).decode("ascii"),
        }
        response = httpx.post(
            self.endpoint,
            headers={"Authorization": self.api_key, "Content-Type": "application/json"},
            json={"photoScan": photo_scan},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        entry = response.json().get("entry") or {}
        provider_scan_id = entry.get("id")
        if entry.get("status") != "success" or not provider_scan_id:
            if provider_scan_id:
                self.delete_scan(str(provider_scan_id))
            raise ValueError("bodygram_measurement_failed")

        try:
            measurements: dict[str, float] = {
                "height_cm": round(float(stats["height_cm"]), 1),
                "weight_kg": round(float(stats["weight_kg"]), 1),
            }
            for measurement in entry.get("measurements") or []:
                target = self.MEASUREMENT_MAP.get(str(measurement.get("name")))
                if not target:
                    continue
                value = float(measurement["value"])
                unit = str(measurement.get("unit", "mm"))
                centimeters = value / 10 if unit == "mm" else value
                if unit not in {"mm", "cm"} or not 0 < centimeters <= 300:
                    raise ValueError("bodygram_measurement_value_invalid")
                measurements[target] = round(centimeters, 1)

            if not any(key in measurements for key in ("chest_cm", "waist_cm", "hip_cm")):
                raise ValueError("bodygram_returned_no_usable_measurements")
        except (KeyError, TypeError, ValueError):
            self.delete_scan(str(provider_scan_id))
            raise

        return BodyScanResult(
            id=scan_id,
            experience_session_id=experience_session_id,
            status="completed",
            provider=self.name,
            measurements_cm=measurements,
            measurement_uncertainty_cm={},
            captured_angles=sorted(frames),
            required_angles=required,
            notice="基于正、侧面照片与校准资料估算；Bodygram 未提供逐项误差区间，不作为购买结论。",
            provider_scan_id=str(provider_scan_id),
        )

    def delete_scan(self, provider_scan_id: str) -> None:
        response = httpx.delete(
            f"{self.endpoint}/{quote(provider_scan_id, safe='')}",
            headers={"Authorization": self.api_key},
            timeout=20,
        )
        if response.status_code == 404:
            return
        response.raise_for_status()
