# Glossary (plain language)

Think of a restaurant. The **agent** is the kitchen, the **client** is the dining room, and
A2UI is the order slip format they pass back and forth.

## The big picture
| Term | Plain meaning |
|---|---|
| **A2UI** | A *format* for an AI to describe a screen as JSON ("a card with a title and a button") instead of writing code. The app draws it. |
| **Agent** | The backend program (Python here) that decides what UI to show. Later it asks an LLM. |
| **Client / renderer** | The frontend (React here). It turns A2UI JSON into real buttons and text. |
| **A2A** | A *delivery protocol* for talking to agents: how a request is sent and how answers stream back. A2UI is the content; A2A is the envelope. |
| **Transport** | Whatever carries the messages (A2A here; could be WebSocket etc.). A2UI doesn't care. |

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

## Inside A2A
| Term | Plain meaning |
|---|---|
| **Agent card** | A public JSON "business card" at `/.well-known/agent-card.json`: who the agent is and what it supports. |
| **Extension** | An optional add-on to A2A. "A2UI" is one. |
| **Capabilities** | The client telling the agent "these are the catalogs I can draw". |
| **Negotiation** | Client and agent agreeing on what they both support (extension + catalog) before the agent sends UI. |
| **Task** | A2A's unit of work. It has a state: `working`, `input-required` (done, waiting for you), `completed`, `failed`. |
| **contextId** | Conversation ID. Same id = same conversation. |
| **status-update** | A progress event in a task. Our agent sends each A2UI message inside one. |
| **Part / DataPart** | A piece of a message. `TextPart` = text. `DataPart` = JSON. A2UI messages travel as DataParts. |
| **SSE (Server-Sent Events)** | A normal HTTP response that stays open so the server can push many events. Why the card appears step by step. |
| **JSON-RPC** | A simple request style: `{ "method": "...", "params": {...} }`. A2A uses it. |
| **CORS / preflight** | Browser safety rule: a page may only call another address if that address allows it. The agent has to say yes. |
| **MIME type** | A label on data saying what it is. Ours: `application/a2ui+json` = "this is A2UI". |

## Added in Milestone 4 (the AI part)
| Term | Plain meaning |
|---|---|
| **LLM** | The AI model (Gemini). It writes text; we make it write A2UI JSON. |
| **System prompt** | Standing instructions given to the model before the user's message. Ours = role + rules + the A2UI schema. |
| **prompt_snippet** | The SDK's ready-made chunk of system prompt that teaches the model the A2UI format. |
| **Validation** | Checking the model's JSON against the catalog schema before the user ever sees it. |
| **Retry loop** | If validation fails, send the error back to the model and ask it to fix its answer. |
| **Memory / history** | The earlier turns of the conversation, sent along each time, so "what is on screen" is known. Kept per `contextId`. |
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
| **Inline catalog** | The client sends its whole catalog (as JSON Schema) inside its capabilities, so the agent learns custom components without keeping its own copy. |
| **catalogId** | A name for a catalog. Both sides must agree on it exactly. Our custom one is `.../stats-v1.json`. |
| **Enum** | A property that may only be one of a fixed list (trend: up, down, flat). Validation rejects anything else. |
| **Lossy export** | Converting between schema formats can drop detail (very nested function calls become "anything"). |
| **Content filter / gateway** | A network security layer that can block sites. Cloudflare Gateway blocked api.openai.com here, returning an HTML "blocked" page instead of the API's answer. |
