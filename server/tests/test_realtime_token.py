from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_realtime_token_is_short_lived_and_model_scoped(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "realtime.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("REALTIME_PROVIDER", "decart-realtime")
    monkeypatch.setenv("DECART_API_KEY", "server-only-test-key")

    observed = {}

    class TokenResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"apiKey": "ek-short-lived-test-token", "expiresAt": "soon"}

    class AsyncClient:
        def __init__(self, timeout):
            observed["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            observed.update(url=url, headers=headers, body=json)
            return TokenResponse()

    monkeypatch.setattr("app.api.routes.httpx.AsyncClient", AsyncClient)

    with TestClient(app) as client:
        app.state.live_mirror_ready = True
        session = client.post(
            "/api/v1/experience-sessions", json={"garment_id": "knit-sand"}
        ).json()
        response = client.post(
            f"/api/v1/experience-sessions/{session['id']}/realtime/client-token"
        )

    assert response.status_code == 200
    assert response.json() == {"apiKey": "ek-short-lived-test-token", "expiresAt": "soon"}
    assert observed["url"] == "https://api.decart.ai/v1/client/tokens"
    assert observed["headers"] == {"x-api-key": "server-only-test-key"}
    assert observed["body"]["allowedModels"] == ["lucy-vton-latest"]
    assert observed["body"]["allowedOrigins"] == ["https://tryon.xuefeitryon.com"]
    assert observed["body"]["constraints"]["realtime"]["maxSessionDuration"] == 120


def test_realtime_token_fails_closed_for_mock_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "realtime-mock.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("REALTIME_PROVIDER", "mock")
    monkeypatch.setenv("DECART_API_KEY", "test-key")

    with TestClient(app) as client:
        session = client.post(
            "/api/v1/experience-sessions", json={"garment_id": "knit-sand"}
        ).json()
        response = client.post(
            f"/api/v1/experience-sessions/{session['id']}/realtime/client-token"
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "realtime_tryon_unavailable"
