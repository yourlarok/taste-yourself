import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def scan_frame() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (320, 480), color=(120, 110, 100)).save(output, "JPEG")
    return output.getvalue()


def test_devtools_vertical_slice(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "experience.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    with TestClient(app) as client:
        catalog = client.get("/api/v1/catalog/garments")
        assert catalog.status_code == 200
        assert len(catalog.json()) == 3
        catalog_image = client.get(catalog.json()[0]["image_url"])
        assert catalog_image.status_code == 200
        assert catalog_image.headers["content-type"] == "image/webp"

        created = client.post(
            "/api/v1/experience-sessions",
            json={"user_id": "tester", "garment_id": "knit-sand"},
        )
        assert created.status_code == 201
        session_id = created.json()["id"]

        static_result = client.post(
            f"/api/v1/experience-sessions/{session_id}/static-tryon"
        )
        assert static_result.status_code == 200
        assert static_result.json()["preview_token"] == "mock:knit-sand"

        recent = client.get("/api/v1/me/recent-experience")
        assert recent.status_code == 200
        assert recent.json()["garment_name"] == "米色针织上衣"

        selected = client.put(
            f"/api/v1/experience-sessions/{session_id}/garment",
            json={"garment_id": "denim-blue"},
        )
        assert selected.json()["garment_id"] == "denim-blue"

        analysis = client.get("/api/v1/catalog/garments/denim-blue/fit-demo")
        assert analysis.status_code == 404

        scan = client.post(
            "/api/v1/body-scans",
            json={"experience_session_id": session_id, "consented": True},
        )
        assert scan.status_code == 503
        assert scan.json()["detail"] == "body_measurement_unavailable"

        personal_analysis = client.get(
            "/api/v1/catalog/garments/denim-blue/fit-analysis"
        )
        assert personal_analysis.status_code == 409


        uploaded = client.post(
            "/api/v1/wardrobe/garments",
            data={"name": "用户衬衫", "category": "tops"},
            files={"image": ("shirt.jpg", scan_frame(), "image/jpeg")},
        )
        assert uploaded.status_code == 201
        uploaded_id = uploaded.json()["id"]

        missing_chart = client.get(f"/api/v1/garments/{uploaded_id}/fit-analysis")
        assert missing_chart.status_code == 409
        assert missing_chart.json()["detail"] == "fit_profile_required"

        chart = client.put(
            f"/api/v1/wardrobe/garments/{uploaded_id}/size-chart",
            json={
                "brand": "测试品牌",
                "stretch_percent": 0,
                "variants": [
                    {
                        "sku_id": "shirt-m",
                        "size_label": "M",
                        "measurements_cm": {"chest_cm": 100, "waist_cm": 96},
                    },
                    {
                        "sku_id": "shirt-l",
                        "size_label": "L",
                        "measurements_cm": {"chest_cm": 106, "waist_cm": 102},
                    },
                ],
            },
        )
        assert chart.status_code == 200
        assert chart.json()["product_id"] == uploaded_id
        assert chart.json()["category"] == "top"

        uploaded_analysis = client.get(f"/api/v1/garments/{uploaded_id}/fit-analysis")
        assert uploaded_analysis.status_code == 409
        assert uploaded_analysis.json()["detail"] == "fit_profile_required"

        cleared = client.delete("/api/v1/me/fit-profile")
        assert cleared.json()["deleted"] == 0
        assert (
            client.get("/api/v1/catalog/garments/denim-blue/fit-analysis").status_code
            == 409
        )


def test_unknown_garment_and_session_return_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "not-found.db"))

    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/experience-sessions",
                json={"garment_id": "missing"},
            ).status_code
            == 404
        )
        assert (
            client.post("/api/v1/experience-sessions/missing/static-tryon").status_code
            == 404
        )
