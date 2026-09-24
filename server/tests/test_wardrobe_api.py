import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def image_bytes(width: int = 320, height: int = 480) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), color=(87, 104, 120)).save(output, format="PNG")
    return output.getvalue()


def test_upload_list_and_read_garment_image(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "wardrobe.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    with TestClient(app) as client:
        uploaded = client.post(
            "/api/v1/wardrobe/garments",
            data={"user_id": "user-1", "name": "蓝色衬衫", "category": "tops"},
            files={"image": ("shirt.png", image_bytes(), "image/png")},
        )
        assert uploaded.status_code == 201
        garment = uploaded.json()
        assert garment["status"] == "ready"
        assert garment["image_path"].startswith("garments/")
        assert "signature=" in garment["image_url"]

        listed = client.get("/api/v1/wardrobe/garments", params={"user_id": "user-1"})
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [garment["id"]]

        media = client.get(f"/api/v1/media/{garment['image_path']}")
        assert media.status_code == 200
        assert media.headers["content-type"] == "image/jpeg"

        session = client.post(
            "/api/v1/experience-sessions",
            json={"user_id": "user-1", "garment_id": garment["id"]},
        )
        assert session.status_code == 201


def test_rejects_invalid_or_tiny_images(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "invalid.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    with TestClient(app) as client:
        invalid = client.post(
            "/api/v1/wardrobe/garments",
            data={"user_id": "user-1", "name": "坏文件", "category": "tops"},
            files={"image": ("not-image.png", b"not an image", "image/png")},
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == "invalid_image"

        tiny = client.post(
            "/api/v1/person-images",
            data={"user_id": "user-1"},
            files={"image": ("tiny.png", image_bytes(64, 64), "image/png")},
        )
        assert tiny.status_code == 422
        assert tiny.json()["detail"] == "image_too_small"
