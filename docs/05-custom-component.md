# Milestone 5: a custom component (StatCard) and our own catalog

## The idea in one picture
```
 BROWSER (owns the component)                          AGENT (never sees React code)
 ┌─────────────────────────────────────┐
 │ statCardApi.ts   name + Zod schema  │ ─ exported ─▶  a2uiClientCapabilities.v0.9.inlineCatalogs
 │ StatCard.tsx     how it looks       │   as JSON      (25 KB of JSON Schema, incl. StatCard + hints)
 │ myCatalog.ts     basic + StatCard   │                         │
 └─────────────────────────────────────┘                         ▼
            ▲                                   prompt_snippet now describes StatCard
            │ renders                           parse_response now VALIDATES StatCard props
            │                                                     │
            └──────── {"component":"StatCard","label":..} ◀───────┘   (data, never code)
```
Security model made concrete: the model can only request components the client approved,
with property values the schema allows. It cannot ship code.

## What we built
- `web/src/catalog/statCardApi.ts`  API half: `name` + Zod schema (`.describe()` text goes to the model)
- `web/src/catalog/StatCard.tsx`    implementation half (`createComponentImplementation`)
- `web/src/catalog/myCatalog.ts`    `Catalog(id, '0.9', [...basic, StatCard], ...)` under OUR catalog id
- `web/src/App.tsx`                processor uses `myCatalog`; capabilities come from
                                    `processor.getRendererCapabilities({versions, includeInlineCatalogs:true})`
- `agent`: `A2uiGenerator(..., accepts_inline_catalogs=True)`; agent card says `acceptsInlineCatalogs: true`
- `web/scripts/export-capabilities.mjs` + `npm run export:caps` -> `agent/fixtures/inline_caps.json`
- `agent/tests/manual/try_agent.py --caps "prompt"` sends that catalog from the command line

## Results (same prompt: "a small KPI dashboard: revenue, active users, churn")
| Client sends | catalogId chosen by the model | Result |
|---|---|---|
| our catalog inline | `.../stats-v1.json` | 3 x `StatCard` with valid label/value/change/trend |
| basic catalog only | basic | Card x3 + Column x4 + Text x7 |
Validation probe (Python side): `trend: "sideways"` is REJECTED (`not one of ['up','down','flat']`);
unknown component `Banana` is REJECTED; a correct StatCard is accepted.

## Gotchas
- The Zod -> JSON Schema export is LOSSY for recursive types: the library logs
  "Recursive reference detected ... Defaulting to any" (function-call arguments). Our StatCard
  schema is exact; deeply nested function-call args are validated loosely on the agent side.
- Inline catalogs are sent on EVERY request (~25 KB of metadata) and add ~1.3k tokens to the prompt.
- Executor: my hand-written `choose_catalog` only knew the basic id, so it ran ONLY in scripted
  mode (both since removed). The SDK negotiates and fails the task if nothing matches.
- A catalog id is just a string both sides agree on; changing it is how the agent can tell
  "client has StatCard" from "client has only basic".
- Network: `api.openai.com` started redirecting (HTTP 303) to `blocked.teams.cloudflare.com`
  (Cloudflare Gateway) mid-session. Gemini and Anthropic stayed reachable. Policy decision for the
  network admin, so we switched `LLM_PROVIDER=gemini` rather than work around it.
  Symptom in our code: `'str' object has no attribute 'choices'` (the SDK returned an HTML page).

## Try it
```
cd web && npm run export:caps
cd ../agent && uv run python tests/manual/try_agent.py --caps "a KPI dashboard for an online shop"
```
In the browser: "a KPI dashboard for an online shop" -> New conversation.
Then Follow-up: "add a fourth card for conversion rate", "make churn trend up".
Ideas to extend: add a `size` enum, an `icon` property, or an `action` so a card is clickable.

## Bug found by use: "Surface not found for message: kpi-dashboard-1"
**Symptom (browser):** error from the library; agent text said "`StatCard.trend` must be a literal ..., so I replaced the bound `trend` fields".

**Cause:** the model bound `trend` to a data path ({"path": ...}) but our schema only allows a literal
enum. Validation rejected attempts 1 and 2 (good). On attempt 3 the model returned a SHORTER answer
WITHOUT `createSurface`: the failed attempts were in its conversation, so it assumed the surface already
existed. But rejected attempts never reach the client, so the browser had no such surface.
Reproduced with `tests/manual/repro_kpi.py`: 2 of 4 runs broken, every broken run had 2 validation retries.

**Fixes (three layers):**
1. `repair_surfaces()` (now `a2ui.py`): the agent remembers which surfaces it has actually DELIVERED
   per conversation; an update for an unknown surface gets the missing `createSurface` inserted
   (with the negotiated catalog id); a duplicate `createSurface` is dropped; `deleteSurface` forgets.
   Unit-tested in `tests/test_repair.py` (`uv run python tests/test_repair.py`).
2. Retry message now says: that attempt was rejected and NOTHING reached the screen, resend the COMPLETE
   block incl. `createSurface`, and don't mention the error in the text reply.
3. `StatCard.trend` description says LITERAL ONLY, not a data binding. Fewer retries in the first place.

**After:** 0 of 6 runs broken (1 of 6 needed a retry, vs 2 of 4 before). Small sample; the live repair
path itself wasn't triggered in that run, the unit tests cover it.

**Lessons:**
- Validate-and-retry creates a hidden state problem: what the model *believes* happened (its
  conversation) can differ from what the client *has*. The agent must track delivered state itself.
- Schema descriptions are prompt text. Tell the model what a property can NOT be, not only what it is.
- `tests/manual/repro_kpi.py [N]` runs the prompt N times and checks that every updated surface was created first.
