from pathlib import Path

from app.domain.experience import CatalogGarment

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
