from pathlib import Path

from app.providers.content_safety import HttpContentSafetyProvider


def test_http_content_safety_sends_scene_and_honors_reject(tmp_path: Path, monkeypatch):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"image")
    captured = {}

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"action": "reject"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.content_safety.httpx.post", fake_post)
    provider = HttpContentSafetyProvider("http://safety/", "secret")

    assert not provider.is_allowed(image, "garment_upload")
    assert captured["url"] == "http://safety/v1/check-image"
    assert captured["data"] == {"scene": "garment_upload"}
    assert captured["headers"] == {"X-Worker-Token": "secret"}


def test_http_content_safety_video_uses_video_endpoint(tmp_path: Path, monkeypatch):
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video")
    captured = {}

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"action": "allow"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.content_safety.httpx.post", fake_post)
    provider = HttpContentSafetyProvider("http://safety", "secret")

    assert provider.is_allowed_video(video, "virtual-tryon-video")
    assert captured["url"] == "http://safety/v1/check-video"
    assert captured["data"] == {"scene": "virtual-tryon-video"}
    assert captured["headers"] == {"X-Worker-Token": "secret"}
