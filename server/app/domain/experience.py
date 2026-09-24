from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CatalogGarment(BaseModel):
    id: str
    product_id: str
    name: str
    category: str
    tone: str
    sizes: list[str]
    image_url: str


class ExperienceSessionCreate(BaseModel):
    user_id: str = Field(default="dev-user", min_length=1, max_length=128)
    garment_id: str = Field(min_length=1, max_length=128)


class ExperienceSession(BaseModel):
    id: str
    user_id: str
    garment_id: str
    status: Literal["active", "closed"]
    created_at: datetime
    updated_at: datetime


class RecentExperience(BaseModel):
    session_id: str
    garment_id: str
    garment_name: str
    updated_at: datetime
    result_url: str | None = None


class GarmentSelection(BaseModel):
    garment_id: str = Field(min_length=1, max_length=128)


class StaticTryOnResult(BaseModel):
    job_id: str
    experience_session_id: str
    garment_id: str
    status: Literal["completed", "failed"]
    provider: str
    preview_token: str | None = None
    result_url: str | None = None
    notice: str


class StaticTryOnCreate(BaseModel):
    person_image_id: str | None = None


class RealtimeSessionResult(BaseModel):
    id: str
    experience_session_id: str
    status: Literal["ready", "unavailable"]
    provider: str
    max_duration_seconds: int = 15
    expires_at: datetime
    client_token: str | None = None
    publish_url: str | None = None
    play_url: str | None = None
    notice: str


class BodyScanCreate(BaseModel):
    experience_session_id: str
    consented: bool


class BodyScanResult(BaseModel):
    id: str
    experience_session_id: str
    status: Literal["created", "uploading", "processing", "completed", "needs_retake", "failed"]
    provider: str
    measurements_cm: dict[str, float] = Field(default_factory=dict)
    measurement_uncertainty_cm: dict[str, float] = Field(default_factory=dict)
    captured_angles: list[str] = Field(default_factory=list)
    required_angles: list[str] = Field(default_factory=lambda: ["front", "side"])
    notice: str


class BodyScanFrame(BaseModel):
    angle: Literal["front", "side", "back"]
    image_path: str
