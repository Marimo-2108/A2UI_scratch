"""Agent settings from environment variables / .env. Azure-hosted models only, via LiteLLM."""

import os
from typing import Any

from google.genai import types as genai_types
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AZURE_PREFIXES = ("azure/", "azure_ai/")


class LiteLlmConfig(BaseModel):
    """Passed straight to ADK's LiteLlm: ``LiteLlm(model=model_name, **provider_args)``."""

    # LiteLLM model string, e.g. "azure/<deployment-name>".
    model_name: str
    # api_key, api_base, api_version, timeout, reasoning_effort, ... Kept out of repr (holds the key).
    provider_args: dict[str, Any] = Field(default_factory=dict, repr=False)

class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("AGENT_ENV_FILE", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    # LLM={"model_name": "azure/...", "provider_args": {"api_key": ..., "api_base": ..., ...}}
    llm: LiteLlmConfig | None = None
    # GENERATE_CONTENT={"temperature": 0.3}; leave unset for reasoning models (they reject temperature).
    generate_content: genai_types.GenerateContentConfig | None = None
    llm_max_retries: int = 2
