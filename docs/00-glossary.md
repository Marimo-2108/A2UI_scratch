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
