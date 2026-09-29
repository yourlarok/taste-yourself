from pathlib import Path

from app.providers.content_safety import (
    BailianContentSafetyProvider,
    HttpContentSafetyProvider,
    WechatImageSafetyProvider,
)


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


def test_bailian_content_safety_uses_guardrail_and_rejects(tmp_path: Path, monkeypatch):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"jpeg-bytes")
    captured = {}

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "choices": [
                    {"message": {"content": '{"action":"reject","categories":["id"]}'}}
                ]
            }

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.content_safety.httpx.post", fake_post)
    provider = BailianContentSafetyProvider(
        "https://workspace.maas.aliyuncs.com/compatible-mode/v1",
        "secret",
        "qwen-vl-plus",
    )

    assert not provider.is_allowed(image, "garment_upload")
    assert captured["headers"]["X-DashScope-DataInspection"] == (
        '{"input":"cip","output":"cip"}'
    )
    assert captured["json"]["model"] == "qwen-vl-plus"
    assert "data:image/jpeg;base64," in captured["json"]["messages"][1]["content"][1][
        "image_url"
    ]["url"]


def test_wechat_image_safety_caches_token_and_allows_image(tmp_path: Path, monkeypatch):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"jpeg-bytes")
    calls = {"token": 0, "check": 0}

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        @staticmethod
        def raise_for_status():
            return None

        def json(self):
            return self.data

    def fake_get(url, **kwargs):
        calls["token"] += 1
        assert kwargs["params"]["appid"] == "app-id"
        assert kwargs["params"]["secret"] == "app-secret"
        return FakeResponse({"access_token": "access-token", "expires_in": 7200})

    def fake_post(url, **kwargs):
        calls["check"] += 1
        assert kwargs["params"] == {"access_token": "access-token"}
        assert kwargs["files"]["media"][2] == "image/jpeg"
        return FakeResponse({"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr("app.providers.content_safety.httpx.get", fake_get)
    monkeypatch.setattr("app.providers.content_safety.httpx.post", fake_post)
    provider = WechatImageSafetyProvider("app-id", "app-secret")

    assert provider.is_allowed(image, "person_upload")
    assert provider.is_allowed(image, "garment_upload")
    assert calls == {"token": 1, "check": 2}


def test_wechat_image_safety_rejects_risky_image(tmp_path: Path, monkeypatch):
    image = tmp_path / "image.webp"
    image.write_bytes(b"webp-bytes")

    class FakeResponse:
        def __init__(self, data):
            self.data = data

        @staticmethod
        def raise_for_status():
            return None

        def json(self):
            return self.data

    monkeypatch.setattr(
        "app.providers.content_safety.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            {"access_token": "access-token", "expires_in": 7200}
        ),
    )
    monkeypatch.setattr(
        "app.providers.content_safety.httpx.post",
        lambda *args, **kwargs: FakeResponse({"errcode": 87014, "errmsg": "risky content"}),
    )

    assert not WechatImageSafetyProvider("app-id", "app-secret").is_allowed(
        image, "garment_upload"
    )
