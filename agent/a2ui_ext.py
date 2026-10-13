"""A2UI-over-A2A plumbing (negotiation is hand-written so you can read it; the DataPart builder
comes from the official SDK).

  1. constants: protocol version + extension URI
  2. the AgentExtension we advertise on the agent card
  3. negotiation: did the client ask for A2UI, and which catalog should we use?
  4. building an A2A DataPart that carries ONE A2UI message
"""

from __future__ import annotations

import logging
from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.types import AgentExtension, Part
from a2ui.a2a import create_a2ui_part

log = logging.getLogger("a2ui_ext")

# The SDK and the web library speak "v0.9". (The spec doc already describes v0.9.1, but the
# libraries validate messages against version "v0.9".) The extension URI embeds this version.
PROTOCOL_VERSION = "v0.9"
EXTENSION_URI = f"https://a2ui.org/a2a-extension/a2ui/{PROTOCOL_VERSION}"

# Catalog IDs this agent can generate UI for. Matched EXACTLY against what the client sends.
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
    context.add_activated_extension(EXTENSION_URI)
    return True


def client_capabilities(context: RequestContext) -> dict[str, Any] | None:
    """The a2uiClientCapabilities note the client put in message.metadata (or None).

    Shape: { "v0.9": { "supportedCatalogIds": [...] } }   (keyed by protocol version)
    """
    metadata: dict[str, Any] = (context.message.metadata if context.message else None) or {}
    caps = metadata.get("a2uiClientCapabilities")
    log.info("a2uiClientCapabilities: %s", caps)
    return caps if isinstance(caps, dict) else None


def choose_catalog(context: RequestContext) -> str | None:
    """Pick a catalog both sides support, or None if there is no overlap."""
    caps = client_capabilities(context)
    if caps is None:
        return None
    client_ids = (caps.get(PROTOCOL_VERSION) or {}).get("supportedCatalogIds") or []
    for catalog_id in SUPPORTED_CATALOG_IDS:
        if catalog_id in client_ids:
            return catalog_id
    return None


def a2ui_part(message: dict[str, Any]) -> Part:
    """Wrap ONE A2UI envelope message in an A2A DataPart (metadata.mimeType marks it as A2UI).

    Delegates to the official helper so we match what other A2UI clients expect. For protocol
    "v0.9" it uses the older MIME type "application/json+a2ui"; the web client accepts both.
    """
    return create_a2ui_part(message, version=PROTOCOL_VERSION)
