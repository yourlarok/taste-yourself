from fastapi.testclient import TestClient

from app.main import app
from app.providers.speech import QwenASRRecognizer, SpeechRecognitionError


class FakeRecognizer:
    name = "qwen-asr"

    def transcribe(self, raw: bytes, content_type: str) -> str:
        assert raw == b"short-audio"
        assert content_type == "audio/mpeg"
        return "我周末去海边穿什么"


def test_mirror_transcription_endpoint_does_not_persist_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "speech.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    with TestClient(app) as client:
        app.state.speech_recognizer = FakeRecognizer()
        response = client.post(
            "/api/v1/mirror/transcriptions",
            files={"audio": ("question.mp3", b"short-audio", "audio/mpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {"text": "我周末去海边穿什么"}
    assert not list((tmp_path / "media").rglob("*.mp3"))


def test_qwen_asr_sends_base64_data_uri(monkeypatch):
    captured = {}

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "帮我拿蓝色夹克"}}]}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("app.providers.speech.httpx.post", fake_post)
    recognizer = QwenASRRecognizer("https://llm.test/v1", "secret", "qwen3-asr-flash")
    text = recognizer.transcribe(b"audio", "audio/mpeg")

    assert text == "帮我拿蓝色夹克"
    body = captured["json"]
    assert body["model"] == "qwen3-asr-flash"
    assert body["asr_options"]["language"] == "zh"
    data_uri = body["messages"][1]["content"][0]["input_audio"]["data"]
    assert data_uri == "data:audio/mpeg;base64,YXVkaW8="


def test_qwen_asr_rejects_unsupported_audio_type():
    recognizer = QwenASRRecognizer("https://llm.test/v1", "secret")
    try:
        recognizer.transcribe(b"audio", "application/octet-stream")
    except SpeechRecognitionError as error:
        assert str(error) == "audio_type_unsupported"
    else:
        raise AssertionError("unsupported audio must be rejected")
