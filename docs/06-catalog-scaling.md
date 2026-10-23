# What if the catalog grows? (measured, not guessed)

## First: what is `https://scratch.local/a2ui/catalogs/stats-v1.json`?
**Not a file. Not a URL. A name.** `scratch.local` does not exist. The spec says a catalogId "is a string
identifier, not a resolvable URI"; URLs are only a naming convention to avoid collisions.
It is used as a label that must match EXACTLY on both sides:
- the browser registers a catalog under it (`new Catalog(MY_CATALOG_ID, ...)`)
- the agent writes it into `createSurface.catalogId`, the browser looks it up.

Why does the browser SEND it, with contents? Because the browser owns the components, and the agent
must know the vocabulary to (1) teach the model and (2) validate its output. Two designs exist:

| Design | Browser sends | Agent has | Good for |
|---|---|---|---|
| **A. Inline (what we do)** | id + full JSON Schema, every request | nothing in advance | small / dynamic / third-party clients, learning |
| **B. IDs only** | just `supportedCatalogIds` | its own copy of the schema (`CatalogConfig.from_path`) | big, stable, production catalogs (the spec's default) |

## Measured numbers (our current setup)
| What | Size |
|---|---|
| Capabilities sent in `message.metadata`, per request | **25,575 bytes** |
| ...of which the 18 BASIC components (agent already has them) | 18,289 bytes (72%) |
| ...of which our `StatCard` | 1,060 bytes (**4%**) |
| LLM prompt, basic catalog only | 41,595 chars |
| LLM prompt, + our StatCard | 42,064 chars: StatCard costs **~470 chars (~120 tokens)** |
| Provider-reported prompt size | ~10,230 tokens (OpenAI) / ~10,330 (Gemini) |
| Prompt pruned to 6 of 18 basic components | 31,770 chars: **24% smaller** |

Growth is roughly LINEAR: each new component ~ +1 KB on the wire and ~ +120 prompt tokens
(extrapolation: 50 custom components ~ +50 KB and ~ +6k tokens per request).
The wire is the small problem (25 KB is tiny on localhost). The real cost is prompt tokens: money + latency.

## Levers, in the order to reach for them
1. **Prompt caching (free, already works).** The system prompt is an identical prefix on every request.
   Measured on OpenAI gpt-5.4-nano: call 1 `cached_tokens=0`, call 2 `cached_tokens=9984` of 10,229 (97.6%),
   no code change. Cached tokens are billed cheaper (check current pricing; not measured here).
   On gemini-3.5-flash-lite the same test reported no cached tokens (inconclusive; Gemini has an explicit
   caching API we did not try). RULE: keep the prompt prefix stable. Never put per-request text first.
2. **Switch big catalogs to IDs only (design B).** Wire cost drops to ~0. Cost: two copies that must agree.
   Mitigate with versioned ids (`stats-v1` -> `stats-v2`) and by GENERATING the agent's copy from the browser's
   Zod source (`npm run export:caps` already does this). Not yet verified: loading that exported catalog
   through `CatalogConfig.from_path` (I would test it first).
3. **Prune per request.** SDK `ComponentPruningTransformer` keeps only chosen components in the prompt
   (24% saved with 6/18 basic ones). Choose by screen, user role, or a cheap intent step.
4. **Several small catalogs instead of one giant one** (checkout, analytics, ...). The client lists the
   catalogs active for the current screen in `supportedCatalogIds`.
5. **Fewer, more general components.** One `Chart` with a `kind` enum beats 15 chart components.
6. **Cache parsed catalogs on the agent** (key = catalogId + hash). Saves CPU, not bytes or tokens.

## Our recommendation
Now (19 components, 25 KB, ~10k tokens): stay inline. It is simple and teaches the most.
When the catalog is > ~50 components or the prompt passes ~20k tokens: move to design B + keep prefix stable
for caching + prune by screen. Measure again with the same method before and after.

## Follow-up: how does the agent get its copy in design B? (verified)
The copy is GENERATED, not hand-written, from the browser's Zod definitions (single source of truth):

    Frontend/src/catalog/statCardApi.ts  --npm run export:caps-->  Backend/fixtures/stats-v1.catalog.json
                                                              agent: CatalogConfig.from_path(...)

Other ways to obtain it, for completeness: author the JSON Schema by hand (what some official samples do;
it drifts), or publish it from one shared package/registry that both repos depend on.

Verified experiment (browser-exported catalog saved as a file, loaded on the agent with `from_path`):
| | Design A (inline) | Design B (file + id only) |
|---|---|---|
| request metadata | 25,575 bytes | **88 bytes** |
| prompt | 42,064 chars | 42,064 chars (same content; only key ORDER in a few function defs differs) |
| good StatCard | accepted | accepted |
| `trend: "sideways"` | rejected | rejected |
| `trend: {"path": ...}` | rejected | rejected |

Risks of B (drift): browser ships `stats-v2` but the agent still has v1. Defences: version the id whenever
a component changes, regenerate the file in CI/build, fail the build if `git diff` shows the generated
file changed but was not committed, and make the agent reject unknown ids (it does: no catalog match -> error).
