"""A2UI-over-A2A plumbing, written by hand (mirrors what a2ui.a2a does in the official SDK).

Everything the A2UI extension needs, in four small pieces:
  1. the extension URI + MIME type constants
  2. the AgentExtension we advertise on the agent card
  3. negotiation: did the client ask for A2UI, and which catalog should we use?
  4. building an A2A DataPart that carries ONE A2UI message
"""

from __future__ import annotations

import logging
from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.types import AgentExtension, DataPart, Part

log = logging.getLogger("a2ui_ext")

PROTOCOL_VERSION = "v0.9.1"
EXTENSION_URI = f"https://a2ui.org/a2a-extension/a2ui/{PROTOCOL_VERSION}"

# Note: the official SDK uses this MIME type for 0.9.1+ and the old
# "application/json+a2ui" for 0.8 / 0.9.
A2UI_MIME_TYPE = "application/a2ui+json"

# The catalog IDs this agent can generate UI for. They are matched EXACTLY against
# what the client advertises. The web client registers the library's basic catalog
# under the v0_9 URL (see docs/01-the-wire.md).
BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
SUPPORTED_CATALOG_IDS = [BASIC_CATALOG_ID]


def agent_extension() -> AgentExtension:
    """What we put in AgentCard.capabilities.extensions."""
    return AgentExtension(
        uri=EXTENSION_URI,
        description="Provides agent driven UI using the A2UI JSON format.",
        required=False,
        params={"supportedCatalogIds": SUPPORTED_CATALOG_IDS},
    )


def a2ui_requested(context: RequestContext) -> bool:
    """True if the client opted in via the X-A2A-Extensions header.

    The a2a-sdk parses that HTTP header into `context.requested_extensions`.
    """
    requested = context.requested_extensions
    log.info("client requested extensions: %s", sorted(requested))
    if EXTENSION_URI not in requested:
        return False
    # Echo it back in the response's X-A2A-Extensions header so the client knows we honored it.
    context.add_activated_extension(EXTENSION_URI)
    return True


def choose_catalog(context: RequestContext) -> str | None:
    """Pick a catalog both sides support, using a2uiClientCapabilities in message.metadata.

    Shape (spec: a2ui_extension_specification.md):
        metadata = { "a2uiClientCapabilities": { "v0.9.1": { "supportedCatalogIds": [...] } } }
    """
    metadata: dict[str, Any] = (context.message.metadata if context.message else None) or {}
    caps = metadata.get("a2uiClientCapabilities")
    log.info("a2uiClientCapabilities: %s", caps)
    if not isinstance(caps, dict):
        return None
    client_ids = (caps.get(PROTOCOL_VERSION) or {}).get("supportedCatalogIds") or []
    for catalog_id in SUPPORTED_CATALOG_IDS:
        if catalog_id in client_ids:
            return catalog_id
    return None


def a2ui_part(message: dict[str, Any]) -> Part:
    """Wrap ONE A2UI envelope message in an A2A DataPart.

    The spec text says DataPart.data is an array, but a2a-sdk types it as a dict and the
    official SDK emits one message per DataPart. We follow what actually works.
    """
    return Part(root=DataPart(data=message, metadata={"mimeType": A2UI_MIME_TYPE}))


def is_a2ui_part(part: Part) -> bool:
    return (
        isinstance(part.root, DataPart)
        and (part.root.metadata or {}).get("mimeType") == A2UI_MIME_TYPE
    )
