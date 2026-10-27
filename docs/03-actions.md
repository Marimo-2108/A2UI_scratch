# The round trip: user action -> agent -> UI update

The original scripted action handler and A2A transport have been removed. Actions now travel
through AG-UI, while the A2UI action payload and renderer behavior remain the same.

## The loop

```text
User edits a field and clicks an A2UI Button
  -> MessageProcessor resolves action bindings and invokes our action handler
  -> POST / with RunAgentInput:
       same threadId, new runId
       user message "USER_ACTION {...}" (the action as JSON)
  -> ADK continues the existing conversation; the model calls send_a2ui_json_to_client
  -> TOOL_CALL_RESULT {validated_a2ui_json: [<A2UI messages>]}
  -> the same MessageProcessor updates the existing screen
  -> RUN_FINISHED (or RUN_ERROR on failure)
```

## Key ideas

- The button's `action.event.name` and `context` define the action. Context values may
  reference data paths; the renderer resolves those bindings before calling our handler.
- The action JSON keeps `name`, `surfaceId`, `sourceComponentId`, `timestamp` and `context`;
  the model reads it as text.
- Actions and text prompts use the same AG-UI endpoint. There is no DataPart or MIME marker.
- A follow-up keeps the existing thread, ADK history and rendered surfaces. A new conversation
  resets the client and screen and uses a new thread.
- The browser blocks a second action while a run is in progress.
- `updateDataModel` can update a single bound data path without resending components.

## Implementation

- [App.tsx](../Frontend/src/App.tsx): action handler and renderer integration.
- [AG-UI client](../Frontend/src/agui/client.ts): request, history and event handling.
- [Backend README](../Backend/README.md): how the agent handles a request.
