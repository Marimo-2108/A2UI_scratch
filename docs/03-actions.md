# The round trip: user action -> agent -> UI update

The original scripted action handler and A2A transport have been removed. Actions now travel
through AG-UI, while the A2UI action payload and renderer behavior remain the same.

## The loop

```text
User edits a field and clicks an A2UI Button
  -> MessageProcessor resolves action bindings and invokes our action handler
  -> POST / with RunAgentInput:
       same threadId, new runId
       user message describing the action
       forwardedProps.a2uiAction = {version: "v0.9", action: {...}}
       forwardedProps.a2uiClientCapabilities = renderer capabilities
  -> executor validates/extracts the action and converts it to USER_ACTION {...}
  -> ADK continues the existing conversation and generates validated A2UI
  -> CUSTOM {name: "a2ui", value: <A2UI message>} events
  -> the same MessageProcessor updates the existing screen
  -> RUN_FINISHED (or RUN_ERROR on failure)
```

## Key ideas

- The button's `action.event.name` and `context` define the action. Context values may
  reference data paths; the renderer resolves those bindings before calling our handler.
- The action envelope preserves `name`, `surfaceId`, `sourceComponentId`, `timestamp` and
  `context`. The backend turns the action's name, surface, source and context into model text.
- Actions and text prompts use the same AG-UI endpoint. There is no DataPart or MIME marker.
- A follow-up keeps the existing thread, ADK history and rendered surfaces. A new conversation
  resets the client and screen and uses a new thread.
- Overlapping runs are rejected rather than racing to update the same session.
- `updateDataModel` can update a single bound data path without resending components.

## Implementation

- [App.tsx](../Frontend/src/App.tsx): action handler and renderer integration.
- [AG-UI client](../Frontend/src/agui/client.ts): request, history and event handling.
- [executor.py](../Backend/src/a2ui_agent_app/executor.py): structured action validation and execution.
- [Migration record](./07-agui-migration.md): complete wire examples and verification.
