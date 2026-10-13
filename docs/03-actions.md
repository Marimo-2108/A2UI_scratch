# Milestone 3: the round trip (user action -> agent -> UI update)

## The loop in one picture
```
 user types a name, clicks Button
        |
        v   (library calls our action handler with name/surfaceId/context)
 client wraps it in a DataPart  ------ A2A message/stream ------>  agent
   { version, action: { name:"submit_name", context:{ name:"Vijaka" } } }
                                                                      |
 client feeds reply into the same MessageProcessor  <---- SSE --------+
   { updateDataModel: path:"/greeting", value:"Nice to meet you, Vijaka!" }
        |
        v
 the Text bound to /greeting redraws. No component was re-sent.
```

## Key ideas
- The **button's JSON** decides what is sent: `action.event.name` + `context`.
  `context` values can be `{ "path": "/name" }`, so the library fills in what the user typed
  before calling our handler.
- Actions go the SAME way as any message (A2A `message/stream`), same `contextId`
  (= same conversation), same MIME type. Only the payload differs.
- The agent is **stateless** here: the reply is built only from the action it received.
- Updating ONE data path is the cheapest way to change the UI. That's the payoff of
  separating structure from data.

## Files changed
- `web/src/demos/LiveDemo.tsx`  `actionPart()` + `run()`; action handler now sends to the agent
- `agent/executor.py`           step 4 reads the action DataPart
- `agent/script.py`             `greeting_update()`

## Things to try
- Click the button with an empty name: different reply.
- In the inspector, compare the outgoing action row with the incoming `updateDataModel` row.
- Add a second button in `script.py` with a different action name and see "Unknown action".
