import json

from a2ui.core import Catalog
from fastapi import FastAPI
from google.adk.models.lite_llm import LiteLlm
from starlette.middleware.cors import CORSMiddleware

from ._config import BackendConfig
from .agents import UiAgent
from .api import health_router, register_ui_agent

_REQUIRED_PROVIDER_ARGS = ("api_key", "api_base", "api_version")
# A stalled model fails with a clear error instead of hanging; override in provider_args.
_DEFAULT_PROVIDER_ARGS = {"timeout": 60, "num_retries": 3}


class App(FastAPI):
    def __init__(self, config: BackendConfig) -> None:
        super().__init__(title="A2UI Agent", docs_url="/docs", redoc_url=None)

        self.add_middleware(
            CORSMiddleware,
            allow_origin_regex=config.web_origin_regex,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.include_router(health_router)

        missing = [k for k in _REQUIRED_PROVIDER_ARGS if not config.llm.provider_args.get(k)]
        if missing:
            raise RuntimeError(f"LLM provider_args is missing {', '.join(missing)} (set it in Backend/.env).")
        try:
            catalog = Catalog.from_json(
                json.loads(config.a2ui_catalog_path.read_text(encoding="utf-8")),
                protocol_version="v0.9",
            )
        except (OSError, ValueError) as e:
            raise RuntimeError(f"Cannot load A2UI catalog {config.a2ui_catalog_path}: {e}") from e

        ui_agent = UiAgent(
            llm=LiteLlm(
                model=config.llm.model_name,
                **{**_DEFAULT_PROVIDER_ARGS, **config.llm.provider_args},
            ),
            catalog=catalog,
            generate_content_config=config.generate_content,
        )
        register_ui_agent(ui_agent, self)
