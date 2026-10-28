# A2UI React client

One screen: ask the agent for a UI, inspect the messages, and interact with the rendered result.
The Python agent must be running; see the [root README](../README.md) for setup.

```bash
npm run dev       # http://localhost:5173
npm run build     # TypeScript check + production build
npm run lint
npm test          # mock HTTP/SSE streams, A2UI processing and UI markup; no LLM required
```

## Where to read

- [src/main.tsx](./src/main.tsx) mounts the React app.
- [src/App.tsx](./src/App.tsx) owns the page layout, wiring the controls to the hook.
- [src/components/AppHeader.tsx](./src/components/AppHeader.tsx),
  [LivePreview.tsx](./src/components/LivePreview.tsx) and
  [AgentNotes.tsx](./src/components/AgentNotes.tsx) render the screen's sections.
- [src/components/Icons.tsx](./src/components/Icons.tsx) contains the SVG artwork.
- [src/components/Button.tsx](./src/components/Button.tsx) and
  [PanelHeading.tsx](./src/components/PanelHeading.tsx) share the button and heading markup.
- [src/components/PromptComposer.tsx](./src/components/PromptComposer.tsx) owns the prompt,
  example prompts and new-conversation/follow-up controls.
- [src/hooks/useUiAgent.ts](./src/hooks/useUiAgent.ts) owns the conversation, streamed text,
  errors, trace entries and rendered surface list.
- [src/components/WireInspector.tsx](./src/components/WireInspector.tsx) displays the trace and
  owns row selection and the raw JSON preview.
- [src/agui/client.ts](./src/agui/client.ts) uses the official AG-UI `HttpAgent` SDK
  for HTTP/SSE, event validation and conversation message history. It also extracts typed
  A2UI messages using the A2UI SDK's schema.
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

## Reading the agent hook

In [useUiAgent.ts](./src/hooks/useUiAgent.ts), follow these functions:

- `send` starts a new conversation; `followUp` keeps the existing one.
- `run` sends the request and manages busy state and errors.
- `handleEvent` records incoming events and routes text and A2UI messages.
- `appendText` joins streamed pieces of the same assistant message.
- `processUiMessages` updates the rendered surfaces, keeping existing surfaces on duplicate creates.

Button actions use the same `run` path. The `running` ref prevents overlapping requests before
React updates the buttons. The AG-UI client also checks for failed or incomplete streams and
preserves callback errors that the SDK would otherwise swallow.

## Screen layout

- **Header and intro**: branding, protocol version and local run status.
- **Prompt composer**: **New conversation**, **Follow-up**, and example prompts.
- **Wire inspector**: requests and streamed events; select one to inspect or copy its JSON.
  Copy feedback resets when selecting another event or clearing the trace.
- **Live preview and agent notes**: rendered A2UI surfaces and the agent's streamed text.

[src/App.css](./src/App.css) is plain CSS with no UI framework. It follows the system light/dark
setting, stacks the panels on narrow screens, and themes the A2UI components through their
`--a2ui-*` CSS variables.

The backend uses a fixed catalog. After changing the catalog here, run `npm run export:caps`
(Node 22.6+) to regenerate `Backend/fixtures/stats-v1.catalog.json`, then restart the agent.
