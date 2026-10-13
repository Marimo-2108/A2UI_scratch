"""The ONLY place that knows which AI vendor we use.

Everything else (prompt building, A2UI validation, retries, memory) works on plain
`Msg(role, text)` turns and gets plain text back. To add another vendor, write one more class
with a `complete()` method and register it in `make_llm()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from config import Settings


@dataclass(frozen=True)
class Msg:
    role: Literal["user", "model"]
    text: str


class Llm(Protocol):
    name: str  # for logs, e.g. "gemini/gemini-3.8-flash"

    async def complete(self, system: str, messages: list[Msg]) -> str: ...


class GeminiLlm:
    def __init__(self, s: Settings) -> None:
        from google import genai
        from google.genai import types

        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (put it in agent/.env).")
        self._types = types
        self._s = s
        self.name = f"gemini/{s.gemini_model}"
        # 429 / 5xx ("high demand") are retried with exponential backoff.
        self._client = genai.Client(
            api_key=s.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=s.llm_timeout_s * 1000,  # milliseconds, applies to each attempt
                retry_options=types.HttpRetryOptions(
                    attempts=3, initial_delay=1.5, max_delay=20,
                    http_status_codes=[429, 500, 502, 503, 504],
                )
            ),
        )

    async def complete(self, system: str, messages: list[Msg]) -> str:
        t = self._types
        resp = await self._client.aio.models.generate_content(
            model=self._s.gemini_model,
            contents=[t.Content(role=m.role, parts=[t.Part(text=m.text)]) for m in messages],
            config=t.GenerateContentConfig(
                system_instruction=system,
                temperature=self._s.temperature,
                # how long the model may "think" first (biggest latency lever)
                thinking_config=t.ThinkingConfig(thinking_level=self._s.thinking_level),
            ),
        )
        return resp.text or ""


class OpenAiLlm:
    def __init__(self, s: Settings) -> None:
        from openai import AsyncOpenAI

        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (put it in agent/.env).")
        if not s.openai_model:
            raise RuntimeError("OPENAI_MODEL is not set (put it in agent/.env).")
        self._s = s
        self.name = f"openai/{s.openai_model}"
        # the SDK retries 429 / 5xx itself with backoff
        self._client = AsyncOpenAI(api_key=s.openai_api_key, max_retries=3, timeout=s.llm_timeout_s)

    async def complete(self, system: str, messages: list[Msg]) -> str:
        # OpenAI names the AI's turns "assistant"; Gemini calls them "model".
        chat = [{"role": "system", "content": system}] + [
            {"role": "assistant" if m.role == "model" else "user", "content": m.text}
            for m in messages
        ]
        kwargs: dict = {"model": self._s.openai_model, "messages": chat}
        if self._s.openai_reasoning_effort:
            # reasoning models take an effort level and reject a custom temperature
            kwargs["reasoning_effort"] = self._s.openai_reasoning_effort
        else:
            kwargs["temperature"] = self._s.temperature
        resp = await self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


def make_llm(s: Settings) -> Llm:
    if s.llm_provider == "gemini":
        return GeminiLlm(s)
    if s.llm_provider == "openai":
        return OpenAiLlm(s)
    raise RuntimeError(f"Unknown LLM_PROVIDER {s.llm_provider!r} (use 'gemini' or 'openai').")

