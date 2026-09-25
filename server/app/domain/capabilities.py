from typing import Literal

from pydantic import BaseModel

CapabilityState = Literal["ready", "configured", "demo", "partial", "unavailable"]


class CapabilityItem(BaseModel):
    key: str
    label: str
    state: CapabilityState
    provider: str
    notice: str


class CapabilitySnapshot(BaseModel):
    environment: str
    mode: Literal["demo", "mixed", "live"]
    items: list[CapabilityItem]
