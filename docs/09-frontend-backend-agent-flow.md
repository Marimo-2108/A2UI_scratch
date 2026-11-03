# Frontend-to-backend agent flow

This guide explains how the React app communicates with the Python agent, how A2UI messages get rendered, and how UI actions return to the agent.

For backend startup, configuration, and ADK internals, see [Backend, end to end](./08-backend-end-to-end-flow.md).

## At a glance

```text
PromptComposer
  -> useUiAgent.send(text)
  -> UiAgentClient / AG-UI HttpAgent
  -> POST RunAgentInput to the backend
  -> ag_ui_adk adapter -> ADK UiAgent -> LLM
  -> LLM calls send_a2ui_json_to_client
  -> A2UI tool validates the proposed messages
  <- AG-UI SSE events, including TOOL_CALL_RESULT with validated A2UI JSON
  -> useUiAgent parses and processes the messages
  -> React renders the resulting surfaces
  -> button click becomes a USER_ACTION message in the same conversation
```

The transport is AG-UI over HTTP: the browser sends a run request, and the server responds with a stream of Server-Sent Events (SSE). The A2UI document is not a separate HTTP response; it is carried in the result of the model's A2UI tool call.

## Main files

| File | Responsibility |
|---|---|
| [`useUiAgent.ts`](../Frontend/src/hooks/useUiAgent.ts) | React state and orchestration: prompts, follow-ups, action callbacks, event handling, and surfaces. |
| [`client.ts`](../Frontend/src/agui/client.ts) | Wraps `HttpAgent`, adds user messages, subscribes to AG-UI events, and extracts validated A2UI messages from tool results. |
| [`myCatalog.ts`](../Frontend/src/catalog/myCatalog.ts) | Frontend component catalog used by the A2UI message processor. |
| [`_ui_agent.py`](../Backend/src/a2ui_agent_app/api/_ui_agent.py) | Adapts the AG-UI endpoint to Google ADK and streams events back. |
| [`_ui_agent.py`](../Backend/src/a2ui_agent_app/agents/_ui_agent.py) | Defines the ADK `LlmAgent` and installs the A2UI toolset. |
| [`system-prompt.txt`](../Backend/src/a2ui_agent_app/agents/system-prompt.txt) | Tells the model how to produce A2UI and respond to UI actions. |

## Starting a conversation

1. The user submits text through the prompt UI. `useUiAgent.send(text)` clears the previous conversation's chat, errors, and surfaces.
2. The hook creates a new `UiAgentClient`. Its `HttpAgent` gets a new `threadId`, identifying this conversation to the backend.
3. The hook creates a `MessageProcessor` with `myCatalog`. The processor handles A2UI messages and reports UI actions through its callback.
4. `UiAgentClient.run()` adds the text as a user message to the SDK's conversation history and calls `HttpAgent.runAgent()` with a new `runId`.
5. The AG-UI adapter at the backend's `/` endpoint passes the request to ADK. ADK runs `UiAgent`, which sends the prompt and catalog schema to the configured LLM.
6. The system prompt instructs the model to answer with a short sentence and call `send_a2ui_json_to_client` with A2UI messages. The toolset validates those messages against the backend catalog. If validation fails, the tool returns an error so the model can retry.
7. The backend returns AG-UI events over SSE. The frontend client forwards each event to the hook.
8. The hook records events for the wire inspector, appends text deltas to chat, and extracts A2UI messages from `TOOL_CALL_RESULT` events. Valid messages are passed to `MessageProcessor`; the resulting surfaces are saved in React state and rendered.

The default frontend URL is `http://localhost:10010/`; it can be overridden with `VITE_AGENT_URL`. This matches the backend's default port. The backend CORS configuration must allow the frontend's origin.

## How the client handles events

`UiAgentClient` delegates HTTP, SSE decoding, event validation, and AG-UI conversation history to `HttpAgent`.

- `onRunInitialized` reports the request URL, headers, and body to the hook for tracing.
- Each AG-UI event is passed to the hook.
- `a2uiMessagesOf(event)` only examines `TOOL_CALL_RESULT`. It parses the result's JSON `content`, looks for `validated_a2ui_json`, and validates each message against the A2UI v0.9 schema.
- A tool result containing an `error` has no `validated_a2ui_json`, so it produces no UI messages. The model can then correct the JSON and call the tool again.
- The client reports an error if a subscriber callback failed, the run emitted `RUN_ERROR`, or the stream ended without a terminal run event.

The backend catalog validation and frontend A2UI schema/version validation serve different purposes: the backend checks the proposed UI against the configured catalog, while the frontend verifies that received messages have the expected protocol shape and version.

## Follow-up text

`useUiAgent.followUp(text)` reuses the current `UiAgentClient` and `MessageProcessor`. That keeps the same `threadId`, AG-UI conversation, ADK session, and rendered surfaces. The client adds the new user text to its message history and starts another run.

The backend stores ADK sessions in memory, keyed by thread, with a one-hour timeout. A backend restart loses those sessions. The system prompt therefore instructs the model to update an existing surface rather than recreate it on follow-ups.

## UI action round trip

1. A rendered component's `action.event` is handled by the `MessageProcessor`.
2. The processor callback records the action in the trace and starts a run with text like `USER_ACTION {"name":...,"surfaceId":...,"context":...}`.
3. The action goes through the same AG-UI client and backend thread as the original prompt.
4. The system prompt tells the model that every action must receive a tool call, normally updating the existing surface.
5. The returned tool result follows the same parsing and rendering path as the initial response.

Action context can include values collected by the UI, including values supplied through A2UI data bindings.

## Run and surface guards

- Both the hook and client prevent overlapping runs. A second action while a run is active is reported as an error or ignored, depending on which guard receives it.
- When a `createSurface` arrives for a surface already present in the current processor, the hook skips it and writes a trace entry instead of replacing the surface.
- Starting a new conversation creates a new thread and processor and clears the old surfaces. Follow-ups and actions reuse the existing ones.
