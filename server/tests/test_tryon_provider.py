import io
from pathlib import Path

from PIL import Image

from app.providers.tryon import FashnHttpTryOnProvider
from app.services.image_storage import LocalImageStorage


def make_jpeg(path: Path, color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (320, 480), color=color).save(output, "JPEG")
    raw = output.getvalue()
    path.write_bytes(raw)
    return raw


def test_fashn_http_provider_sends_inputs_and_stores_result(tmp_path: Path, monkeypatch):
    person_path = tmp_path / "person.jpg"
    garment_path = tmp_path / "garment.jpg"
    make_jpeg(person_path, (180, 160, 140))
    make_jpeg(garment_path, (40, 70, 110))
    generated = make_jpeg(tmp_path / "generated.jpg", (80, 90, 100))
    captured = {}

    class FakeResponse:
        content = generated

        @staticmethod
        def raise_for_status():
            return None

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.tryon.httpx.post", fake_post)
    storage = LocalImageStorage(tmp_path / "media")
    provider = FashnHttpTryOnProvider(
        "http://worker:9000/", "secret", storage, timeout_seconds=5
    )

    result = provider.generate_static(
        "session-1",
        "garment-1",
        person_path=person_path,
        garment_path=garment_path,
        category="tops",
    )

    assert result.status == "completed"
    assert result.result_url and result.result_url.startswith("/api/v1/media/results/")
    assert captured["url"] == "http://worker:9000/v1/try-on"
    assert captured["headers"] == {"X-Worker-Token": "secret"}
    assert list((tmp_path / "media" / "results").glob("*.jpg"))


def test_fashn_http_provider_requires_both_images(tmp_path: Path):
    provider = FashnHttpTryOnProvider("http://worker", "", LocalImageStorage(tmp_path))

    result = provider.generate_static("session-1", "garment-1")

    assert result.status == "failed"
    assert result.result_url is None
