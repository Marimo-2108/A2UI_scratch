# A2UI React client

One screen: ask the agent for a UI, inspect the messages, and interact with the rendered result.
The Python agent must be running; see the [root README](../README.md) for setup.

```bash
npm run dev       # http://localhost:5173
npm run build     # TypeScript check + production build
npm run lint
npm test          # real AG-UI SDK against mock HTTP/SSE streams; no LLM required
```

## Where to read

- [src/main.tsx](./src/main.tsx) mounts the React app.
- [src/App.tsx](./src/App.tsx) owns the prompt, conversation, wire inspector and rendered surfaces.
- [src/agui/client.ts](./src/agui/client.ts) uses the official AG-UI `HttpAgent` SDK
  for HTTP/SSE, event validation and conversation message history.
- [src/catalog/myCatalog.ts](./src/catalog/myCatalog.ts) registers basic components plus
  [StatCard](./src/catalog/StatCard.tsx), our custom example.

## What happens

1. **New conversation** clears the screen and creates a new AG-UI client with a fresh `threadId`.
2. Each run gets a new `runId`. The client sends the user/assistant message history.
3. Each response event appears in the wire inspector. The agent's `send_a2ui_json_to_client`
   tool result (`TOOL_CALL_RESULT` with `validated_a2ui_json`) feeds the `MessageProcessor`;
   `A2uiSurface` renders the resulting surfaces.
4. **Follow-up** reuses the screen and `threadId`. Button clicks are sent as a user message
   `USER_ACTION {...}` through the same path.
5. Errors are displayed rather than hidden. Click a wire row to inspect its raw JSON.
   `RUN_ERROR`, HTTP failures, malformed events, renderer callback failures and truncated
   streams all reach the caller. Concurrent actions are rejected explicitly.

The backend uses a fixed catalog. After changing the catalog here, run `npm run export:caps`
(Node 22.6+) to regenerate `Backend/fixtures/stats-v1.catalog.json`, then restart the agent.
