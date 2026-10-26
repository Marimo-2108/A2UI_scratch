"""Serve AG-UI runs over HTTP/SSE. Run: uv run a2ui-agent."""

import json
import logging
from collections.abc import AsyncIterator

import uvicorn
from ag_ui.core import RunAgentInput, UserMessage
from ag_ui.encoder import EventEncoder
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .executor import UiExecutor, UiRunProps
from .settings import Settings

log = logging.getLogger(__name__)


def build_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings()
    settings.apply_truststore()
    executor = UiExecutor(settings)
    active_threads: set[str] = set()

    async def run_agent(request: Request) -> Response:
        try:
            run = RunAgentInput.model_validate(await request.json())
            props = UiRunProps.model_validate(run.forwarded_props)
            if not run.thread_id.strip() or not run.run_id.strip():
                raise ValueError("threadId and runId must not be empty.")
            if not run.messages or not isinstance(run.messages[-1], UserMessage):
                raise ValueError("The last message must be a user message.")
            content = run.messages[-1].content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("The last user message must contain non-empty text.")
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            log.warning("Invalid AG-UI request: %s", exc)
            return JSONResponse({"error": str(exc)}, status_code=422)

        if run.thread_id in active_threads:
            log.warning("Concurrent run rejected for thread=%s", run.thread_id)
            return JSONResponse({"error": "A run is already active for this thread."}, status_code=409)
        active_threads.add(run.thread_id)
        encoder = EventEncoder()

        async def stream() -> AsyncIterator[str]:
            try:
                async for event in executor.execute(run, props, content):
                    yield encoder.encode(event)
            finally:
                active_threads.discard(run.thread_id)

        return StreamingResponse(
            stream(),
            media_type=encoder.get_content_type(),
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app = Starlette(routes=[Route("/", run_agent, methods=["POST"])])
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.web_origin_regex,
        allow_methods=["POST"],
        allow_headers=["Content-Type", "Accept"],
    )
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    settings = Settings()
    uvicorn.run(build_app(settings), host=settings.agent_bind_host, port=settings.agent_port)


if __name__ == "__main__":
    main()
