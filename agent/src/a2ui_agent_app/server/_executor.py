"""The A2A AgentExecutor: where an incoming A2A message becomes a stream of A2UI messages.

Flow (same for both brains):
  1. look at what arrived (text or an A2UI action)
  2. A2A task bookkeeping
  3. negotiation: extension header + client capabilities
  4. ask the brain (scripted or the ADK UI agent) and stream each result back as a status-update
  5. finish with input-required ("done, waiting for the user's next action")
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Task, TaskState
from a2a.utils import new_agent_parts_message, new_agent_text_message, new_task

from a2ui_agent_app.a2ui_ext import (
    a2ui_part,
    a2ui_requested,
    action_to_text,
    choose_catalog,
    client_capabilities,
)

from ._scripted import greeting_update, welcome_card
from ._settings import Settings
from ._ui_brain import UiBrain

log = logging.getLogger("executor")

STEP_DELAY_S = 0.7  # scripted mode only: artificial delay so streaming is visible

Say = Callable[..., Awaitable[None]]


class UiExecutor(AgentExecutor):
    def __init__(self, settings: Settings) -> None:
        self.brain: UiBrain | None = None
        if settings.llm_enabled:  # scripted mode needs no key, so the agent is only built here
            self.brain = UiBrain(settings.to_agent_config(), settings.gemini_max_retries)
            log.info("llm: %s", self.brain.llm_name)
        log.info("agent mode: %s", settings.agent_mode)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        assert msg is not None

        # --- 1. what arrived? ------------------------------------------------------------
        user_text = context.get_user_input()
        action = next(
            (
                p.root.data["action"]
                for p in msg.parts
                if isinstance(p.root, DataPart) and "action" in p.root.data
            ),
            None,
        )
        log.info("incoming: text=%r action=%s contextId=%s", user_text, action, msg.context_id)

        # --- 2. A2A task bookkeeping ----------------------------------------------------------
        task = context.current_task
        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        async def say(text: str, state: TaskState = TaskState.working, final: bool = False) -> None:
            await updater.update_status(
                state, new_agent_text_message(text, task.context_id, task.id), final=final
            )

        # --- 3. negotiation ---------------------------------------------------------------
        if not a2ui_requested(context):
            await say(
                "I only speak A2UI. Send header X-A2A-Extensions with the A2UI extension URI.",
                TaskState.completed,
                final=True,
            )
            return
        # Catalog negotiation. Scripted mode only knows the basic catalog, so our hand-written
        # check is enough. In LLM mode the SDK negotiates (it may even accept the client's
        # INLINE catalog), so we leave that to UiBrain: it fails the task if nothing matches.
        catalog_id = None
        if self.brain is None:
            catalog_id = choose_catalog(context)
            if catalog_id is None:
                await say(
                    "No shared A2UI catalog. Send metadata.a2uiClientCapabilities.",
                    TaskState.failed,
                    final=True,
                )
                return

        # --- 4. the brain ------------------------------------------------------------------
        try:
            if self.brain is None:
                assert catalog_id is not None
                await self._scripted(updater, task, action, catalog_id)
            else:
                await self._llm(self.brain, updater, task, context, user_text, action, say)
        except Exception as e:  # noqa: BLE001  - report any failure to the client, don't hang
            log.exception("brain failed")
            await say(f"Agent error: {type(e).__name__}: {e}", TaskState.failed, final=True)
            return

        # --- 5. done; wait for the user's next action -----------------------------------------
        await say("Done.", TaskState.input_required)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")

    # ---- brain A: Milestone 2/3, fixed UI ---------------------------------------------------
    async def _scripted(
        self,
        updater: TaskUpdater,
        task: Task,
        action: dict[str, Any] | None,
        catalog_id: str,
    ) -> None:
        if action is not None:
            name = str((action.get("context") or {}).get("name", ""))
            msgs = greeting_update(action["surfaceId"], name) if action.get("name") == "submit_name" else []
        else:
            msgs = welcome_card(catalog_id)
        for m in msgs:
            await asyncio.sleep(STEP_DELAY_S)
            await updater.update_status(
                TaskState.working,
                new_agent_parts_message([a2ui_part(m)], task.context_id, task.id),
            )

    # ---- brain B: Milestone 4, the ADK UI agent (Gemini or OpenAI) ----------------------------
    async def _llm(
        self,
        brain: UiBrain,
        updater: TaskUpdater,
        task: Task,
        context: RequestContext,
        user_text: str,
        action: dict[str, Any] | None,
        say: Say,
    ) -> None:
        await say("Thinking...")
        user_input = action_to_text(action) if action is not None else user_text
        async for part in brain.respond(
            task.context_id, user_input, client_capabilities(context) or {}
        ):
            await updater.update_status(
                TaskState.working, new_agent_parts_message([part], task.context_id, task.id)
            )
