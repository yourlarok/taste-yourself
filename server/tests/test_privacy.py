import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (320, 480), color=(90, 80, 70)).save(output, "JPEG")
    return output.getvalue()


def test_delete_my_data_removes_database_rows_and_media(tmp_path: Path, monkeypatch):
    database = tmp_path / "privacy.db"
    media_root = tmp_path / "media"
    monkeypatch.setenv("DATABASE_PATH", str(database))
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("APP_ENV", "development")

    with TestClient(app) as client:
        garment = client.post(
            "/api/v1/wardrobe/garments",
            data={"name": "待删除衣服", "category": "tops"},
            files={"image": ("garment.jpg", jpeg(), "image/jpeg")},
        ).json()
        person = client.post(
            "/api/v1/person-images",
            files={"image": ("person.jpg", jpeg(), "image/jpeg")},
        ).json()
        garment_file = media_root / garment["image_path"]
        person_file = media_root / person["image_path"]
        assert garment_file.is_file() and person_file.is_file()

        deleted = client.request("DELETE", "/api/v1/me/data", json={"confirmation": "DELETE"})
        listed = client.get("/api/v1/wardrobe/garments")

    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert not garment_file.exists()
    assert not person_file.exists()
    assert listed.json() == []
