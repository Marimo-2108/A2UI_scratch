from typing import Any

from google.genai import types as genai_types
from pydantic import BaseModel, SecretStr, model_validator


class GeminiConfig(BaseModel):
    model_name: str
    api_key: SecretStr
    # Give up on a single model call after this many seconds (applies to each retry attempt).
    timeout_s: int = 60


class LiteLlmConfig(BaseModel):
    # LiteLLM model id incl. provider prefix, e.g. "openai/gpt-5.4-nano".
    model_name: str
    api_key: SecretStr
    provider_args: dict[str, Any] = {}

    def to_litellm_kwargs(self) -> dict[str, Any]:
        return {"api_key": self.api_key.get_secret_value(), **self.provider_args}


class AgentConfig(BaseModel):
    gemini: GeminiConfig | None = None
    lite_llm: LiteLlmConfig | None = None
    generate_content: genai_types.GenerateContentConfig | None = None

    @model_validator(mode="after")
    def validate_provider_config(self) -> "AgentConfig":
        # Exactly one provider config must be specified.
        if (self.gemini is None) == (self.lite_llm is None):
            raise ValueError("Exactly one of gemini or lite_llm must be provided.")
        return self
