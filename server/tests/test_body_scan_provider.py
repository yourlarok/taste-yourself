from pathlib import Path

from app.providers.body_scan import HttpBodyScanProvider


def test_http_body_scan_requires_front_and_side(tmp_path: Path):
    front = tmp_path / "front.jpg"
    front.write_bytes(b"frame")
    provider = HttpBodyScanProvider("http://measurement-worker", "secret")

    result = provider.process("scan-1", "session-1", {"front": front})

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

    result = provider.process("scan-1", "session-1", {"front": front, "side": side})

    assert result.status == "completed"
    assert result.measurements_cm == {"chest_cm": 92.4, "waist_cm": 75.8}
    assert result.measurement_uncertainty_cm["chest_cm"] == 1.6
