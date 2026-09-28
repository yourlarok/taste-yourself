from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.quota import QuotaRepository


class FailingTryOnProvider:
    def generate_static(self, *args, **kwargs):
        raise ValueError("provider_failed")


def test_quota_repository_consumes_refunds_and_separates_kinds(tmp_path: Path):
    repository = QuotaRepository(tmp_path / "quota.db")

    assert repository.consume("user-1", "static", 1)
    assert not repository.consume("user-1", "static", 1)
    assert repository.consume("user-1", "realtime", 1)
    assert repository.get("user-1") == {"static_count": 1, "realtime_count": 1}

    repository.refund("user-1", "static")
    assert repository.get("user-1") == {"static_count": 0, "realtime_count": 1}


def test_api_enforces_daily_limits_and_reports_usage(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "quota-api.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STATIC_DAILY_LIMIT", "1")
    monkeypatch.setenv("REALTIME_DAILY_LIMIT", "1")
    monkeypatch.setenv("TRYON_PROVIDER", "mock")
    monkeypatch.setenv("REALTIME_PROVIDER", "decart-realtime")
    monkeypatch.setenv("DECART_API_KEY", "test-key")

    class TokenResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"apiKey": "ephemeral"}

    class AsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return TokenResponse()

    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", AsyncClient)

    with TestClient(app) as client:
        app.state.live_mirror_ready = True
        session = client.post(
            "/api/v1/experience-sessions", json={"garment_id": "knit-sand"}
        ).json()
        first_static = client.post(
            f"/api/v1/experience-sessions/{session['id']}/static-tryon", json={}
        )
        second_static = client.post(
            f"/api/v1/experience-sessions/{session['id']}/static-tryon", json={}
        )
        first_realtime = client.post(
            f"/api/v1/experience-sessions/{session['id']}/realtime/client-token"
        )
        second_realtime = client.post(
            f"/api/v1/experience-sessions/{session['id']}/realtime/client-token"
        )
        usage = client.get("/api/v1/me/usage")

    assert first_static.status_code == 200
    assert second_static.status_code == 429
    assert second_static.json()["detail"] == "static_daily_limit_reached"
    assert first_realtime.status_code == 200
    assert second_realtime.status_code == 429
    assert usage.json() == {
        "static": {"used": 1, "limit": 1},
        "realtime": {"used": 1, "limit": 1},
    }


def test_failed_static_provider_refunds_quota(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "quota-refund.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STATIC_DAILY_LIMIT", "1")
    monkeypatch.setenv("TRYON_PROVIDER", "mock")

    with TestClient(app) as client:
        session = client.post(
            "/api/v1/experience-sessions", json={"garment_id": "knit-sand"}
        ).json()
        app.state.tryon_provider = FailingTryOnProvider()
        failed = client.post(
            f"/api/v1/experience-sessions/{session['id']}/static-tryon", json={}
        )
        usage = client.get("/api/v1/me/usage")

    assert failed.status_code == 503
    assert failed.json()["detail"] == "static_tryon_unavailable"
    assert usage.json()["static"] == {"used": 0, "limit": 1}
