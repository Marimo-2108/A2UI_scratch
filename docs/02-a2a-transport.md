# Milestone 2: A2UI over A2A (scripted agent)

## Run it
```
# terminal 1
cd agent && uv run python server.py        # http://localhost:10010
# terminal 2
cd web && npm run dev                      # http://localhost:5173  (tab "M2 · Live agent")
```
Raw protocol check without a browser: see "Poke it with curl" below.

## The conversation, step by step
1. Client fetches `/.well-known/agent-card.json`. It lists the A2UI extension and
   `params.supportedCatalogIds`. (Our client doesn't fetch it yet; we just opt in.)
2. Client POSTs JSON-RPC `message/stream` with
   - HTTP header `X-A2A-Extensions: https://a2ui.org/a2a-extension/a2ui/v0.9.1` (opt in)
   - `message.metadata.a2uiClientCapabilities = { "v0.9.1": { supportedCatalogIds: [...] } }`
3. Agent replies with an SSE stream. Each `data:` line is a JSON-RPC response:
   `task (submitted)` -> `status-update (working)` x N -> `status-update (input-required)`.
4. Each A2UI message is its own `DataPart`, `metadata.mimeType = "application/a2ui+json"`,
   inside `status.message.parts` of a `status-update`.
5. `input-required` = "agent is done, waiting for the user". Not an error, it ends the stream.

## Things the docs don't tell you (found by reading code / testing)
| Topic | Spec doc says | What actually works |
|---|---|---|
| DataPart payload | `data` is an ARRAY of messages | `a2a-sdk` types `data` as a dict; official SDK sends ONE message per DataPart |
| MIME type | `application/a2ui+json` | official SDK uses the old `application/json+a2ui` for versions 0.8/0.9, new one for 0.9.1+. Our client accepts both. |
| Catalog ID | `.../v0_9_1/catalogs/basic/catalog.json` | the web library registers `.../v0_9/...`; match is exact string |
| a2a-sdk version | n/a | `a2a-sdk` 1.x is a protobuf rewrite and incompatible with 0.3 JSON-RPC clients; pin `>=0.3.0,<0.4.0` like the official project |
| Extension echo | agent should activate | `context.add_activated_extension` is called, but no `X-A2A-Extensions` response header showed up on the streaming response in a2a-sdk 0.3.26 |
| Official React shell | | does A2A in a Vite Node middleware, not the browser; sends extension `.../v0.9` and puts `mimeType` on the part itself. We talk A2A from the browser directly to see the wire. |

## Files
- `agent/a2ui_ext.py`   extension URI, MIME, agent-card extension, negotiation, DataPart builder
- `agent/script.py`     the fixed A2UI messages (an LLM replaces this in Milestone 4)
- `agent/executor.py`   A2A `AgentExecutor`: negotiate -> stream one status-update per A2UI message
- `agent/server.py`     AgentCard + Starlette app + CORS (`expose_headers` for X-A2A-Extensions)
- `web/src/a2a/client.ts`   hand-written `message/stream` client + SSE parser
- `web/src/demos/LiveDemo.tsx`  wire inspector + the same `MessageProcessor` as Milestone 1

## Poke it with curl
```
curl -N -X POST http://localhost:10010/ -H "Content-Type: application/json" \
  -H "X-A2A-Extensions: https://a2ui.org/a2a-extension/a2ui/v0.9.1" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/stream","params":{"message":{"kind":"message","messageId":"m1","role":"user","parts":[{"kind":"text","text":"hi"}],"metadata":{"a2uiClientCapabilities":{"v0.9.1":{"supportedCatalogIds":["https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"]}}}}}}'
```
Try removing the header, or the metadata, and see the agent refuse. That is negotiation.
