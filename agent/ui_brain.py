"""The LLM decides the UI (vendor-neutral; see llm.py for Gemini / OpenAI).

The loop for one request:

    system prompt  = our role/rules  +  SDK's prompt_snippet (A2UI format + full JSON schema)
    conversation   = remembered per A2A contextId (so follow-ups and clicks have context)
         |
         v
    LLM -> text containing  <a2ui-json> [ ...A2UI messages... ] </a2ui-json>
         |
         v
    processor.parse_response(text)   # heals small JSON slips, VALIDATES against the catalog
         |  ok                       \\ A2uiValidationError
         v                            v
    yield parts to the client      tell the LLM what was wrong, ask again (max N retries)

Why validate? v0.9 is "prompt-first": the model is *asked* to follow the schema but nothing forces
it. Validation is the safety net between a probabilistic model and your UI.
"""

from __future__ import annotations

import json
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

from a2ui_ext import a2ui_part
from config import Settings
from llm import Msg, make_llm

log = logging.getLogger("ui_brain")

ROLE = """You are the brain of a UI-generating assistant. Instead of answering only with text,
you answer with a small user interface that is rendered for the user, plus (optionally) one short
sentence of text."""

RULES = """## How this conversation works
- Reply with ONE short sentence of text, then the A2UI JSON block. Keep UIs small and tidy.
- The user's clicks arrive as messages that start with `USER_ACTION`. They contain the action
  name, the surfaceId, and a `context` object with values the UI collected.
- A surface you already created earlier in this conversation STILL EXISTS on screen. For a
  follow-up or an action, do NOT send `createSurface` for that surfaceId again. Send
  `updateComponents` (to change layout) and/or `updateDataModel` (to change data) instead.
  To show something completely different, use a NEW surfaceId.
- Prefer binding text to the data model ({"path": "/..."}) and sending data with
  `updateDataModel`; it is cheaper than resending components.
- Every Button that should do something needs an `action.event` with a meaningful `name` and a
  `context` (context values may be {"path": "/..."} bindings so the user's input is included).
- The first component of every `components` list MUST have id `root`.
- EVERY reply MUST contain an A2UI JSON block, including the reply to a USER_ACTION. Never answer
  a click with text only: the user is looking at the screen, so update it to show the result
  (for example replace a submitted form with a confirmation, or show the next step)."""


class UiBrain:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = make_llm(settings)  # Gemini or OpenAI, chosen by LLM_PROVIDER
        # The generator holds the catalogs THIS AGENT can produce UI for.
        self.generator = A2uiGenerator([CatalogConfig(BasicCatalog(VERSION_0_9))])
        # contextId -> conversation so far (in RAM; restart = forgotten).
        self.histories: dict[str, list[Msg]] = {}

    def system_prompt(self, processor: Any) -> str:
        return "\n\n".join([ROLE, RULES, processor.prompt_snippet])

    async def respond(
        self, context_id: str, user_input: str, client_caps: dict[str, Any]
    ) -> AsyncIterator[Part]:
        """Yield A2A Parts: TextParts for progress/chat and DataParts for A2UI messages."""
        # NEGOTIATION, SDK style: given what the client can render, which catalogs are active?
        # Raises A2uiValidationError if there is no overlap.
        processor = self.generator.create_processor(client_caps)
        system = self.system_prompt(processor)
        log.info("system prompt: %d chars, llm=%s", len(system), self.llm.name)

        history = self.histories.setdefault(context_id, [])
        turn = [Msg("user", user_input)]  # this request only; committed to history on success
        retry_msgs: list[Msg] = []  # failed attempts + our corrections (retries only)

        for attempt in range(self.settings.max_retries + 1):
            text = await self.llm.complete(system, [*history, *turn, *retry_msgs])
            log.info("attempt %d: model returned %d chars", attempt + 1, len(text))
            try:
                parts = processor.parse_response(text)  # heal + validate against the catalog
            except A2uiValidationError as e:
                log.warning("attempt %d failed validation: %s", attempt + 1, e)
                if attempt == self.settings.max_retries:
                    raise
                yield Part(root=TextPart(text=f"(model output invalid, retrying {attempt + 1}/{self.settings.max_retries}...)"))
                retry_msgs += [
                    Msg("model", text),
                    Msg(
                        "user",
                        "Your previous A2UI JSON failed validation:\n"
                        f"{e}\n\nFix it and send the complete A2UI JSON block again.",
                    ),
                ]
                continue

            history += [*turn, Msg("model", text)]  # success: remember it
            for part in parts:
                if isinstance(part, ParsedText) and part.text.strip():
                    yield Part(root=TextPart(text=part.text.strip()))
                elif isinstance(part, A2uiPart):
                    for msg in to_message_dicts(part.a2ui):
                        yield a2ui_part(msg)
            return


def action_to_text(action: dict[str, Any]) -> str:
    """Turn a client action into text the model can read."""
    return "USER_ACTION " + json.dumps(
        {
            "name": action.get("name"),
            "surfaceId": action.get("surfaceId"),
            "sourceComponentId": action.get("sourceComponentId"),
            "context": action.get("context", {}),
        }
    )
