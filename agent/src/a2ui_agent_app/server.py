"""Entry point: builds the AgentCard and serves the A2A app.  Run:  uv run a2ui-agent"""

import logging

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from .a2ui import agent_extension
from .executor import UiExecutor
from .settings import Settings


def build_card(settings: Settings) -> AgentCard:
    return AgentCard(
        name="Scratch A2UI Agent",
        description="Streams A2UI over A2A; an LLM decides the UI.",
        url=f"http://{settings.agent_host}:{settings.agent_port}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True, extensions=[agent_extension()]),
        skills=[
            AgentSkill(
                id="generate_ui",
                name="Generate UI",
                description="Answers a request with a small user interface (A2UI).",
                tags=["a2ui", "ui"],
            )
        ],
    )


def build_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings()
    settings.apply_truststore()
    handler = DefaultRequestHandler(
        agent_executor=UiExecutor(settings), task_store=InMemoryTaskStore()
    )
    app = A2AStarletteApplication(agent_card=build_card(settings), http_handler=handler).build()
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.web_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
        # the browser must be allowed to READ the response's X-A2A-Extensions header
        expose_headers=["X-A2A-Extensions"],
    )
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    settings = Settings()
    uvicorn.run(build_app(settings), host=settings.agent_bind_host, port=settings.agent_port)


if __name__ == "__main__":
    main()
