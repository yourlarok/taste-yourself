from app.domain.models import FitAnalysisRequest
from app.services.fit_analyzer import FitAnalyzer


def request_for(category: str, measurements: dict, variants: list[dict], preference="regular"):
    return FitAnalysisRequest.model_validate(
        {
            "profile": {"preference": preference, "measurements": measurements},
            "product": {
                "product_id": "product-1",
                "category": category,
                "variants": variants,
            },
        }
    )


def test_top_describes_each_size_without_recommending_one():
    request = request_for(
        "top",
        {"chest_cm": 92},
        [
            {"sku_id": "m", "size_label": "M", "measurements_cm": {"chest_cm": 94}},
            {"sku_id": "l", "size_label": "L", "measurements_cm": {"chest_cm": 100}},
            {"sku_id": "xl", "size_label": "XL", "measurements_cm": {"chest_cm": 108}},
        ],
    )

    result = FitAnalyzer().analyze(request)

    assert [item.size_label for item in result.variants] == ["M", "L", "XL"]
    assert [item.assessment.value for item in result.variants] == [
        "below_reference",
        "within_reference",
        "above_reference",
    ]
    assert "不替用户作购买决定" in result.notice


def test_preference_changes_reference_band_not_size_order():
    variants = [
        {"sku_id": "m", "size_label": "M", "measurements_cm": {"chest_cm": 98}},
        {"sku_id": "l", "size_label": "L", "measurements_cm": {"chest_cm": 104}},
    ]
    regular = FitAnalyzer().analyze(request_for("top", {"chest_cm": 92}, variants))
    relaxed = FitAnalyzer().analyze(
        request_for("top", {"chest_cm": 92}, variants, preference="relaxed")
    )

    assert [item.size_label for item in regular.variants] == ["M", "L"]
    assert [item.size_label for item in relaxed.variants] == ["M", "L"]
    assert regular.variants[0].assessment.value == "within_reference"
    assert relaxed.variants[1].assessment.value == "within_reference"


def test_bottom_analyzes_waist_and_hip():
    request = request_for(
        "bottom",
        {"waist_cm": 76, "hip_cm": 94},
        [
            {
                "sku_id": "30",
                "size_label": "30",
                "measurements_cm": {"waist_cm": 77, "hip_cm": 96},
            },
            {
                "sku_id": "31",
                "size_label": "31",
                "measurements_cm": {"waist_cm": 79, "hip_cm": 100},
            },
        ],
    )

    result = FitAnalyzer().analyze(request)

    assert result.missing_body_measurements == []
    assert all(len(item.reasons) == 2 for item in result.variants)


def test_missing_body_measurements_are_reported_without_guessing():
    request = request_for(
        "dress",
        {"height_cm": 168, "weight_kg": 55},
        [
            {
                "sku_id": "s",
                "size_label": "S",
                "measurements_cm": {"chest_cm": 88, "waist_cm": 72, "hip_cm": 94},
            }
        ],
    )

    result = FitAnalyzer().analyze(request)

    assert set(result.missing_body_measurements) == {"chest_cm", "waist_cm", "hip_cm"}
    assert result.variants[0].assessment.value == "insufficient_data"


def test_incomplete_product_measurements_are_reported():
    request = request_for(
        "bottom",
        {"waist_cm": 76, "hip_cm": 94},
        [
            {
                "sku_id": "incomplete",
                "size_label": "M",
                "measurements_cm": {"waist_cm": 79},
            }
        ],
    )

    result = FitAnalyzer().analyze(request)

    assert result.variants[0].assessment.value == "insufficient_data"
    assert result.variants[0].missing_product_measurements == ["hip_cm"]
