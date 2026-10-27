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

## Function guide

| Function | Responsibility |
| --- | --- |
| `App` | Composes the prompt controls, inspector, text and A2UI surfaces. |
| `PromptComposer` | Edits the prompt, fills examples, and sends new or follow-up messages; blank prompts are disabled. |
| `useUiAgent` | Keeps React state and mutable SDK instances together; exposes the screen's commands and data. |
| `describe` | Builds a trace label from an event and its already-parsed A2UI messages. |
| `push` | Adds a timestamped trace entry with a unique sequence number. |
| `reportError` | Converts an exception or error string into a visible error entry. |
| `makeProcessor` | Creates the A2UI processor with our catalog and routes rendered button actions through `run`. |
| `run` | Rejects concurrent runs, sends a request, handles text/UI events, preserves existing surfaces on duplicate creates, and reports failures. |
| `send` | Starts a new thread and processor, clears text/errors/surfaces, then runs the prompt. |
| `followUp` | Runs the prompt using the existing thread, history and surfaces. |
| `clearTrace` | Clears trace entries without resetting the conversation. |
| `WireInspector` / `clear` | Renders the trace and JSON preview; clears both entries and selection. |
| `UiAgentClient.constructor` | Creates an HTTP agent with a fresh thread ID. |
| `UiAgentClient.run` | Appends the user message, starts an SDK run, forwards request/event callbacks, and checks completion/errors. |
| `notify` (inside the client run) | Retains callback failures that the SDK would otherwise swallow, so the caller receives them. |
| `a2uiMessagesOf` | Extracts and validates the A2UI messages in a tool result; ignores non-A2UI events and rejected tool results. |
| `StatCard` | Displays resolved metric properties with an optional trend indicator. |

## Cleanup and optimization

- Each tool result is parsed once per incoming event, rather than separately for tracing and rendering.
- The surface list is refreshed only for A2UI payloads, not for every text or lifecycle event.
  Existing surfaces handle their internal reactive updates through the A2UI renderer.
- A processor is created only when starting a conversation, rather than also creating an unused
  initial processor during rendering.
- The selected row's JSON is memoized, so incoming events do not repeatedly serialize an unchanged
  request or payload. Selecting a trace row no longer re-renders the whole app.
- The SDK's A2UI schema replaces the handwritten envelope check and removes unsafe renderer casts.
  The client still accepts only `v0.9`; malformed operation fields now fail at the extraction boundary.
- Unused starter images/icons and the redundant `sent` CSS class have been removed.
  `A2UI_TOOL_NAME` was already removed from the working tree; result extraction does not need it.

The synchronous `running` ref is intentional: it prevents two actions from starting before React
has committed the `busy` state. The client's completion and callback-error checks are also
intentional safeguards, not obsolete code.

Trace and conversation history remain unlimited, as before. For much longer sessions, consider
trace virtualization or an explicit retention limit; that should be a separate UX decision because
discarding entries changes what the inspector can show. Splitting files improves maintainability,
not bundle size by itself; avoid blanket memoization or additional state libraries without profiling.

## Interface styling

[src/App.css](./src/App.css) defines the workspace's colors, spacing and responsive layout without
external fonts or a UI framework. It follows the system light/dark preference and respects reduced
motion. On narrow screens the preview comes before the inspector; the inspector keeps every event
in a scrollable list with keyboard-accessible row buttons and a separate JSON preview. Each row has
a color-coded category (request, run, text, tool, UI, state, error); long labels are truncated until
selected, and the payload panel wraps long values and can copy the selected JSON.

The prompt composer includes examples that fill (but do not automatically send) the input. Enter
starts a new conversation; Follow-up reuses the current conversation. Empty or whitespace-only
prompts cannot be sent. Status badges describe local run state, not backend connection health.

The preview customizes the basic catalog through its supported `--a2ui-*` CSS tokens rather than
overriding generated component markup or agent-supplied themes.

The backend uses a fixed catalog. After changing the catalog here, run `npm run export:caps`
(Node 22.6+) to regenerate `Backend/fixtures/stats-v1.catalog.json`, then restart the agent.
