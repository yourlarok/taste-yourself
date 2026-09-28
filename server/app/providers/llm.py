from __future__ import annotations

import json
from typing import Protocol

import httpx


class LLMProvider(Protocol):
    name: str

    def complete_json(self, messages: list[dict]) -> dict: ...


class DisabledLLMProvider:
    name = "disabled"

    def complete_json(self, messages: list[dict]) -> dict:
        raise RuntimeError("mirror_llm_not_configured")


class OpenAICompatibleLLMProvider:
    """Small server-side adapter for Bailian and other OpenAI-compatible chat APIs."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete_json(self, messages: list[dict]) -> dict:
        response = httpx.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.35,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("mirror_llm_invalid_json") from error
        if not isinstance(parsed, dict):
            raise ValueError("mirror_llm_invalid_json")
        return parsed
