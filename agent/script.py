"""The scripted "agent brain" for Milestone 2: fixed A2UI messages, no LLM.

These are the same messages as web/src/wire/messages.ts (steps 1-3). In Milestone 4 an LLM
will produce this JSON instead, and everything around it (A2A, negotiation, rendering) stays.
"""

from __future__ import annotations

from typing import Any

from a2ui_ext import PROTOCOL_VERSION

SURFACE_ID = "welcome_card"


def welcome_card(catalog_id: str) -> list[dict[str, Any]]:
    v = PROTOCOL_VERSION
    return [
        {"version": v, "createSurface": {"surfaceId": SURFACE_ID, "catalogId": catalog_id}},
        {
            "version": v,
            "updateComponents": {
                "surfaceId": SURFACE_ID,
                "components": [
                    {"id": "root", "component": "Card", "child": "content"},
                    {
                        "id": "content",
                        "component": "Column",
                        "children": ["title", "greeting", "name_input", "submit_btn"],
                    },
                    {"id": "title", "component": "Text", "variant": "h2", "text": {"path": "/title"}},
                    {"id": "greeting", "component": "Text", "text": {"path": "/greeting"}},
                    {
                        "id": "name_input",
                        "component": "TextField",
                        "label": "Your name",
                        "value": {"path": "/name"},
                    },
                    {"id": "submit_label", "component": "Text", "text": "Send my name to the agent"},
                    {
                        "id": "submit_btn",
                        "component": "Button",
                        "variant": "primary",
                        "child": "submit_label",
                        "action": {
                            "event": {"name": "submit_name", "context": {"name": {"path": "/name"}}}
                        },
                    },
                ],
            },
        },
        {
            "version": v,
            "updateDataModel": {
                "surfaceId": SURFACE_ID,
                "path": "/",
                "value": {
                    "title": "Hello from the agent",
                    "greeting": "This card was streamed over A2A.",
                    "name": "",
                },
            },
        },
    ]


def greeting_update(surface_id: str, name: str) -> list[dict[str, Any]]:
    """Reply to the `submit_name` action: change ONE value in the data model.

    No components are re-sent. The Text component bound to /greeting redraws on its own.
    """
    greeting = f"Nice to meet you, {name}!" if name.strip() else "You didn't type a name."
    return [
        {
            "version": PROTOCOL_VERSION,
            "updateDataModel": {"surfaceId": surface_id, "path": "/greeting", "value": greeting},
        }
    ]
