# A2UI React client

One screen: ask the agent for a UI, inspect the messages, and interact with the rendered result.
The Python agent must be running; see the [root README](../README.md) for setup.

```bash
npm run dev       # http://localhost:5173
npm run build     # TypeScript check + production build
npm run lint
```

## Where to read

- [src/main.tsx](./src/main.tsx) mounts the React app.
- [src/App.tsx](./src/App.tsx) owns the prompt, conversation, wire inspector and rendered surfaces.
- [src/a2a/client.ts](./src/a2a/client.ts) sends A2A JSON-RPC requests and reads SSE events.
- [src/catalog/myCatalog.ts](./src/catalog/myCatalog.ts) registers basic components plus
  [StatCard](./src/catalog/StatCard.tsx), our custom example.

## What happens

1. **New conversation** clears the screen and starts without a `contextId`.
2. The client sends the prompt and renderer capabilities, including the catalog's JSON schema.
3. Each response event appears in the wire inspector. Its A2UI messages feed the
   `MessageProcessor`; `A2uiSurface` renders the resulting surfaces.
4. **Follow-up** reuses the screen and `contextId`. Button clicks send actions through the same path.
5. Errors are displayed rather than hidden. Click a wire row to inspect its raw JSON.

After changing the catalog, run `npm run export:caps` to refresh the backend's manual-test fixtures.
The live app sends capabilities directly from its catalog; it does not read those fixtures.
