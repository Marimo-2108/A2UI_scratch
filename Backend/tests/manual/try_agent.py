"""Tiny CLI client to poke the agent without a browser:
    uv run python tests/manual/try_agent.py "make a signup form"

Prints a compact view of every streamed event. Handy for debugging the LLM output.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

URL = os.getenv("AGENT_URL", "http://localhost:10010/")  # override to test another instance
CATALOG = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"  # Backend/fixtures
BASIC_CAPS = {"v0.9": {"supportedCatalogIds": [CATALOG]}}


def load_caps():
    """Capabilities exported from the web app (our custom catalog inline). `npm run export:caps`."""
    return json.load(open(FIXTURES / "inline_caps.json", encoding="utf-8"))


CAPS = BASIC_CAPS  # replaced by main when --caps is passed


def stream(text, thread_id=None):
    thread_id = thread_id or str(uuid.uuid4())
    body = {
        "threadId": thread_id,
        "runId": str(uuid.uuid4()),
        "protocolVersion": "1.0.0",
        "messages": [{"id": str(uuid.uuid4()), "role": "user", "content": text}],
        "forwardedProps": {"a2uiClientCapabilities": CAPS},
    }
    t0 = time.time()
    out = []
    finished = False
    with httpx.stream("POST", URL, json=body, headers={"Accept": "text/event-stream"}, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            kind = event["type"]
            if kind == "RUN_ERROR":
                raise RuntimeError(event["message"])
            if kind == "TEXT_MESSAGE_CONTENT":
                print(f"  +{time.time()-t0:5.1f}s text: {event['delta'][:140]}")
            elif kind == "CUSTOM" and event["name"] == "a2ui":
                message = event["value"]
                keys = [k for k in message if k != "version"]
                print(f"  +{time.time()-t0:5.1f}s A2UI {keys}")
                out.append(message)
            else:
                print(f"  +{time.time()-t0:5.1f}s {kind}")
            if kind == "RUN_FINISHED":
                finished = True
    if not finished:
        raise RuntimeError("AG-UI stream ended before RUN_FINISHED.")
    return thread_id, out


if __name__ == "__main__":
    # usage: try_agent.py [--caps] "prompt" [save_to.json]
    args = sys.argv[1:]
    if args and args[0] == "--caps":
        CAPS = load_caps()
        print("using exported custom catalog:", CAPS["v0.9"]["supportedCatalogIds"])
        args = args[1:]
    elif args and args[0] == "--ids-only":
        # advertise only a catalog NAME (no schema), e.g. to see what happens when the agent doesn't know it
        CAPS = {"v0.9": {"supportedCatalogIds": [args[1]]}}
        print("advertising catalog id only:", args[1])
        args = args[2:]
    ctx, msgs = stream(args[0])
    print("threadId:", ctx)
    if len(args) > 1:
        json.dump(msgs, open(args[1], "w"), indent=2)
        print("saved", args[1])
