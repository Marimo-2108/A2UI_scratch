"""The LLM decides the UI (the agent itself lives in a2ui_agent_app.agents; this drives it).

The loop for one request:

    static instruction  = our role/rules                     (agents/ui/_static_instructions.py)
    dynamic instruction = SDK's prompt_snippet (A2UI format + full JSON schema), negotiated per
                          request and served by CatalogContextProvider
    conversation        = ADK session keyed by the A2A contextId (follow-ups and clicks have context)
         |
         v
    ADK Runner -> UiAgent -> text containing  <a2ui-json> [ ...A2UI messages... ] </a2ui-json>
         |
         v
    processor.parse_response(text)   # heals small JSON slips, VALIDATES against the catalog
         |  ok                       \\ A2uiValidationError
         v                            v
    yield parts to the client      tell the LLM what was wrong, ask again (max N retries)

Why validate? v0.9 is "prompt-first": the model is *asked* to follow the schema but nothing forces
it. Validation is the safety net between a probabilistic model and your UI.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from a2a.types import Part, TextPart
from a2ui.core.basic_catalog import BasicCatalog
from a2ui.core.exceptions import A2uiValidationError
from a2ui.inference_formats import to_message_dicts
from a2ui.parser import A2uiPart
from a2ui.parser import TextPart as ParsedText
from a2ui.processor import A2uiGenerator, CatalogConfig
from a2ui.schema import VERSION_0_9
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from a2ui_agent_app.a2ui_ext import a2ui_part, repair_surfaces
from a2ui_agent_app.agents import AgentConfig, UiAgent

from ._catalog_context import CatalogContextProvider

log = logging.getLogger("ui_brain")

# ADK expects the app name to match the agent's folder (agents/ui) and warns otherwise.
_APP_NAME = "ui"
_USER_ID = "a2ui-client"


def make_generator() -> A2uiGenerator:
    """The catalogs THIS AGENT can produce UI for.

    accepts_inline_catalogs=True: a client may send its OWN catalog (JSON Schema) inside
    a2uiClientCapabilities. We then prompt and validate against that, so custom components
    defined in the browser work without a copy on the server. The basic catalog stays as
    the fallback for clients that only send supportedCatalogIds.
    """
    return A2uiGenerator([CatalogConfig(BasicCatalog(VERSION_0_9))], accepts_inline_catalogs=True)


class UiBrain:
    def __init__(self, config: AgentConfig, max_retries: int) -> None:
        self.max_retries = max_retries
        self.generator = make_generator()
        self.catalogs = CatalogContextProvider()
        self.agent = UiAgent(context_provider=self.catalogs, config=config)
        # contextId -> conversation so far (in RAM; restart = forgotten).
        self.runner = Runner(
            app_name=_APP_NAME,
            agent=self.agent,
            session_service=InMemorySessionService(),
            auto_create_session=True,
        )
        # contextId -> surfaceIds we have DELIVERED to that client (not merely generated).
        self.surfaces: dict[str, set[str]] = {}

    @property
    def llm_name(self) -> str:
        model = self.agent.model
        return model if isinstance(model, str) else model.model

    async def _ask(self, context_id: str, text: str) -> str:
        """Run the agent for one user message; return the model's final (non-thought) text."""
        message = genai_types.Content(role="user", parts=[genai_types.Part(text=text)])
        chunks: list[str] = []
        async for event in self.runner.run_async(
            user_id=_USER_ID, session_id=context_id, new_message=message
        ):
            if event.error_code:
                raise RuntimeError(f"LLM error {event.error_code}: {event.error_message}")
            if event.is_final_response() and event.content and event.content.parts:
                chunks += [p.text for p in event.content.parts if p.text and not p.thought]
        return "".join(chunks)

    async def respond(
        self, context_id: str, user_input: str, client_caps: dict[str, Any]
    ) -> AsyncIterator[Part]:
        """Yield A2A Parts: TextParts for progress/chat and DataParts for A2UI messages."""
        # NEGOTIATION, SDK style: given what the client can render, which catalogs are active?
        # Raises A2uiValidationError if there is no overlap.
        processor = self.generator.create_processor(client_caps)
        self.catalogs.set_processor(context_id, processor)
        log.info("catalog prompt: %d chars, llm=%s", len(processor.prompt_snippet), self.llm_name)

        # The ADK session keeps every turn, including rejected attempts and our corrections,
        # so the model can see what went wrong on the next try.
        text_in = user_input
        for attempt in range(self.max_retries + 1):
            text = await self._ask(context_id, text_in)
            log.info("attempt %d: model returned %d chars", attempt + 1, len(text))
            try:
                parts = processor.parse_response(text)  # heal + validate against the catalog
            except A2uiValidationError as e:
                log.warning("attempt %d failed validation: %s", attempt + 1, e)
                if attempt == self.max_retries:
                    raise
                yield Part(root=TextPart(text=f"(model output invalid, retrying {attempt + 1}/{self.max_retries}...)"))
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
                yield Part(root=TextPart(text=t))
            for msg in wire:
                yield a2ui_part(msg)
            return
