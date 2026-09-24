from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_feedback(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

        response = client.post(
            "/api/v1/fit-feedback",
            json={
                "user_id": "user-1",
                "product_id": "product-1",
                "sku_id": "sku-l",
                "size_label": "L",
                "outcome": "kept",
                "overall_fit": "fit",
                "area_feedback": {"chest": "fit"},
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "accepted"


def test_fit_analysis_endpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/fit/analyze",
            json={
                "profile": {
                    "preference": "regular",
                    "measurements": {"chest_cm": 92},
                },
                "product": {
                    "product_id": "tee-1",
                    "category": "top",
                    "variants": [
                        {
                            "sku_id": "tee-m",
                            "size_label": "M",
                            "measurements_cm": {"chest_cm": 98},
                        }
                    ],
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "recommended_size" not in body
    assert "confidence" not in body
    assert body["variants"][0]["assessment"] == "within_reference"
