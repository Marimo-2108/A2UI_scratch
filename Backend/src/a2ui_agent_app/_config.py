from pathlib import Path

from google.genai import types as genai_types
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agents import LiteLlmConfig


class BackendConfig(BaseSettings):
    """Read from environment variables / Backend/.env (see .env.example)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    llm: LiteLlmConfig
    generate_content: genai_types.GenerateContentConfig | None = None
    a2ui_catalog_path: Path = Path("fixtures/stats-v1.catalog.json")

    agent_host: str = "localhost"
    agent_port: int = 10010
    web_origin_regex: str = r"http://localhost:\d+"
