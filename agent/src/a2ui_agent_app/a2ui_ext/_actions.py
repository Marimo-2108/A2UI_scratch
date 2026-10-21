import json
from typing import Any


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
