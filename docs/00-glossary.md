# Glossary (plain language)

Think of a restaurant. The **agent** is the kitchen, the **client** is the dining room, and
A2UI is the order slip format they pass back and forth.

## The big picture
| Term | Plain meaning |
|---|---|
| **A2UI** | A *format* for an AI to describe a screen as JSON ("a card with a title and a button") instead of writing code. The app draws it. |
| **Agent** | The backend program (Python here) that decides what UI to show. Later it asks an LLM. |
| **Client / renderer** | The frontend (React here). It turns A2UI JSON into real buttons and text. |
| **AG-UI** | The agent-to-frontend interaction protocol used here. It defines run inputs and streamed events; A2UI describes the UI inside those events. |
| **A2A** | Agent-to-agent protocol used by earlier milestones, no longer the browser/server protocol here. |
| **Transport** | HTTP + Server-Sent Events here, carrying AG-UI events. A2UI itself is transport-independent. |

## Inside A2UI
| Term | Plain meaning |
|---|---|
| **Message** | One JSON instruction. Only four kinds: `createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`. |
| **Surface** | One independent screen area (like one card). It has an ID. |
| **Component** | One UI piece: `Text`, `Button`, `Card`, `Column`... |
| **Flat list + `id` references** | Components are listed side by side, not nested. A `Column` says `children: ["title","button"]`, pointing at them by id. The one with id `root` is the top. |
| **Data model** | The surface's data (name, title, ...), kept separate from layout. |
| **Path / binding** | `{"path": "/name"}` means "show whatever is stored at `/name` in the data model". Change the data and the text updates by itself. |
| **Catalog** | The menu of components the client is willing to draw. The agent can only order from it. This is the safety idea: the AI sends data, never code. |
| **Action** | What happens when the user clicks: it is sent to the agent as a named event. |

## Inside AG-UI
| Term | Plain meaning |
|---|---|
| **RunAgentInput** | The JSON body sent to `POST /` to start a run: thread ID, run ID, messages and optional application properties. |
| **threadId** | Conversation ID. Reuse it for follow-ups and button actions; also the ADK session ID. |
| **runId** | A unique ID for one request/response run within a thread. |
| **RUN_STARTED / RUN_FINISHED** | Events marking the beginning and successful end of a run. Finishing does not end the conversation. |
| **RUN_ERROR** | Terminal failure event; the UI displays its message. No success event follows it. |
| **TEXT_MESSAGE_START / CONTENT / END** | Events opening a text message, delivering its text delta, and closing it. |
| **TOOL_CALL_START / ARGS / END / RESULT** | Events for a tool the agent calls. Our agent calls `send_a2ui_json_to_client`; its RESULT carries the validated A2UI messages the browser renders. |
| **Catalog (backend)** | The backend loads one fixed catalog file (`Backend/fixtures/stats-v1.catalog.json`), generated from the frontend catalog with `npm run export:caps`. |
| **SSE (Server-Sent Events)** | A normal HTTP response that stays open so the server can push many events. Why the card appears step by step. |
| **CORS / preflight** | Browser safety rule: a page may only call another address if that address allows it. The agent has to say yes. |
| **Content type** | The response is `text/event-stream`. A2UI payloads no longer need a separate DataPart MIME marker. |

## Added in Milestone 4 (the AI part)
| Term | Plain meaning |
|---|---|
| **LLM** | The AI model (an Azure deployment, called through LiteLLM). It writes text; we make it write A2UI JSON. |
| **System prompt** | Standing instructions given to the model before the user's message. Ours = role + rules + the A2UI schema. |
| **prompt_snippet** | The SDK's ready-made chunk of system prompt that teaches the model the A2UI format. |
| **Validation** | Checking the model's JSON against the catalog schema before the user ever sees it. |
| **Retry loop** | If validation fails, the tool returns the error to the model, which fixes its answer and calls the tool again. |
| **Memory / history** | The earlier turns kept in ADK's in-memory session, keyed by `threadId`. The AG-UI client also maintains user/assistant message history. |
| **Thinking level** | How long the model reasons before answering. Lower = faster. LOW is ~5-12s here, default ~43s, same result. |
| **Token** | A chunk of text the model reads or writes (~4 characters). Cost and speed scale with tokens. |
| **503 / 429** | Server busy / too many requests. Temporary; we retry with backoff. |
| **truststore / certificate store** | Makes Python trust the same HTTPS certificates as Windows. Needed on networks that re-sign traffic. |

## Added in Milestone 5 (custom components)
| Term | Plain meaning |
|---|---|
| **Custom component** | A UI piece you invent (StatCard) and add to your catalog. The agent can then request it by name. |
| **Component API vs implementation** | API = the name and the allowed properties (a schema, just data). Implementation = how it looks (React code). Only the API is shared with the agent. |
| **Zod** | A TypeScript library for describing the shape of data. We use it to describe StatCard's properties. |
| **JSON Schema** | The language-neutral way to describe data shapes. The agent side reads this. Zod can be exported to it. |
| **Inline catalog** | Earlier milestones: the client sent its whole catalog inside its capabilities. Now the backend uses a fixed exported catalog instead. |
| **catalogId** | A name for a catalog. Both sides must agree on it exactly. Our custom one is `.../stats-v1.json`. |
| **Enum** | A property that may only be one of a fixed list (trend: up, down, flat). Validation rejects anything else. |
| **Lossy export** | Converting between schema formats can drop detail (very nested function calls become "anything"). |
| **Content filter / gateway** | A network security layer that can block sites. Cloudflare Gateway blocked api.openai.com here, returning an HTML "blocked" page instead of the API's answer. |
