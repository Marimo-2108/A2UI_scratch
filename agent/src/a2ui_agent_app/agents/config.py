"""Agent settings from environment variables / .env. Existing variable names are preserved."""

import os
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("AGENT_ENV_FILE", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    llm_provider: Literal["gemini", "openai"] = "gemini"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.6-flash"
    gemini_thinking_level: Literal["MINIMAL", "LOW", "MEDIUM", "HIGH"] = "LOW"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_reasoning_effort: str = ""
    # The GEMINI_ prefix is historical; these two settings apply to both providers.
    gemini_temperature: float = 0.3
    gemini_max_retries: int = 2
    llm_timeout_s: int = 60

    @field_validator("llm_provider", "openai_reasoning_effort", mode="before")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        return value.lower()

    @field_validator("gemini_thinking_level", mode="before")
    @classmethod
    def _uppercase(cls, value: str) -> str:
        return value.upper()
