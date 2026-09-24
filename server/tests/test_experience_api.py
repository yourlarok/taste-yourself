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
        assert analysis.status_code == 200
        assert len(analysis.json()["variants"]) == 3
        assert "recommended_size" not in analysis.json()

        realtime = client.post(f"/api/v1/experience-sessions/{session_id}/realtime")
        assert realtime.status_code == 200
        assert realtime.json()["max_duration_seconds"] == 15

        scan = client.post(
            "/api/v1/body-scans",
            json={"experience_session_id": session_id, "consented": True},
        )
        assert scan.status_code == 201
        assert scan.json()["provider"] == "mock"
        assert scan.json()["status"] == "created"
        scan_id = scan.json()["id"]

        for angle in ("front", "side"):
            frame = client.post(
                f"/api/v1/body-scans/{scan_id}/frames",
                data={"angle": angle},
                files={"image": (f"{angle}.jpg", scan_frame(), "image/jpeg")},
            )
            assert frame.status_code == 200

        completed = client.post(f"/api/v1/body-scans/{scan_id}/complete")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["measurements_cm"]["chest_cm"] == 92.0
        assert not list((tmp_path / "media" / "scans" / scan_id).glob("*.jpg"))

        personal_analysis = client.get(
            "/api/v1/catalog/garments/denim-blue/fit-analysis"
        )
        assert personal_analysis.status_code == 200
        assert personal_analysis.json()["profile_source"] == "mock"
        assert personal_analysis.json()["variants"][0]["reasons"][0]["body_cm"] == 92.0

        cleared = client.delete("/api/v1/me/fit-profile")
        assert cleared.json()["deleted"] == 1
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
