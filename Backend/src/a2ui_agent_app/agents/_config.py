from typing import Any

from pydantic import BaseModel, Field


class LiteLlmConfig(BaseModel):
    """Passed straight to ADK: LiteLlm(model=model_name, **provider_args)."""

    model_name: str
    provider_args: dict[str, Any] = Field(default_factory=dict, repr=False)
