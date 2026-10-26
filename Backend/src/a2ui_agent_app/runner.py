"""Negotiate a catalog -> run the ADK agent -> validate/retry -> yield text or A2UI.

ADK sessions hold conversation history, keyed by AG-UI threadId. Both history and the record of
surfaces already sent to the client live in memory; restarting the server forgets them.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Any

from a2ui.core.exceptions import A2uiValidationError
from a2ui.inference_formats import to_message_dicts
from a2ui.parser import A2uiPart
from a2ui.parser import TextPart as ParsedText
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from .a2ui import make_generator, repair_surfaces
from .agents import AgentConfig, create_agent

log = logging.getLogger(__name__)

_APP_NAME = "a2ui_agent_app"
_USER_ID = "a2ui-client"
_CATALOG_PROMPT = "temp:a2ui_catalog_prompt"


async def catalog_instruction(context: ReadonlyContext) -> str:
    """A callable avoids ADK interpreting JSON schema braces as {state} placeholders."""
    prompt = context.state.get(_CATALOG_PROMPT)
    if not isinstance(prompt, str):
        raise RuntimeError("No A2UI catalog negotiated for this request.")
    return prompt


class UiRunner:
    def __init__(self, config: AgentConfig) -> None:
        self.max_retries = config.llm_max_retries
        self.generator = make_generator()
        self.agent = create_agent(config, catalog_instruction)
        # threadId -> conversation so far (in RAM; restart = forgotten).
        self.runner = Runner(
            app_name=_APP_NAME,
            agent=self.agent,
            session_service=InMemorySessionService(),
            auto_create_session=True,
        )
        # threadId -> surfaceIds we have DELIVERED to that client (not merely generated).
        self.surfaces: dict[str, set[str]] = {}

    @property
    def llm_name(self) -> str:
        model = self.agent.model
        return model if isinstance(model, str) else model.model

    async def _ask(self, context_id: str, text: str, catalog_prompt: str) -> str:
        """Run the agent for one user message; return the model's final (non-thought) text."""
        message = genai_types.Content(role="user", parts=[genai_types.Part(text=text)])
        chunks: list[str] = []
        async with aclosing(
            self.runner.run_async(
                user_id=_USER_ID,
                session_id=context_id,
                new_message=message,
                # temp: state belongs to this invocation, not to the remembered conversation.
                state_delta={_CATALOG_PROMPT: catalog_prompt},
            )
        ) as events:
            # Close in this task on errors/cancellation so ADK detaches its tracing context here.
            async for event in events:
                if event.error_code:
                    raise RuntimeError(f"LLM error {event.error_code}: {event.error_message}")
                if event.is_final_response() and event.content and event.content.parts:
                    chunks += [p.text for p in event.content.parts if p.text and not p.thought]
        return "".join(chunks)

    async def respond(
        self, context_id: str, user_input: str, client_caps: dict[str, Any]
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Yield text for progress/chat and dictionaries for validated A2UI messages."""
        # NEGOTIATION, SDK style: given what the client can render, which catalogs are active?
        # Raises A2uiValidationError if there is no overlap.
        processor = self.generator.create_processor(client_caps)
        log.info("catalog prompt: %d chars, llm=%s", len(processor.prompt_snippet), self.llm_name)

        # The ADK session keeps every turn, including rejected attempts and our corrections,
        # so the model can see what went wrong on the next try.
        text_in = user_input
        for attempt in range(self.max_retries + 1):
            text = await self._ask(context_id, text_in, str(processor.prompt_snippet))
            log.info("attempt %d: model returned %d chars", attempt + 1, len(text))
            try:
                parts = processor.parse_response(text)  # heal + validate against the catalog
            except A2uiValidationError as e:
                log.warning("attempt %d failed validation: %s", attempt + 1, e)
                if attempt == self.max_retries:
                    raise
                yield f"(model output invalid, retrying {attempt + 1}/{self.max_retries}...)"
                text_in = (
                    "Your previous A2UI JSON failed validation:\n"
                    f"{e}\n\n"
                    "IMPORTANT: that attempt was rejected and NOTHING from it reached the user's "
                    "screen. Send the COMPLETE A2UI JSON block again from scratch, including "
                    "`createSurface` for any new surface. Do not mention this error or the fix "
                    "in your text reply; just write the normal one-sentence reply."
                )
                continue

            # Flatten to wire messages, then reconcile with what the client really has on screen.
            known = self.surfaces.setdefault(context_id, set())
            catalog_id = processor.active_catalogs[0].catalog_id
            texts: list[str] = []
            wire: list[dict[str, Any]] = []
            for part in parts:
                if isinstance(part, A2uiPart):
                    wire += to_message_dicts(part.a2ui)
                elif isinstance(part, ParsedText) and part.text.strip():
                    texts.append(part.text.strip())
            wire, notes = repair_surfaces(wire, known, catalog_id)
            for n in notes:
                log.warning("repaired model output: %s", n)

            for t in texts:
                yield t
            for msg in wire:
                yield msg
            return
