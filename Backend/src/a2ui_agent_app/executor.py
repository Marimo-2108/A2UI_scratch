"""Map validated AG-UI runs to the transport-independent A2UI/ADK runner."""

import logging
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import uuid4

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from pydantic import BaseModel, ConfigDict, Field

from .a2ui import action_to_text
from .runner import UiRunner
from .settings import Settings

log = logging.getLogger(__name__)

# Application-level convention, not a built-in AG-UI event name.
A2UI_EVENT_NAME = "a2ui"


class UiAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    surfaceId: str = Field(min_length=1)
    sourceComponentId: str = Field(min_length=1)
    timestamp: str
    context: dict[str, Any] = Field(default_factory=dict)


class ActionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v0.9"]
    action: UiAction


class UiRunProps(BaseModel):
    """Our application contract inside AG-UI's forwardedProps."""

    model_config = ConfigDict(extra="forbid")

    a2uiClientCapabilities: dict[str, Any] = Field(min_length=1)
    a2uiAction: ActionEnvelope | None = None


def text_events(text: str) -> tuple[BaseEvent, ...]:
    message_id = str(uuid4())
    return (
        TextMessageStartEvent(message_id=message_id, role="assistant"),
        TextMessageContentEvent(message_id=message_id, delta=text),
        TextMessageEndEvent(message_id=message_id),
    )


class UiExecutor:
    def __init__(self, settings: Settings) -> None:
        self.runner = UiRunner(settings)
        log.info("llm: %s", self.runner.llm_name)

    async def execute(
        self, run: RunAgentInput, props: UiRunProps, user_text: str
    ) -> AsyncIterator[BaseEvent]:
        yield RunStartedEvent(
            thread_id=run.thread_id, run_id=run.run_id, protocol_version="1.0.0"
        )
        try:
            for event in text_events("Thinking..."):
                yield event
            user_input = (
                action_to_text(props.a2uiAction.action.model_dump())
                if props.a2uiAction is not None
                else user_text
            )
            async for item in self.runner.respond(
                run.thread_id, user_input, props.a2uiClientCapabilities
            ):
                if isinstance(item, str):
                    for event in text_events(item):
                        yield event
                else:
                    yield CustomEvent(name=A2UI_EVENT_NAME, value=item)
        except Exception as exc:  # Report failures after HTTP streaming has begun.
            log.exception("AG-UI run failed: thread=%s run=%s", run.thread_id, run.run_id)
            yield RunErrorEvent(message=f"Agent error: {type(exc).__name__}: {exc}", code="AGENT_ERROR")
            return
        yield RunFinishedEvent(thread_id=run.thread_id, run_id=run.run_id)
