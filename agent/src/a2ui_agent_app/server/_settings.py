"""All settings in one place. Values come from environment variables / agent/.env.

Copy .env.example to .env and fill in an API key. Never commit .env.
Variable names match the field names (case-insensitive), e.g. AGENT_MODE -> agent_mode.
"""

import os

from google.genai import types as genai_types
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from a2ui_agent_app.agents import AgentConfig, GeminiConfig, LiteLlmConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("AGENT_ENV_FILE", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    # "scripted" = hard-coded UI (no API key needed). "llm" (alias "gemini") = an AI decides the UI.
    agent_mode: str = "scripted"

    agent_host: str = "localhost"
    # Interface uvicorn listens on. Defaults to `agent_host`; dev container sets 0.0.0.0 so ports forward.
    agent_bind_host: str = ""
    agent_port: int = 10010
    # Which browser origins may call the agent (CORS).
    web_origin_regex: str = r"http://localhost:\d+"
    # Corporate networks often re-sign HTTPS traffic with a company certificate that lives in the
    # OS certificate store but not in Python's bundled one (certifi) -> "self-signed certificate in
    # certificate chain". truststore makes Python use the OS store. Verification stays ON.
    use_system_truststore: bool = True

    # Which AI vendor answers in "llm" mode: gemini | openai
    llm_provider: str = "gemini"

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    # Optional: low | medium | high for reasoning models. Empty = don't send (and use temperature).
    openai_reasoning_effort: str = ""

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.6-flash"
    # (name is historical; used by both providers when no reasoning effort is set)
    gemini_temperature: float = 0.3
    # Gemini 3 "thinking" level: LOW | MEDIUM | HIGH. Measured on our UI prompt: LOW ~5s,
    # MEDIUM ~24s, default ~43s, all producing valid UI. (MINIMAL is rejected by 3.8-flash.)
    gemini_thinking_level: str = "LOW"
    # Give up on a single model call after this many seconds (a stalled model must not hang the UI).
    llm_timeout_s: int = 60
    # How many times to send validation errors back to the model before giving up.
    gemini_max_retries: int = 2

    @model_validator(mode="after")
    def _normalize(self) -> "Settings":
        self.agent_mode = self.agent_mode.lower()
        self.llm_provider = self.llm_provider.lower()
        self.openai_reasoning_effort = self.openai_reasoning_effort.lower()
        self.gemini_thinking_level = self.gemini_thinking_level.upper()
        self.agent_bind_host = self.agent_bind_host or self.agent_host
        return self

    @property
    def llm_enabled(self) -> bool:
        return self.agent_mode in ("llm", "gemini")  # "gemini" = old name, kept as alias

    def apply_truststore(self) -> None:
        if self.use_system_truststore:
            import truststore

            truststore.inject_into_ssl()

    def to_agent_config(self) -> AgentConfig:
        """Translate the flat env settings into the agent's provider config."""
        if self.llm_provider == "gemini":
            if not self.gemini_api_key.get_secret_value():
                raise RuntimeError("GEMINI_API_KEY is not set (put it in agent/.env).")
            return AgentConfig(
                gemini=GeminiConfig(
                    model_name=self.gemini_model,
                    api_key=self.gemini_api_key,
                    timeout_s=self.llm_timeout_s,
                ),
                generate_content=genai_types.GenerateContentConfig(
                    temperature=self.gemini_temperature,
                    # how long the model may "think" first (biggest latency lever)
                    thinking_config=genai_types.ThinkingConfig(
                        thinking_level=self.gemini_thinking_level  # type: ignore[arg-type]
                    ),
                ),
            )
        if self.llm_provider == "openai":
            if not self.openai_api_key.get_secret_value():
                raise RuntimeError("OPENAI_API_KEY is not set (put it in agent/.env).")
            if not self.openai_model:
                raise RuntimeError("OPENAI_MODEL is not set (put it in agent/.env).")
            # LiteLLM retries 429 / 5xx itself with backoff.
            provider_args: dict[str, object] = {
                "timeout": self.llm_timeout_s,
                "num_retries": 3,
            }
            generate_content = None
            if self.openai_reasoning_effort:
                # reasoning models take an effort level and reject a custom temperature
                provider_args["reasoning_effort"] = self.openai_reasoning_effort
            else:
                generate_content = genai_types.GenerateContentConfig(
                    temperature=self.gemini_temperature
                )
            return AgentConfig(
                lite_llm=LiteLlmConfig(
                    model_name=f"openai/{self.openai_model}",
                    api_key=self.openai_api_key,
                    provider_args=provider_args,
                ),
                generate_content=generate_content,
            )
        raise RuntimeError(
            f"Unknown LLM_PROVIDER {self.llm_provider!r} (use 'gemini' or 'openai')."
        )
