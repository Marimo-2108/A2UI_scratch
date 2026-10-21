from typing import Any


def repair_surfaces(
    messages: list[dict[str, Any]], known: set[str], catalog_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Make a batch of A2UI messages consistent with what the client ACTUALLY has on screen.

    `known` = surfaceIds already delivered to this client (updated in place). Rules, in order:
      - updateComponents / updateDataModel for an unknown surface -> insert the missing createSurface
        (the model assumed an earlier attempt, which never reached the client, had created it)
      - createSurface for a surface the client already has        -> drop it (spec: that's an error)
      - deleteSurface                                             -> forget the surface
    Returns (fixed messages, human-readable notes about what was repaired).
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
        else:  # updateComponents / updateDataModel / anything addressed to a surface
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
