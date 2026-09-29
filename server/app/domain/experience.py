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
    audience: Literal["women", "men", "unisex"] = "unisex"
    body_types: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    material: str = ""
    silhouette: str = ""


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


class BodyScanCreate(BaseModel):
    experience_session_id: str
    consented: bool


class BodyScanStats(BaseModel):
    age: int = Field(ge=18, le=100)
    gender: Literal["male", "female"]
    height_cm: float = Field(ge=100, le=230)
    weight_kg: float = Field(gt=25, le=250)


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
    provider_scan_id: str | None = Field(default=None, exclude=True)


class BodyScanFrame(BaseModel):
    angle: Literal["front", "side", "back"]
    image_path: str
