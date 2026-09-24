from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
