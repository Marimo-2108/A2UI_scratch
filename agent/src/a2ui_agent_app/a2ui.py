"""A2UI helpers: catalogs, A2A envelopes, user actions and surface repair."""

import json
import logging
from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.types import AgentExtension, Part
from a2ui.a2a import create_a2ui_part
from a2ui.core.basic_catalog import BasicCatalog
from a2ui.processor import A2uiGenerator, CatalogConfig
from a2ui.schema import VERSION_0_9

log = logging.getLogger(__name__)

# The SDK and the web library speak "v0.9". (The spec doc already describes v0.9.1, but the
# libraries validate messages against version "v0.9".) The extension URI embeds this version.
PROTOCOL_VERSION = "v0.9"
EXTENSION_URI = f"https://a2ui.org/a2a-extension/a2ui/{PROTOCOL_VERSION}"

# Catalog IDs this agent can generate UI for. Matched EXACTLY against what the client sends.
BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
SUPPORTED_CATALOG_IDS = [BASIC_CATALOG_ID]


def make_generator() -> A2uiGenerator:
    """Use the basic catalog, or a custom schema supplied by the client."""
    return A2uiGenerator([CatalogConfig(BasicCatalog(VERSION_0_9))], accepts_inline_catalogs=True)


def agent_extension() -> AgentExtension:
    """What we put in AgentCard.capabilities.extensions."""
    return AgentExtension(
        uri=EXTENSION_URI,
        description="Provides agent driven UI using the A2UI JSON format.",
        required=False,
        params={
            "supportedCatalogIds": SUPPORTED_CATALOG_IDS,
            "acceptsInlineCatalogs": True,
        },
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


def a2ui_part(message: dict[str, Any]) -> Part:
    """Wrap ONE A2UI envelope message in an A2A DataPart (metadata.mimeType marks it as A2UI).

    Delegates to the official helper so we match what other A2UI clients expect. For protocol
    "v0.9" it uses the older MIME type "application/json+a2ui"; the web client accepts both.
    """
    return create_a2ui_part(message, version=PROTOCOL_VERSION)


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


def repair_surfaces(
    messages: list[dict[str, Any]], known: set[str], catalog_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reconcile model output with the client's screen; update known surface IDs in place.

    Insert missing creates, drop duplicate creates, and forget deleted surfaces.
    Return the repaired messages and notes to log, rather than hiding the model's mistakes.
    """
    out: list[dict[str, Any]] = []
    notes: list[str] = []
    for m in messages:
        kind = next((k for k in m if k != "version"), "")
        body = m.get(kind)
        sid = body.get("surfaceId") if isinstance(body, dict) else None
        if sid is None:
            out.append(m)
        elif kind == "createSurface":
            if sid in known:
                notes.append(f"dropped duplicate createSurface for {sid!r}")
                continue
            known.add(sid)
            out.append(m)
        elif kind == "deleteSurface":
            known.discard(sid)
            out.append(m)
        else:
            if sid not in known:
                notes.append(f"inserted missing createSurface for {sid!r}")
                out.append(
                    {
                        "version": m.get("version", "v0.9"),
                        "createSurface": {"surfaceId": sid, "catalogId": catalog_id},
                    }
                )
                known.add(sid)
            out.append(m)
    return out, notes
