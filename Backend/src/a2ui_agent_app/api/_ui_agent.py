import re
from collections.abc import AsyncGenerator
from contextlib import aclosing

from ag_ui.core import BaseEvent, EventType, RunAgentInput
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI
from google.adk.agents.run_config import RunConfig, StreamingMode

from ..agents import UiAgent


class _UiAgUiAgent(ADKAgent):
    async def run(self, input: RunAgentInput) -> AsyncGenerator[BaseEvent, None]:
        # ag_ui_adk sends RUN_FINISHED after RUN_ERROR; AG-UI clients reject events after an error,
        # which would hide the real message. End the stream at the error instead.
        async with aclosing(super().run(input)) as events:
            async for event in events:
                if event.type == EventType.RUN_ERROR:
                    yield event.model_copy(update={"message": _short_error(event.message)})
                    return
                yield event


def _short_error(message: str) -> str:
    # A proxy/firewall answering instead of Azure returns a whole HTML page; keep only its title.
    if "<html" not in message.lower():
        return message
    title = re.search(r"<title>(.*?)</title>", message, re.IGNORECASE | re.DOTALL)
    head = message.split("<", 1)[0].strip(" -:\n")
    page = title.group(1).strip() if title else "an HTML page"
    return f"{head} - the endpoint returned {page!r} instead of an LLM response (network/proxy issue)."


def register_ui_agent(ui_agent: UiAgent, app: FastAPI) -> None:
    # Conversation history is kept in memory per AG-UI threadId; a restart forgets it.
    ag_ui_agent = _UiAgUiAgent(
        adk_agent=ui_agent,
        app_name="a2ui_agent_app",
        user_id="a2ui-client",
        session_timeout_seconds=3600,
        use_in_memory_services=True,
        # No token streaming: LiteLLM's stream mode turns some HTTP failures (e.g. a proxy's HTML
        # block page) into an empty reply; the non-streaming call raises a real error instead.
        run_config_factory=lambda _input: RunConfig(streaming_mode=StreamingMode.NONE),
    )
    add_adk_fastapi_endpoint(app, ag_ui_agent, path="/")
