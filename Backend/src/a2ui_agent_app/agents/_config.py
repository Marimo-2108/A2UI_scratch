from typing import Any

from pydantic import BaseModel, Field


class LiteLlmConfig(BaseModel):
    """Passed straight to ADK: LiteLlm(model=model_name, **provider_args)."""

    # LiteLLM model string, e.g. "azure/<deployment-name>".
    model_name: str
    # api_key, api_base, api_version, timeout, reasoning_effort, ... Hidden from repr (holds the key).
    provider_args: dict[str, Any] = Field(default_factory=dict, repr=False)
