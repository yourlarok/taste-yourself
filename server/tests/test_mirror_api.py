import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def test_mirror_bootstrap_and_conversation_without_fake_agent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "mirror.db"))
    monkeypatch.setenv("MIRROR_LLM_API_KEY", "")
    monkeypatch.setenv("MIRROR_LLM_BASE_URL", "")
    monkeypatch.setenv("MIRROR_LLM_MODEL", "")

    with TestClient(app) as client:
        bootstrap = client.get("/api/v1/mirror/bootstrap")
        assert bootstrap.status_code == 200
        assert bootstrap.json()["name"] == "猫猫魔镜"
        assert bootstrap.json()["face_test_available_today"] is True

        conversation = client.post("/api/v1/mirror/conversations")
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        unavailable = client.post(
            f"/api/v1/mirror/conversations/{conversation_id}/messages",
            json={"content": "我去海边穿什么？"},
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["detail"] == "mirror_agent_unavailable"


def test_wellbeing_assessment_uses_who5_scoring_and_collects_card(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "wellbeing.db"))

    with TestClient(app) as client:
        questions = client.get("/api/v1/mirror/wellbeing/questions")
        assert questions.status_code == 200
        assert len(questions.json()) == 5

        assessment = client.post(
            "/api/v1/mirror/wellbeing/assessments",
            json={
                "answers": [2, 2, 1, 1, 2],
                "contributors": ["sleep", "workload"],
                "immediate_danger": False,
            },
        )
        assert assessment.status_code == 200
        body = assessment.json()
        assert body["score"] == 32
        assert body["state"] == "strained"
        assert body["card"]["cat_type"] == "苔纹猫"
        assert "不是医学诊断" in body["notice"]

        cards = client.get("/api/v1/mirror/cards")
        assert cards.status_code == 200
        assert len(cards.json()) == 1
        assert cards.json()[0]["family"] == "wellbeing"


def test_wellbeing_immediate_danger_prioritizes_safety(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "urgent.db"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/mirror/wellbeing/assessments",
            json={"answers": [5, 5, 5, 5, 5], "immediate_danger": True},
        )

    assert response.status_code == 200
    assert response.json()["state"] == "urgent"
    assert response.json()["card"]["cat_type"] == "守夜黑猫"


def test_fun_face_is_real_vision_backed_bounded_and_daily_limited(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "fun-face.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("MIRROR_LLM_API_KEY", "test-key")
    monkeypatch.setenv("MIRROR_LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setenv("MIRROR_LLM_MODEL", "text-model")
    monkeypatch.setenv("MIRROR_VISION_MODEL", "vision-model")
    captured = {}

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "photo_quality": 88,
                                    "expression_energy": 74,
                                    "lighting_softness": 61,
                                    "style_clarity": 83,
                                    "eye_contact": 70,
                                    "observations": ["正面构图清晰", "光线较柔和"],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.providers.llm.httpx.post", fake_post)
    image = io.BytesIO()
    Image.new("RGB", (512, 512), (180, 160, 150)).save(image, "JPEG")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/mirror/fun-face/assessments",
            data={"answers_json": "[60, 75, 80]"},
            files={"image": ("face.jpg", image.getvalue(), "image/jpeg")},
        )
        second = client.post(
            "/api/v1/mirror/fun-face/assessments",
            data={"answers_json": "[60, 75, 80]"},
            files={"image": ("face.jpg", image.getvalue(), "image/jpeg")},
        )

    assert response.status_code == 200
    assert all(35 <= score <= 85 for score in response.json()["dimensions"].values())
    assert "不从脸推断人格" in response.json()["notice"]
    assert second.status_code == 429
    assert captured["json"]["model"] == "vision-model"
    assert not list((tmp_path / "media" / "mirror" / "fun-face").rglob("*.jpg"))
