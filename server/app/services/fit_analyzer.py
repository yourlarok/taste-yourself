from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    FitAnalysisRequest,
    FitAnalysisResponse,
    FitAssessment,
    FitPreference,
    GarmentCategory,
    MeasurementReason,
    VariantAnalysis,
)


@dataclass(frozen=True)
class EaseBand:
    minimum: float
    maximum: float
    weight: float


# Garment measurements are finished-garment circumferences, not body measurements.
# The bands are neutral reference ranges, not purchase recommendations.
BASE_RULES: dict[GarmentCategory, dict[str, EaseBand]] = {
    GarmentCategory.TOP: {"chest_cm": EaseBand(4, 10, 1.0)},
    GarmentCategory.OUTERWEAR: {"chest_cm": EaseBand(10, 20, 1.0)},
    GarmentCategory.BOTTOM: {
        "waist_cm": EaseBand(1, 5, 0.55),
        "hip_cm": EaseBand(3, 9, 0.45),
    },
    GarmentCategory.DRESS: {
        "chest_cm": EaseBand(3, 9, 0.4),
        "waist_cm": EaseBand(2, 8, 0.3),
        "hip_cm": EaseBand(3, 10, 0.3),
    },
}

PREFERENCE_SHIFT = {
    FitPreference.SLIM: -2.0,
    FitPreference.REGULAR: 0.0,
    FitPreference.RELAXED: 4.0,
}

SUMMARY = {
    FitAssessment.BELOW_REFERENCE: "穿着余量低于当前参考区间，体感可能更贴身。",
    FitAssessment.WITHIN_REFERENCE: "穿着余量位于当前参考区间内。",
    FitAssessment.ABOVE_REFERENCE: "穿着余量高于当前参考区间，体感可能更宽松。",
    FitAssessment.INSUFFICIENT_DATA: "数据不足，仅展示已知测量信息。",
}


class FitAnalyzer:
    """Describe size differences without ranking sizes or making a purchase decision."""

    def analyze(self, request: FitAnalysisRequest) -> FitAnalysisResponse:
        rules = BASE_RULES[request.product.category]
        body = request.profile.measurements.model_dump()
        missing_body = [name for name in rules if body.get(name) is None]
        shift = PREFERENCE_SHIFT[request.profile.preference]
        variants: list[VariantAnalysis] = []

        for variant in request.product.variants:
            reasons: list[MeasurementReason] = []
            votes: list[tuple[FitAssessment, float]] = []
            missing_product: list[str] = []

            for name, rule in rules.items():
                body_value = body.get(name)
                garment_value = variant.measurements_cm.get(name)
                if garment_value is None:
                    missing_product.append(name)
                    continue
                if body_value is None:
                    continue

                stretch_relief = request.product.stretch_percent * 0.04
                minimum = rule.minimum + shift - stretch_relief
                maximum = rule.maximum + shift
                ease = garment_value - body_value

                if ease < minimum:
                    assessment = FitAssessment.BELOW_REFERENCE
                elif ease > maximum:
                    assessment = FitAssessment.ABOVE_REFERENCE
                else:
                    assessment = FitAssessment.WITHIN_REFERENCE

                votes.append((assessment, rule.weight))
                reasons.append(
                    MeasurementReason(
                        measurement=name,
                        body_cm=round(body_value, 1),
                        garment_cm=round(garment_value, 1),
                        ease_cm=round(ease, 1),
                        target_ease_cm=(round(minimum, 1), round(maximum, 1)),
                        assessment=assessment,
                    )
                )

            if missing_body or missing_product:
                assessment = FitAssessment.INSUFFICIENT_DATA
            else:
                assessment = self._overall_assessment(votes)

            variants.append(
                VariantAnalysis(
                    sku_id=variant.sku_id,
                    size_label=variant.size_label,
                    assessment=assessment,
                    reasons=reasons,
                    missing_product_measurements=missing_product,
                    summary=SUMMARY[assessment],
                )
            )

        return FitAnalysisResponse(
            product_id=request.product.product_id,
            missing_body_measurements=missing_body,
            variants=variants,
            notice=(
                "本结果仅分析人体尺寸、成衣尺寸与参考穿着余量之间的关系；"
                "不对尺码排序，也不替用户作购买决定。"
            ),
        )

    @staticmethod
    def _overall_assessment(votes: list[tuple[FitAssessment, float]]) -> FitAssessment:
        if not votes:
            return FitAssessment.INSUFFICIENT_DATA
        totals = {
            label: 0.0
            for label in (
                FitAssessment.BELOW_REFERENCE,
                FitAssessment.WITHIN_REFERENCE,
                FitAssessment.ABOVE_REFERENCE,
            )
        }
        for label, weight in votes:
            totals[label] += weight
        return max(totals, key=totals.get)
