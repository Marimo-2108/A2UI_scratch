"""Entry point: builds the AgentCard and serves the A2A app.  Run:  uv run python server.py"""

from __future__ import annotations

import logging

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.middleware.cors import CORSMiddleware

from a2ui_ext import agent_extension
from config import settings
from executor import UiExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

HOST, PORT = settings.host, settings.port


def build_card() -> AgentCard:
    return AgentCard(
        name="Scratch A2UI Agent",
        description="Streams A2UI over A2A (mode: scripted or gemini).",
        url=f"http://{HOST}:{PORT}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True, extensions=[agent_extension()]),
        skills=[
            AgentSkill(
                id="welcome_card",
                name="Welcome card",
                description="Shows a welcome card.",
                tags=["demo"],
            )
        ],
    )


def build_app():
    handler = DefaultRequestHandler(
        agent_executor=UiExecutor(), task_store=InMemoryTaskStore()
    )
    app = A2AStarletteApplication(agent_card=build_card(), http_handler=handler).build()
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.web_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
        # the browser must be allowed to READ the response's X-A2A-Extensions header
        expose_headers=["X-A2A-Extensions"],
    )
    return app


if __name__ == "__main__":
    uvicorn.run(build_app(), host=settings.bind_host, port=PORT)

