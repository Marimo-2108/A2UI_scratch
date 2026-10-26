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
2. Each run gets a new `runId`. The client sends user/assistant message history and renderer
   capabilities (including the catalog's JSON schema) in `forwardedProps.a2uiClientCapabilities`.
3. Each response event appears in the wire inspector. Its A2UI messages feed the
   `MessageProcessor`; `A2uiSurface` renders the resulting surfaces.
4. **Follow-up** reuses the screen and `threadId`. Button clicks send a structured A2UI envelope
   in `forwardedProps.a2uiAction` through the same path.
5. Errors are displayed rather than hidden. Click a wire row to inspect its raw JSON.
   `RUN_ERROR`, HTTP failures, malformed events, renderer callback failures and truncated
   streams all reach the caller. Concurrent actions are rejected explicitly.

A2UI messages arrive in `CUSTOM` events named `a2ui`. That name and the forwarded-property
keys are this application's contract, not built-in AG-UI fields.
See [the migration record](../docs/07-agui-migration.md) for examples and limitations.

After changing the catalog, run `npm run export:caps` to refresh the backend's manual-test fixtures.
The live app sends capabilities directly from its catalog; it does not read those fixtures.
