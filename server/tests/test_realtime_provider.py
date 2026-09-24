from datetime import datetime

import httpx
import pytest

from app.providers.realtime import HttpRealtimeProvider


def test_http_realtime_provider_enforces_15_seconds(monkeypatch):
    captured: dict = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={
                "id": "relay-1",
                "publish_url": "webrtc://relay.example/publish",
                "play_url": "webrtc://relay.example/play",
                "max_duration_seconds": 600,
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = HttpRealtimeProvider("https://relay.example/v1/sessions", "secret")
    result = provider.create("experience-1", "garment-1")

    assert captured["json"]["max_duration_seconds"] == 15
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert result.max_duration_seconds == 15
    assert result.publish_url == "webrtc://relay.example/publish"
    assert isinstance(result.expires_at, datetime)


def test_http_realtime_provider_rejects_incomplete_stream_pair(monkeypatch):
    def fake_post(url, headers, json, timeout):
        return httpx.Response(
            200,
            json={"publish_url": "webrtc://relay.example/publish"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = HttpRealtimeProvider("https://relay.example/v1/sessions", "")

    with pytest.raises(ValueError, match="publish_url and play_url"):
        provider.create("experience-1", "garment-1")
