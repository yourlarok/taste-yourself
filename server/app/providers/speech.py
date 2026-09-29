from __future__ import annotations

import base64

import httpx

MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
    "audio/mp4": "audio/mp4",
    "audio/x-m4a": "audio/mp4",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
}


class SpeechRecognitionError(ValueError):
    pass


class DisabledSpeechRecognizer:
    name = "disabled"

    def transcribe(self, raw: bytes, content_type: str) -> str:
        raise RuntimeError("mirror_asr_not_configured")


class QwenASRRecognizer:
    """Short-utterance ASR through Bailian's OpenAI-compatible endpoint."""

    name = "qwen-asr"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "qwen3-asr-flash",
        timeout_seconds: float = 45,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def transcribe(self, raw: bytes, content_type: str) -> str:
        if not raw or len(raw) > MAX_AUDIO_BYTES:
            raise SpeechRecognitionError("audio_size_invalid")
        media_type = ALLOWED_AUDIO_TYPES.get(content_type.lower().split(";", 1)[0])
        if media_type is None:
            raise SpeechRecognitionError("audio_type_unsupported")
        data_uri = f"data:{media_type};base64,{base64.b64encode(raw).decode('ascii')}"
        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "猫猫魔镜、试衣间、衣橱、尺码、海边穿搭。",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": data_uri},
                            }
                        ],
                    },
                ],
                "stream": False,
                "asr_options": {"language": "zh", "enable_itn": True},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            text = str(response.json()["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise SpeechRecognitionError("asr_invalid_response") from error
        if not text:
            raise SpeechRecognitionError("asr_empty_result")
        return text[:1000]
