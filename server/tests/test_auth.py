from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import InvalidToken, TokenService


def test_token_round_trip_and_tamper_rejection():
    service = TokenService("a-secure-test-secret-that-is-long-enough")
    issued = service.issue("user-123")

    assert service.verify(issued.access_token) == "user-123"

    broken = issued.access_token[:-1] + ("a" if issued.access_token[-1] != "a" else "b")
    try:
        service.verify(broken)
    except InvalidToken as error:
        assert str(error) == "invalid_signature"
    else:
        raise AssertionError("tampered token should be rejected")


def test_dev_login_token_can_create_owned_session(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "auth-dev.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_ENV", "development")

    with TestClient(app) as client:
        auth = client.post("/api/v1/auth/dev-login")
        token = auth.json()["access_token"]
        created = client.post(
            "/api/v1/experience-sessions",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": "spoofed-user", "garment_id": "knit-sand"},
        )

    assert auth.status_code == 200
    assert created.status_code == 201
    assert created.json()["user_id"] == "dev-user"


def test_production_rejects_missing_authentication(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "auth-production.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "a-production-secret-with-at-least-32-characters")
    monkeypatch.setenv("WECHAT_APP_ID", "test-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("TRYON_PROVIDER", "fashn-http")
    monkeypatch.setenv("FASHN_WORKER_URL", "http://worker.test")
    monkeypatch.setenv("REALTIME_PROVIDER", "http")
    monkeypatch.setenv("REALTIME_SESSION_URL", "http://realtime.test/session")
    monkeypatch.setenv("BODY_SCAN_PROVIDER", "http")
    monkeypatch.setenv("BODY_SCAN_WORKER_URL", "http://measurement.test")
    monkeypatch.setenv("CONTENT_SAFETY_PROVIDER", "http")
    monkeypatch.setenv("CONTENT_SAFETY_URL", "http://safety.test")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/experience-sessions",
            json={"garment_id": "knit-sand"},
        )
        dev_login = client.post("/api/v1/auth/dev-login")

    assert response.status_code == 401
    assert dev_login.status_code == 404
