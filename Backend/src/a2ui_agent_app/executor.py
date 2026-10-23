"""The A2A AgentExecutor: where an incoming A2A message becomes a stream of A2UI messages.

Flow:
  1. look at what arrived (text or an A2UI action)
  2. A2A task bookkeeping
  3. negotiation: extension header (catalog negotiation happens inside UiRunner)
  4. ask the brain (the ADK UI agent) and stream each result back as a status-update
  5. finish with input-required ("done, waiting for the user's next action")
"""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, TaskState
from a2a.utils import new_agent_parts_message, new_agent_text_message, new_task

from .a2ui import a2ui_requested, action_to_text, client_capabilities
from .runner import UiRunner
from .settings import Settings

log = logging.getLogger("executor")


class UiExecutor(AgentExecutor):
    def __init__(self, settings: Settings) -> None:
        self.runner = UiRunner(settings)
        log.info("llm: %s", self.runner.llm_name)

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
        # Catalog negotiation is left to the SDK inside UiRunner (it may even accept the client's
        # INLINE catalog); it fails the task if nothing matches.

        # --- 4. the brain ------------------------------------------------------------------
        try:
            await say("Thinking...")
            user_input = action_to_text(action) if action is not None else user_text
            async for part in self.runner.respond(
                task.context_id, user_input, client_capabilities(context) or {}
            ):
                await updater.update_status(
                    TaskState.working, new_agent_parts_message([part], task.context_id, task.id)
                )
        except Exception as e:  # noqa: BLE001  - report any failure to the client, don't hang
            log.exception("brain failed")
            await say(f"Agent error: {type(e).__name__}: {e}", TaskState.failed, final=True)
            return

        # --- 5. done; wait for the user's next action -----------------------------------------
        await say("Done.", TaskState.input_required)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
