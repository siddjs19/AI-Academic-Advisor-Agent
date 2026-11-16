"""LLM provider abstraction.

`stub` is not a fake model: it means "no generation available". Features that
need generation say so plainly instead of returning invented content, while
every deterministic capability (planning, grading of objective questions,
spaced repetition, analytics) keeps working with no key at all.
"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from ..config import settings


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str
    enabled: bool

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...

    def complete_text(self, system: str, user: str) -> str: ...


class StubLLM:
    name = "stub"
    enabled = False

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        raise LLMError("no model configured — set LLM_PROVIDER and LLM_API_KEY")

    def complete_text(self, system: str, user: str) -> str:
        raise LLMError("no model configured — set LLM_PROVIDER and LLM_API_KEY")


class GeminiLLM:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY missing")
        self.api_key, self.model = api_key, model
        self.name = f"gemini:{model}"
        self.enabled = True

    def _call(self, system: str, user: str, json_mode: bool) -> str:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3 if json_mode else 0.6},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        try:
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json=body,
                timeout=90,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: could not reach the provider ({exc.__class__.__name__})") from exc

        if r.status_code >= 400:
            raise LLMError(f"gemini {r.status_code}: {r.text[:180]}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return _loose_json(self._call(system, user, True))

    def complete_text(self, system: str, user: str) -> str:
        return self._call(system, user, False).strip()


class GroqLLM:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY missing")
        self.api_key, self.model = api_key, model
        self.name = f"groq:{model}"
        self.enabled = True

    def _call(self, system: str, user: str, json_mode: bool) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.3 if json_mode else 0.6,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(
                f"https://api.groq.com/openai/v1/chat/completions",
                params={"key": self.api_key},
                json=body,
                timeout=90,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: could not reach the provider ({exc.__class__.__name__})") from exc

        if r.status_code >= 400:
            raise LLMError(f"groq {r.status_code}: {r.text[:180]}")
        return r.json()["choices"][0]["message"]["content"]

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return _loose_json(self._call(system, user, True))

    def complete_text(self, system: str, user: str) -> str:
        return self._call(system, user, False).strip()


class OpenAICompatLLM:
    """Any OpenAI-compatible endpoint (vLLM, Ollama, OpenRouter, LM Studio)."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key, self.model = api_key, model
        self.name = f"openai:{model}"
        self.enabled = True

    def _call(self, system: str, user: str, json_mode: bool) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.3 if json_mode else 0.6,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                params={"key": self.api_key},
                json=body,
                timeout=90,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name}: could not reach the provider ({exc.__class__.__name__})") from exc

        if r.status_code >= 400:
            raise LLMError(f"provider {r.status_code}: {r.text[:180]}")
        return r.json()["choices"][0]["message"]["content"]

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return _loose_json(self._call(system, user, True))

    def complete_text(self, system: str, user: str) -> str:
        return self._call(system, user, False).strip()


def _loose_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise LLMError("model did not return JSON")
        return json.loads(m.group(0))


def get_llm() -> LLM:
    provider = (settings.llm_provider or "stub").lower()
    try:
        if provider == "gemini":
            return GeminiLLM(settings.llm_api_key, settings.llm_model)
        if provider == "groq":
            return GroqLLM(settings.llm_api_key, settings.llm_model)
        if provider == "openai" and settings.llm_base_url:
            return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    except ValueError:
        return StubLLM()
    return StubLLM()
