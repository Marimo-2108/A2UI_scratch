# Milestone 4: Gemini decides the UI

## Run it
```
cd agent
copy .env.example .env      # then set GEMINI_API_KEY (never commit .env)
uv run a2ui-agent           # AGENT_MODE=llm in .env; set AGENT_MODE=scripted for the fixed UI
uv run python tests/manual/try_agent.py "a small signup form"   # poke it without a browser
```
Web: tab "M2 · Live agent" -> **New conversation** (fresh screen + memory) or **Follow-up**
(same conversation, same screen).

## What the agent does per request
```
client caps ──> generator.create_processor(caps)   # SDK-side negotiation: which catalogs are active
                       │
 system prompt = our ROLE + RULES + processor.prompt_snippet   (A2UI format + full JSON schema, ~10k tokens)
 memory        = Gemini "contents" kept per contextId (in RAM)
                       │
                    Gemini ──> text with  <a2ui-json>[ ...messages... ]</a2ui-json>
                       │
        processor.parse_response(text)  ── heals small JSON slips, VALIDATES vs catalog
             ok │                     │ A2uiValidationError
                v                     v
   one DataPart per A2UI message    send the error text back to Gemini, ask again (max 2 retries)
```
A click arrives as a DataPart, becomes the text `USER_ACTION {...}`, and goes through the same loop.

## Why validate at all?
v0.9 is "prompt-first": the model is *asked* to follow the schema, nothing forces it. Validation
is the safety net between a probabilistic model and your UI. Example from the probe:
`Unrecognized component type 'Banana'`: a message the model can read and fix.

## Findings
| Topic | What happened | What we did |
|---|---|---|
| Protocol version | SDK + web lib validate `"version": "v0.9"`; passing `v0.9.1` to `create_processor` raises. Spec doc is ahead of the libraries. | Whole stack uses `v0.9`; extension URI `.../a2ui/v0.9` |
| MIME type | SDK labels v0.9 parts `application/json+a2ui` (old name) | use SDK `create_a2ui_part`; web accepts both |
| SDK on PyPI | `a2ui-agent-sdk` 0.8.0 on PyPI predates `A2uiGenerator`/`processor` that the docs describe | install both packages from the public GitHub repo, **pinned to a commit** (git dependency in `agent/pyproject.toml`). Needs access to github.com; no local clone needed. |
| TLS | `CERTIFICATE_VERIFY_FAILED: self-signed certificate in chain` for google domains only | `truststore` -> Python uses the OS cert store. Verification stays ON. |
| Transient 503 | "model is currently experiencing high demand" (varies per model, per hour) | `HttpRetryOptions` backoff (429/5xx), and pick a model that is serving |
| Latency | default ~43s, MEDIUM ~24s, **LOW ~5-12s**, same valid UI. `MINIMAL` is rejected by 3.8-flash. | `GEMINI_THINKING_LEVEL=LOW` default (`bench_thinking.py` reproduces the numbers) |
| Prompt size | ~10,180 tokens every request | later: prune the catalog to the components we need |

## Observed model behaviour (good)
- Wired the button: `action.event.name = submit_signup`, `context` bound to `/name` and `/email`.
- After the click it kept the same `surfaceId`, sent only `updateComponents` (no `createSurface`),
  and used a bound `formatString` function for the confirmation text.
- Message order was `createSurface, updateDataModel, updateComponents`; the client doesn't mind.

## Files
(Original Milestone 4 layout; see "Addendum: Google ADK" below for where these live now.)
- `agent/config.py`        all settings from env / `.env` (+ truststore)
- `agent/gemini_brain.py`  prompt, Gemini call, validate + retry loop, per-context memory
- `agent/executor.py`      one flow for both brains; negotiation -> brain -> status-updates
- `agent/try_agent.py`     CLI client; `agent/bench_thinking.py` latency benchmark

## Known limits (on purpose, for now)
- Wait-for-full-response: the UI appears all at once after ~5-12s. The SDK has an incremental
  parser (`processor.create_parser()`) to render while tokens stream. Candidate for Milestone 5.
- Memory is in RAM per contextId; restart the agent and conversations are forgotten.
- Full schema in every prompt (cost + latency).

## Addendum: provider layer (Gemini or OpenAI)
`agent/llm.py` is the only file that knows the vendor. Everything else talks to a tiny interface:
`complete(system, messages) -> text`. Choose with `LLM_PROVIDER=gemini|openai` in `.env`.
`gemini_brain.py` became the vendor-neutral `ui_brain.py`. `AGENT_MODE=llm` (alias `gemini`).

Lesson: A2UI is a *format*. Prompt building, validation, retry and the client never changed.

OpenAI setup: add `OPENAI_API_KEY` and `OPENAI_MODEL` to `agent/.env`;
`uv run python tests/manual/list_models.py openai` shows what your key can use. Reasoning models take
`OPENAI_REASONING_EFFORT` (and reject a custom temperature, so we send one or the other).

### Reliability lessons (same day)
- A model can stall instead of failing: `gemini-3.8-flash` returned 504 DEADLINE_EXCEEDED while
  `gemini-3.5-flash-lite` answered in <1s. Our agent had NO timeout and hung for minutes.
  Fixed: `LLM_TIMEOUT_S` (default 60) per call, 3 attempts, then a clear error in the UI.
- Speed vs quality is a real knob: lite ~2.5s per UI, bigger models slower. Both passed validation
  on a form + a follow-up edit in our tests (small sample, not a benchmark).
- `try_agent.py` = CLI client for the agent; `list_models.py` = which models your key can use.
  (`bench_thinking.py` was a one-off and was deleted.)

### OpenAI (gpt-4.1-mini) results
- Works through the same pipeline; no change to the client. First UI in ~5s (non-reasoning model,
  so no thinking delay; `OPENAI_REASONING_EFFORT` must stay EMPTY for it, reasoning models only).
- **Model difference found:** after a click, gpt-4.1-mini answered with TEXT ONLY ("Thank you!")
  and left the form on screen. Gemini replaced the form. Text-only passes validation, so nothing
  flagged it. Fix was a prompt rule: "EVERY reply MUST contain an A2UI block, including the reply to a
  USER_ACTION". Re-tested 2/2 runs: now sends `updateComponents` that swaps the form for a confirmation.
- Lesson: validation catches *invalid* output, not *unhelpful* output. Behaviour rules belong in the prompt.
- `.env` gotcha: python-dotenv does not warn about duplicate variables. Keep one line per variable.

### "Surface X already exists" on Follow-up
Cause (browser-side error, from the library): the model sent `createSurface` for a surface that is
already on screen. Two ways that happens: (1) the model ignores the prompt rule; (2) the agent was
RESTARTED, so its in-RAM memory of the conversation is gone, while the browser still holds the screen.
Fix in `LiveDemo.tsx`: if `createSurface` names a surface the processor already has
(`processor.getSurface(id)`), skip it and log "ignored duplicate createSurface" in the inspector;
the updateComponents / updateDataModel that follow still apply. The official React shell does the same.
Verified against the real library: a 2nd createSurface throws, getSurface detects it, updates still apply.

Related finding (same session): the model once merged updateComponents + updateDataModel into ONE
message ("multiple conflicting update actions"). The validate-and-retry loop caught it twice and the
3rd attempt was correct. That is the safety net doing its job.

Known limit: after an agent restart a Follow-up has no history. Fix later by persisting history.

## Addendum: Google ADK + team package layout
The agent now follows the same structure as our other AI agents (`nova-ai`): an installable
`src/` package, sub-packages whose `__init__.py` re-exports private `_module.py` files, Pydantic
config, and a `Protocol` for what the agent needs from its host. The LLM side is a Google ADK
`LlmAgent`; A2A, negotiation, validation/retry and surface repair are unchanged.

| Before | Now (`agent/src/a2ui_agent_app/`) |
|---|---|
| `llm.py` (own Gemini/OpenAI clients) | `agents/ui/_agent.py`: `UiAgent(LlmAgent)` on ADK `Gemini` or `LiteLlm` (`openai/<model>`) |
| `ROLE` + `RULES` in `ui_brain.py` | `agents/ui/_static_instructions.py` (ADK `static_instruction`) |
| `processor.prompt_snippet` in the system prompt | `agents/ui/_instruction_provider.py` asks the host via `AgentContextProvider` (`_protocol.py`); `server/_catalog_context.py` answers per session |
| `histories` dict | ADK `Runner` + `InMemorySessionService`, session id = A2A `contextId` |
| `config.py` (dataclass + `os.getenv`) | `server/_settings.py` (pydantic-settings, **same env var names**) -> `agents.AgentConfig` |
| `ui_brain.py` validate/retry loop | `server/_ui_brain.py` (drives the ADK runner) |
| `repair_surfaces`, `action_to_text`, `a2ui_ext.py` | `a2ui_ext/` |
| `executor.py`, `server.py`, `script.py` | `server/_executor.py`, `server/_app.py` (`uv run a2ui-agent`), `server/_scripted.py` |
| `try_agent.py`, `repro_kpi.py`, `list_models.py` | `tests/manual/` (+ `tests/manual/ui_agent` for `uv run adk web tests/manual`) |

Behaviour notes:
- With `static_instruction` set, ADK sends the dynamic instruction (the catalog schema) as a
  labelled user-content block instead of in the system prompt. Validation-retry rates on
  gpt-5.4-nano matched the old code in a side-by-side run.
- Rejected attempts and the correction messages now stay in the ADK session history (before, only
  the successful turn was kept). The model sees its own mistake on later turns; costs more tokens.
- `OPENAI_*` now goes through LiteLLM (`timeout`, `num_retries=3`, `reasoning_effort` or temperature).
