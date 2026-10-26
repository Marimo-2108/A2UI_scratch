"""Transport-independent A2UI helpers: catalogs, user actions and surface repair."""

import json
from typing import Any

from a2ui.core.basic_catalog import BasicCatalog
from a2ui.processor import A2uiGenerator, CatalogConfig
from a2ui.schema import VERSION_0_9

# The SDK and the web library speak "v0.9". (The spec doc already describes v0.9.1, but the
# libraries validate messages against version "v0.9".)
PROTOCOL_VERSION = "v0.9"

# Catalog IDs this agent can generate UI for. Matched EXACTLY against what the client sends.
BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def make_generator() -> A2uiGenerator:
    """Use the basic catalog, or a custom schema supplied by the client."""
    return A2uiGenerator([CatalogConfig(BasicCatalog(VERSION_0_9))], accepts_inline_catalogs=True)


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
