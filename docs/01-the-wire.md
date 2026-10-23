# Milestone 1: the wire (no agent, no AI)

## What we built
`Frontend/` fed hand-written A2UI JSON into the real `MessageProcessor`
(`@a2ui/web_core/v0_9`) and rendered with `@a2ui/react/v0_9`.

> **Removed:** the "M1 · Static wire" tab (`WireDemo.tsx`, `wire/messages.ts`) was deleted in the
> cleanup that dropped the scripted agent. The concepts below still apply to the live app.

## Mental model
- Agent -> client is a stream of JSON envelopes. Four types:
  `createSurface`, `updateComponents`, `updateDataModel`, `deleteSurface`.
- UI **structure** (flat component list, linked by id, entry point id `root`) is separate
  from UI **data** (JSON-Pointer addressed data model). Components bind with `{ "path": "/x" }`.
- `updateComponents` upserts by id. `updateDataModel` replaces the value at a path.
- A **catalog** is the allow-list of components the client will render. The agent can only
  name components that exist in it. This is the security model: data, not code.
- User input flows back as **actions** (`action.event.name` + `context`). Context values may
  themselves be bound to the data model.

## Gotchas we hit
- `catalogId` is matched by EXACT string. This lib registers its basic catalog under the
  `.../specification/v0_9/catalogs/basic/catalog.json` URL even though the spec doc says v0_9_1.
  Read it from `basicCatalog.id` instead of hardcoding.
- Library accepts `version: "v0.9"` and `"v0.9.1"`.
- `@a2ui/react` needs zod 3 as a peer (Vite's default install gives zod 4).
- `basicCatalog` is runtime-fine but needs `MessageProcessor<ReactCatalogComponent>` to typecheck.
- The published `@a2ui/react` README is out of sync with the code. Trust the source.

## Open questions for Milestone 2
- How does A2UI ride on A2A (which Part type, which metadata keys)?
- How does the client advertise its supported catalogs to the agent?
