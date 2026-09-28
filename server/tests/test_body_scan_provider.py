import base64
from pathlib import Path

from app.providers.body_scan import BodygramPlatformProvider, HttpBodyScanProvider


def test_http_body_scan_requires_front_and_side(tmp_path: Path):
    front = tmp_path / "front.jpg"
    front.write_bytes(b"frame")
    provider = HttpBodyScanProvider("http://measurement-worker", "secret")

    result = provider.process("scan-1", "session-1", {"front": front}, {})

    assert result.status == "needs_retake"
    assert result.required_angles == ["side"]


def test_http_body_scan_preserves_uncertainty(tmp_path: Path, monkeypatch):
    front = tmp_path / "front.jpg"
    side = tmp_path / "side.jpg"
    front.write_bytes(b"front")
    side.write_bytes(b"side")

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "status": "completed",
                "measurements_cm": {"chest_cm": 92.4, "waist_cm": 75.8},
                "measurement_uncertainty_cm": {"chest_cm": 1.6, "waist_cm": 1.9},
            }

    monkeypatch.setattr(
        "app.providers.body_scan.httpx.post", lambda *args, **kwargs: FakeResponse()
    )
    provider = HttpBodyScanProvider("http://measurement-worker/", "secret")

    result = provider.process("scan-1", "session-1", {"front": front, "side": side}, {
        "age": 30, "gender": "female", "height_cm": 168, "weight_kg": 58
    })

    assert result.status == "completed"
    assert result.measurements_cm == {"chest_cm": 92.4, "waist_cm": 75.8}
    assert result.measurement_uncertainty_cm["chest_cm"] == 1.6


def test_bodygram_maps_real_measurements_and_calibration(tmp_path: Path, monkeypatch):
    front = tmp_path / "front.jpg"
    side = tmp_path / "side.jpg"
    front.write_bytes(b"front-frame")
    side.write_bytes(b"side-frame")
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"entry": {
                "id": "provider-scan-123",
                "status": "success",
                "measurements": [
                    {"name": "bustGirth", "value": 934, "unit": "mm"},
                    {"name": "waistGirth", "value": 781, "unit": "mm"},
                    {"name": "hipGirth", "value": 101.2, "unit": "cm"},
                ],
            }}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.body_scan.httpx.post", fake_post)
    provider = BodygramPlatformProvider("org-1", "secret-key")
    result = provider.process(
        "local-scan",
        "session-1",
        {"front": front, "side": side},
        {"age": 29, "gender": "female", "height_cm": 167.5, "weight_kg": 57.2},
    )

    photo_scan = captured["json"]["photoScan"]
    assert captured["url"] == "https://platform.bodygram.com/api/orgs/org-1/scans"
    assert captured["headers"]["Authorization"] == "secret-key"
    assert photo_scan["height"] == 1675
    assert photo_scan["weight"] == 57200
    assert base64.b64decode(photo_scan["frontPhoto"]) == b"front-frame"
    assert base64.b64decode(photo_scan["rightPhoto"]) == b"side-frame"
    assert result.measurements_cm == {
        "height_cm": 167.5,
        "weight_kg": 57.2,
        "chest_cm": 93.4,
        "waist_cm": 78.1,
        "hip_cm": 101.2,
    }
    assert result.measurement_uncertainty_cm == {}
    assert result.provider_scan_id == "provider-scan-123"


def test_bodygram_rejects_scan_without_body_measurements(tmp_path: Path, monkeypatch):
    front = tmp_path / "front.jpg"
    side = tmp_path / "side.jpg"
    front.write_bytes(b"front")
    side.write_bytes(b"side")

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"entry": {"id": "scan-id", "status": "success", "measurements": []}}

    monkeypatch.setattr(
        "app.providers.body_scan.httpx.post", lambda *args, **kwargs: FakeResponse()
    )
    deleted = []
    monkeypatch.setattr(
        BodygramPlatformProvider,
        "delete_scan",
        lambda self, scan_id: deleted.append(scan_id),
    )
    provider = BodygramPlatformProvider("org-1", "secret-key")

    try:
        provider.process("local", "session", {"front": front, "side": side}, {
            "age": 30, "gender": "male", "height_cm": 180, "weight_kg": 75
        })
    except ValueError as error:
        assert str(error) == "bodygram_returned_no_usable_measurements"
    else:
        raise AssertionError("provider must not create a profile without circumference results")
    assert deleted == ["scan-id"]
