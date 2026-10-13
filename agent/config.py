"""All settings in one place. Values come from environment variables / agent/.env.

Copy .env.example to .env and fill in GEMINI_API_KEY. Never commit .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Corporate networks often re-sign HTTPS traffic with a company certificate that lives in the
# OS certificate store but not in Python's bundled one (certifi) -> "self-signed certificate in
# certificate chain". truststore makes Python use the OS store. Verification stays ON.
if os.getenv("USE_SYSTEM_TRUSTSTORE", "1") == "1":
    import truststore

    truststore.inject_into_ssl()


@dataclass(frozen=True)
class Settings:
    # "scripted" = Milestone 2 hard-coded UI (no API key needed). "gemini" = Milestone 4.
    agent_mode: str = os.getenv("AGENT_MODE", "scripted").lower()

    host: str = os.getenv("AGENT_HOST", "localhost")
    port: int = int(os.getenv("AGENT_PORT", "10010"))
    # Which browser origins may call the agent (CORS).
    web_origin_regex: str = os.getenv("WEB_ORIGIN_REGEX", r"http://localhost:\d+")

    # Which AI vendor answers in "gemini" mode (the mode name is historical): gemini | openai
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "")
    # Optional: low | medium | high for reasoning models. Empty = don't send (and use temperature).
    openai_reasoning_effort: str = os.getenv("OPENAI_REASONING_EFFORT", "").lower()

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
    # Gemini 3 "thinking" level: LOW | MEDIUM | HIGH. Measured on our UI prompt: LOW ~5s,
    # MEDIUM ~24s, default ~43s, all producing valid UI. (MINIMAL is rejected by 3.8-flash.)
    thinking_level: str = os.getenv("GEMINI_THINKING_LEVEL", "LOW").upper()
    # Give up on a single model call after this many seconds (a stalled model must not hang the UI).
    llm_timeout_s: int = int(os.getenv("LLM_TIMEOUT_S", "60"))
    # How many times to send validation errors back to the model before giving up.
    max_retries: int = int(os.getenv("GEMINI_MAX_RETRIES", "2"))


settings = Settings()


