from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import GarmentVariant


class GarmentRecord(BaseModel):
    id: str
    user_id: str
    name: str
    category: Literal["tops", "bottoms", "one-pieces"]
    image_path: str
    image_url: str | None = None
    status: Literal["ready", "rejected"]
    width: int
    height: int
    created_at: datetime


class PersonImageRecord(BaseModel):
    id: str
    user_id: str
    image_path: str
    width: int
    height: int
    created_at: datetime


class GarmentSizeChartInput(BaseModel):
    brand: str | None = Field(default=None, max_length=128)
    stretch_percent: float = Field(default=0, ge=0, le=100)
    variants: list[GarmentVariant] = Field(min_length=1, max_length=30)
