import os
from pathlib import Path

from google.genai import types as genai_types
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agents import LiteLlmConfig


class BackendConfig(BaseSettings):
    """Read from environment variables / Backend/.env (see .env.example)."""

    model_config = SettingsConfigDict(
        env_file=os.getenv("AGENT_ENV_FILE", ".env"),
        env_ignore_empty=True,
        extra="ignore",
    )

    # LLM={"model_name": "azure/<deployment>", "provider_args": {"api_key": ..., "api_base": ..., "api_version": ...}}
    llm: LiteLlmConfig
    # GENERATE_CONTENT={"temperature": 0.3}; leave unset for reasoning models.
    generate_content: genai_types.GenerateContentConfig | None = None
    # Basic components + StatCard, exported from the frontend (`npm run export:caps`).
    a2ui_catalog_path: Path = Path("fixtures/stats-v1.catalog.json")

    agent_host: str = "localhost"
    # The dev container binds 0.0.0.0 without changing the default host.
    agent_bind_host: str = ""
    agent_port: int = 10010
    web_origin_regex: str = r"http://localhost:\d+"
    # Trust the OS certificate store (corporate proxies); TLS stays verified.
    use_system_truststore: bool = True
