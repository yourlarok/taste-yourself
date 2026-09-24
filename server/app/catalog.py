from pathlib import Path

from app.domain.experience import CatalogGarment
from app.domain.models import (
    BodyMeasurements,
    FitAnalysisRequest,
    FitPreference,
    GarmentCategory,
    GarmentVariant,
    ProductFitData,
    UserFitProfile,
)

GARMENTS = [
    CatalogGarment(
        id="knit-sand",
        product_id="knit-001",
        name="米色针织上衣",
        category="top",
        tone="sand",
        sizes=["M", "L", "XL"],
        image_url="/api/v1/catalog/garments/knit-sand/image",
    ),
    CatalogGarment(
        id="denim-blue",
        product_id="denim-001",
        name="深蓝牛仔夹克",
        category="outerwear",
        tone="blue",
        sizes=["M", "L", "XL"],
        image_url="/api/v1/catalog/garments/denim-blue/image",
    ),
    CatalogGarment(
        id="coat-brown",
        product_id="coat-001",
        name="棕色短外套",
        category="outerwear",
        tone="brown",
        sizes=["M", "L", "XL"],
        image_url="/api/v1/catalog/garments/coat-brown/image",
    ),
]


def get_garment(garment_id: str) -> CatalogGarment | None:
    return next((item for item in GARMENTS if item.id == garment_id), None)


def get_catalog_garment_path(garment_id: str) -> Path | None:
    garment = get_garment(garment_id)
    if garment is None:
        return None
    target = Path(__file__).parent / "assets" / "garments" / f"{garment.id}.webp"
    return target if target.is_file() else None


def demo_fit_request(garment_id: str) -> FitAnalysisRequest:
    garment = get_garment(garment_id)
    category = (
        GarmentCategory.OUTERWEAR
        if garment and garment.category == "outerwear"
        else GarmentCategory.TOP
    )
    base = 102 if category == GarmentCategory.OUTERWEAR else 94
    return FitAnalysisRequest(
        profile=UserFitProfile(
            user_id="dev-user",
            preference=FitPreference.REGULAR,
            measurements=BodyMeasurements(chest_cm=92),
        ),
        product=ProductFitData(
            product_id=garment.product_id if garment else "unknown",
            category=category,
            variants=[
                GarmentVariant(
                    sku_id=f"{garment_id}-m",
                    size_label="M",
                    measurements_cm={"chest_cm": base},
                ),
                GarmentVariant(
                    sku_id=f"{garment_id}-l",
                    size_label="L",
                    measurements_cm={"chest_cm": base + 6},
                ),
                GarmentVariant(
                    sku_id=f"{garment_id}-xl",
                    size_label="XL",
                    measurements_cm={"chest_cm": base + 14},
                ),
            ],
        ),
    )


def fit_request_for_measurements(
    garment_id: str,
    user_id: str,
    measurements_cm: dict[str, float],
) -> FitAnalysisRequest:
    request = demo_fit_request(garment_id)
    return request.model_copy(
        update={
            "profile": UserFitProfile(
                user_id=user_id,
                preference=FitPreference.REGULAR,
                measurements=BodyMeasurements.model_validate(measurements_cm),
            )
        }
    )
