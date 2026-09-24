from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

Centimeters = Annotated[float, Field(gt=0, le=300)]


class GarmentCategory(StrEnum):
    TOP = "top"
    OUTERWEAR = "outerwear"
    BOTTOM = "bottom"
    DRESS = "dress"


class FitPreference(StrEnum):
    SLIM = "slim"
    REGULAR = "regular"
    RELAXED = "relaxed"


class FitLabel(StrEnum):
    TOO_SMALL = "too_small"
    FIT = "fit"
    TOO_LARGE = "too_large"
    INSUFFICIENT_DATA = "insufficient_data"


class FitAssessment(StrEnum):
    BELOW_REFERENCE = "below_reference"
    WITHIN_REFERENCE = "within_reference"
    ABOVE_REFERENCE = "above_reference"
    INSUFFICIENT_DATA = "insufficient_data"


class BodyMeasurements(BaseModel):
    height_cm: Centimeters | None = None
    weight_kg: Annotated[float, Field(gt=0, le=500)] | None = None
    chest_cm: Centimeters | None = None
    waist_cm: Centimeters | None = None
    hip_cm: Centimeters | None = None


class UserFitProfile(BaseModel):
    user_id: str | None = Field(default=None, max_length=128)
    preference: FitPreference = FitPreference.REGULAR
    measurements: BodyMeasurements


class GarmentVariant(BaseModel):
    sku_id: str = Field(min_length=1, max_length=128)
    size_label: str = Field(min_length=1, max_length=32)
    measurements_cm: dict[str, Centimeters]


class ProductFitData(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)
    brand: str | None = Field(default=None, max_length=128)
    category: GarmentCategory
    stretch_percent: Annotated[float, Field(ge=0, le=100)] = 0
    variants: list[GarmentVariant] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sizes_and_skus(self) -> ProductFitData:
        skus = [variant.sku_id for variant in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("sku_id must be unique within a product")
        return self


class FitAnalysisRequest(BaseModel):
    profile: UserFitProfile
    product: ProductFitData


class MeasurementReason(BaseModel):
    measurement: str
    body_cm: float
    garment_cm: float
    ease_cm: float
    target_ease_cm: tuple[float, float]
    assessment: FitAssessment


class VariantAnalysis(BaseModel):
    sku_id: str
    size_label: str
    assessment: FitAssessment
    reasons: list[MeasurementReason]
    missing_product_measurements: list[str]
    summary: str


class FitAnalysisResponse(BaseModel):
    product_id: str
    missing_body_measurements: list[str]
    variants: list[VariantAnalysis]
    notice: str
    profile_source: str | None = None
    measurement_uncertainty_cm: dict[str, float] = Field(default_factory=dict)
    profile_updated_at: str | None = None


class PurchaseOutcome(StrEnum):
    KEPT = "kept"
    EXCHANGED = "exchanged"
    RETURNED = "returned"


class FitFeedback(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    product_id: str = Field(min_length=1, max_length=128)
    sku_id: str = Field(min_length=1, max_length=128)
    size_label: str = Field(min_length=1, max_length=32)
    outcome: PurchaseOutcome
    overall_fit: FitLabel
    area_feedback: dict[str, FitLabel] = Field(default_factory=dict)
    analysis_id: str | None = Field(default=None, max_length=128)
