"""The A2A AgentExecutor: where an incoming A2A message becomes a stream of A2UI messages."""

from __future__ import annotations

import asyncio
import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, TaskState
from a2a.utils import new_agent_parts_message, new_agent_text_message, new_task

from a2ui_ext import a2ui_part, a2ui_requested, choose_catalog
from script import greeting_update, welcome_card

log = logging.getLogger("executor")

STEP_DELAY_S = 0.7  # artificial delay so streaming is visible in the browser


class ScriptedExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        assert msg is not None

        # --- 1. look at what the client sent -------------------------------------------
        user_text = context.get_user_input()
        action = next(
            (
                p.root.data
                for p in msg.parts
                if isinstance(p.root, DataPart) and "action" in p.root.data
            ),
            None,
        )
        log.info("incoming: text=%r action=%s contextId=%s", user_text, action, msg.context_id)

        # --- 2. A2A task bookkeeping ----------------------------------------------------
        task = context.current_task
        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # --- 3. negotiation ---------------------------------------------------------------
        if not a2ui_requested(context):
            await updater.update_status(
                TaskState.completed,
                new_agent_text_message(
                    "I only speak A2UI. Send header X-A2A-Extensions with the A2UI extension URI.",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )
            return

        catalog_id = choose_catalog(context)
        if catalog_id is None:
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    "No shared A2UI catalog. Send metadata.a2uiClientCapabilities.",
                    task.context_id,
                    task.id,
                ),
                final=True,
            )
            return

        # --- 4. an ACTION: the user clicked something in the UI ---------------------------
        # It arrives as a DataPart: { "version": ..., "action": { name, surfaceId, context, ... } }
        if action is not None:
            act = action["action"]
            log.info("ACTION %s from %s, context=%s", act.get("name"), act.get("sourceComponentId"), act.get("context"))
            if act.get("name") == "submit_name":
                name = str((act.get("context") or {}).get("name", ""))
                for a2ui_msg in greeting_update(act["surfaceId"], name):
                    await updater.update_status(
                        TaskState.working,
                        new_agent_parts_message([a2ui_part(a2ui_msg)], task.context_id, task.id),
                    )
                reply = "Updated the greeting."
            else:
                reply = f"Unknown action {act.get('name')!r}."
            await updater.update_status(
                TaskState.input_required,
                new_agent_text_message(reply, task.context_id, task.id),
            )
            return
        # --- 5. stream the UI: one status-update per A2UI message ----------------------------
        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Building your card...", task.context_id, task.id),
        )
        for a2ui_msg in welcome_card(catalog_id):
            await asyncio.sleep(STEP_DELAY_S)
            await updater.update_status(
                TaskState.working,
                new_agent_parts_message([a2ui_part(a2ui_msg)], task.context_id, task.id),
            )

        # input_required = "I'm done for now, waiting for the user's next action"
        await updater.update_status(
            TaskState.input_required,
            new_agent_text_message("Done. Interact with the card.", task.context_id, task.id),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")