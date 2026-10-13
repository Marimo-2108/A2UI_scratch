"""Tiny CLI client to poke the agent without a browser:  uv run python try_agent.py "make a signup form"

Prints a compact view of every streamed event. Handy for debugging the LLM output.
"""

import json
import sys
import time
import uuid

import httpx

import os

URL = os.getenv("AGENT_URL", "http://localhost:10010/")  # override to test another instance
EXT = "https://a2ui.org/a2a-extension/a2ui/v0.9"
CATALOG = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


BASIC_CAPS = {"v0.9": {"supportedCatalogIds": [CATALOG]}}


def load_caps():
    """Capabilities exported from the web app (our custom catalog inline). `npm run export:caps`."""
    return json.load(open("fixtures/inline_caps.json", encoding="utf-8"))


CAPS = BASIC_CAPS  # replaced by main when --caps is passed


def stream(parts, context_id=None):
    msg = {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": "user",
        "parts": parts,
        "metadata": {"a2uiClientCapabilities": CAPS},
    }
    if context_id:
        msg["contextId"] = context_id
    body = {"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {"message": msg}}
    t0 = time.time()
    out = []
    with httpx.stream("POST", URL, json=body, headers={"X-A2A-Extensions": EXT}, timeout=120) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            res = json.loads(line[5:])["result"]
            ctx = res.get("contextId", context_id)
            status = res.get("status", {})
            for p in (status.get("message") or {}).get("parts", []):
                if p["kind"] == "text":
                    print(f"  +{time.time()-t0:5.1f}s [{status.get('state')}] text: {p['text'][:140]}")
                else:
                    keys = [k for k in p["data"] if k != "version"]
                    print(f"  +{time.time()-t0:5.1f}s [{status.get('state')}] A2UI {keys}")
                    out.append(p["data"])
            context_id = ctx
    return context_id, out


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
    ctx, msgs = stream([{"kind": "text", "text": args[0]}])
    print("contextId:", ctx)
    if len(args) > 1:
        json.dump(msgs, open(args[1], "w"), indent=2)
        print("saved", args[1])
