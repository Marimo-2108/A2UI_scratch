# Backend, end to end

This guide walks through the backend from process startup to the UI appearing in the browser.
It is written for someone who knows Node.js backend concepts and is getting reacquainted with
Python.

The backend is intentionally small. FastAPI hosts the endpoint, Google ADK runs the agent,
LiteLLM connects the agent to Azure, and the A2UI SDK supplies the model-facing tool and checks
its output.

## 1. The request path at a glance

```text
React browser
  │ AG-UI POST /: threadId, runId, messages, state, ...
  ▼
uvicorn                         HTTP server process; accepts sockets and serves ASGI
  ▼
FastAPI App                     CORS, health endpoint, the rest of the app
  ▼
ag_ui_adk endpoint              parses AG-UI input and streams AG-UI events
  ▼
_UiAgUiAgent                    forwards events and cleans up terminal errors
  ▼
ADKAgent / Google ADK Runner    session history and agent execution
  ▼
UiAgent                         prompt + A2UI tool + catalog
  ▼
LiteLlm                         translates ADK model calls into LiteLLM calls
  ▼
Azure OpenAI                    returns text and a send_a2ui_json_to_client tool call
  │
  ▼
A2UI tool                       parses and validates the UI against the catalog
  │ valid tool result
  ▼
AG-UI events (SSE) ────────────► browser validates the result and renders A2UI
```

The browser and backend speak AG-UI. The agent speaks to Azure through LiteLLM. The UI itself
is A2UI JSON carried in the result of an agent tool call; it is not a separate HTTP endpoint.

## 2. Python concepts in Node.js terms

| Python | Rough Node.js equivalent |
|---|---|
| `from .agents import UiAgent` | Import from a sibling module, like `import { UiAgent } from './agents'` |
| `from ..agents import UiAgent` | Import from the parent package, like `import { UiAgent } from '../agents'` |
| `__init__.py` | Makes a directory a Python package; can also act like a barrel `index.js` |
| `class App(FastAPI):` | `class App extends FastAPI` |
| `self` | `this` |
| `super().__init__(...)` | `super(...)` |
| `@router.get("/health")` | A decorator that registers a route, roughly `router.get('/health', handler)` |
| `async def` | `async function` |
| `async for item in stream` | `for await (const item of stream)` |
| `async def ...: yield item` | An async generator, like `async function*` |
| `async with aclosing(stream)` | A `try/finally` that guarantees an async iterator is closed |
| `dict[str, Any]` | A type hint for an object with string keys and arbitrary values |
| `str \| None` | A string or `None` (roughly `string | null`) |
| `**mapping` | Spread a mapping into keyword arguments, similar to `fn(...args)` or object spread |
| `{**a, **b}` | Merge mappings; keys in `b` replace the same keys in `a`, like `{...a, ...b}` |
| `raise Error(...)` / `except Error` | `throw` / `catch` |
| `Path(__file__).parent / "file"` | Resolve a path next to this module, like `path.join(__dirname, "file")` |

Python type hints alone usually do not validate values at runtime. Here, Pydantic and FastAPI
use type information at runtime for configuration and request validation.

## 3. Files and responsibilities

Paths below are relative to `Backend/src/a2ui_agent_app/`.

| File | Responsibility |
|---|---|
| [`main.py`](../Backend/src/a2ui_agent_app/main.py) | Process entry point: load settings, initialize TLS trust, build the app, start uvicorn. |
| [`_config.py`](../Backend/src/a2ui_agent_app/_config.py) | Server settings, including `.env`, model config, catalog path, host and port. |
| [`_app.py`](../Backend/src/a2ui_agent_app/_app.py) | Creates FastAPI, middleware, catalog, LiteLLM model, agent and routes. |
| [`agents/_config.py`](../Backend/src/a2ui_agent_app/agents/_config.py) | Pydantic model for the LiteLLM config. |
| [`agents/_ui_agent.py`](../Backend/src/a2ui_agent_app/agents/_ui_agent.py) | The ADK `LlmAgent`, its system prompt and A2UI toolset. |
| [`agents/system-prompt.txt`](../Backend/src/a2ui_agent_app/agents/system-prompt.txt) | Instructions describing how the model should respond and use A2UI. |
| [`api/_ui_agent.py`](../Backend/src/a2ui_agent_app/api/_ui_agent.py) | Adapts the agent to AG-UI and registers the `POST /` endpoint. |
| [`api/_health.py`](../Backend/src/a2ui_agent_app/api/_health.py) | Simple `GET /health` liveness endpoint. |
| [`agents/__init__.py`](../Backend/src/a2ui_agent_app/agents/__init__.py), [`api/__init__.py`](../Backend/src/a2ui_agent_app/api/__init__.py) | Re-export names for convenient imports. |

## 4. Startup: from command to listening HTTP server

### 4.1 The project command

From `Backend/`, run:

```bash
uv run a2ui-agent
```

`uv` reads [`pyproject.toml`](../Backend/pyproject.toml) and the lock file, uses the project's
virtual environment, and makes the installed Python dependencies available. This is roughly like
using `npm run` with packages from `node_modules`.

The project defines this script entry:

```toml
[project.scripts]
a2ui-agent = "a2ui_agent_app.main:main"
```

It means “import `a2ui_agent_app.main` and call its `main()` function.” Python does not need a
separate TypeScript-style compile step. It parses and compiles modules to bytecode as they are
imported; `uv` is handling the environment and command, not compiling the application.

### 4.2 [`main.py`](../Backend/src/a2ui_agent_app/main.py)

The startup function first configures logging:

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
```

This sets a useful default for application and library messages.

Then it loads and validates the environment:

```python
config = BackendConfig()
```

`BackendConfig` is a Pydantic Settings class. It reads the `.env` file and process environment
variables and converts values to declared Python types. An actual environment variable takes
precedence over the `.env` value.

If configured, the process injects the operating system's certificate store into Python's TLS
stack:

```python
if config.use_system_truststore:
    import truststore
    truststore.inject_into_ssl()
```

This is useful in environments with a corporate certificate authority. It does not turn off
certificate verification; it changes which trusted certificates Python can use.

Next, startup creates the app:

```python
app = App(config)
```

Configuration errors and expected setup errors are turned into a concise startup message:

```python
except (ValidationError, RuntimeError) as e:
    sys.exit(f"Backend config error ...\n{e}")
```

`sys.exit` terminates the process with a non-zero exit status. This is preferable to accepting
bad settings and failing later on the first user request.

Finally:

```python
uvicorn.run(app, host=..., port=...)
```

Uvicorn is the HTTP server process, comparable to Node's `http.createServer(...).listen(...)`.
FastAPI defines how requests are handled; Uvicorn opens the socket, accepts HTTP traffic and calls
the ASGI application. `agent_host` controls where Uvicorn listens. It defaults to `localhost`;
the dev container sets it to `0.0.0.0` so forwarded connections can reach the backend.
`agent_port` defaults to `10010`.

The `if __name__ == "__main__":` block is similar to checking `require.main === module` in
CommonJS: it calls `main()` only when this file itself is executed as a script.

## 5. Configuration: [`_config.py`](../Backend/src/a2ui_agent_app/_config.py)

`BackendConfig` inherits from `BaseSettings`. This combines environment loading with Pydantic
validation, similar to loading dotenv values and parsing them with a Zod schema.

```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_ignore_empty=True,
    extra="ignore",
)
```

- The `.env` path is relative to the process's current working directory. Running from
  `Backend/` makes that `Backend/.env`.
- Empty environment values are treated as unset.
- Unknown environment variables are ignored. This allows unrelated or older keys to exist
  without making startup fail; it also means a misspelled setting may be silently ignored.

Important fields:

| Field | Source/default | Purpose |
|---|---|---|
| `llm: LiteLlmConfig` | Required `LLM` JSON variable | Model identifier and provider arguments. |
| `generate_content` | Optional `GENERATE_CONTENT` JSON variable | ADK generation settings, such as temperature. |
| `a2ui_catalog_path` | `fixtures/stats-v1.catalog.json` | Components and schema allowed for generated UI. |
| `agent_host` | `AGENT_HOST`, default `localhost` | Server bind host. |
| `agent_port` | `AGENT_PORT`, default `10010` | TCP port for uvicorn. |
| `web_origin_regex` | Default `http://localhost:\d+` | Browser origins allowed by CORS middleware. |
| `use_system_truststore` | `USE_SYSTEM_TRUSTSTORE`, default `True` | Whether to use the OS certificate store. |

The nested model type lives in [`agents/_config.py`](../Backend/src/a2ui_agent_app/agents/_config.py):

```python
class LiteLlmConfig(BaseModel):
    model_name: str
    provider_args: dict[str, Any] = Field(default_factory=dict, repr=False)
```

`model_name` is a LiteLLM identifier such as `azure/<deployment-name>`. `provider_args` holds
the Azure-specific values. `repr=False` keeps the dictionary (including its API key) out of the
model's usual debug representation. Do not print or log `provider_args` yourself.

The relevant shape in `.env` is JSON:

```env
LLM={"model_name":"azure/<deployment-name>","provider_args":{"api_key":"...","api_base":"https://<resource>.openai.azure.com/","api_version":"2025-04-01-preview"}}
```

For GPT-5.4+ Azure deployments, the tested setup also sets
`"reasoning_effort":"none"` in `provider_args`. In the current LiteLLM/ADK combination, another
reasoning effort can route tool-enabled requests through the Azure Responses API and present the
text and function call as separate choices; ADK can then consume the text without the A2UI tool
call. This is model/provider-specific behavior, not a general rule for every Azure model. The
example config in [`Backend/.env.example`](../Backend/.env.example) contains further notes.

## 6. Building the FastAPI app: [`_app.py`](../Backend/src/a2ui_agent_app/_app.py)

`App` subclasses FastAPI:

```python
class App(FastAPI):
    def __init__(self, config: BackendConfig) -> None:
        super().__init__(title="A2UI Agent", docs_url="/docs", redoc_url=None)
```

The call to `super()` initializes FastAPI itself and enables interactive OpenAPI docs at
`/docs`.

### 6.1 CORS and health route

```python
self.add_middleware(
    CORSMiddleware,
    allow_origin_regex=config.web_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)
self.include_router(health_router)
```

The React development server and backend usually have different origins because they use
different ports. CORS middleware adds response headers that allow the browser to read the
response, and handles browser preflight requests.

CORS is not authentication or server-side access control. A script or `curl` can call the
endpoint without a browser enforcing CORS. Do not expose this unauthenticated development
backend to untrusted networks.

`include_router` mounts the `/health` endpoint defined in
[`api/_health.py`](../Backend/src/a2ui_agent_app/api/_health.py). It returns
`{"status":"ok"}` and does not contact the model.

### 6.2 Check the Azure arguments

```python
_REQUIRED_PROVIDER_ARGS = ("api_key", "api_base", "api_version")
missing = [k for k in _REQUIRED_PROVIDER_ARGS if not config.llm.provider_args.get(k)]
if missing:
    raise RuntimeError(...)
```

This checks that the required Azure settings are non-empty before listening for requests. The
list comprehension is equivalent to filtering the required keys for ones with missing values.
Failing early makes configuration errors easier to understand than waiting for the first model
call.

The app also supplies defaults:

```python
_DEFAULT_PROVIDER_ARGS = {"timeout": 60, "num_retries": 3}
```

The merge below applies defaults first and user-supplied values second, so `.env` values override
defaults:

```python
{**_DEFAULT_PROVIDER_ARGS, **config.llm.provider_args}
```

### 6.3 Load the A2UI catalog

```python
catalog = Catalog.from_json(
    json.loads(config.a2ui_catalog_path.read_text(encoding="utf-8")),
    protocol_version="v0.9",
)
```

The catalog is the contract for which components and properties the model can use. It includes
the app's standard A2UI components and custom components exported from the frontend. The backend
uses the same catalog both to inform the model and validate its proposed UI.

The path is relative to the current working directory, which is why the backend commands should
be run from `Backend/`. File and JSON errors are wrapped as a `RuntimeError` with the catalog
path, making the startup failure explicit.

### 6.4 Construct and register the agent

```python
ui_agent = UiAgent(
    llm=LiteLlm(
        model=config.llm.model_name,
        **{**_DEFAULT_PROVIDER_ARGS, **config.llm.provider_args},
    ),
    catalog=catalog,
    generate_content_config=config.generate_content,
)
register_ui_agent(ui_agent, self)
```

`LiteLlm` is Google ADK's model adapter. It receives the model name plus provider arguments and
uses LiteLLM to call Azure. This construction does not call Azure yet; the network request
happens when a user request invokes the agent.

`UiAgent` is created once at startup and registered with the FastAPI app. It is not created anew
for every HTTP request.

## 7. The agent: [`agents/_ui_agent.py`](../Backend/src/a2ui_agent_app/agents/_ui_agent.py)

`UiAgent` subclasses ADK's `LlmAgent`. In its constructor it calls the parent with four key
things:

1. **Name and description** — metadata for ADK.
2. **Model** — the `LiteLlm` instance constructed by `_app.py`.
3. **Static instruction** — `system-prompt.txt` loaded from the directory beside the Python file.
4. **Toolset** — `SendA2uiToClientToolset`, configured with the catalog.

The toolset exposes the model-facing function
`send_a2ui_json_to_client(a2ui_json: string)`. It adds the catalog's schema to the instructions
and provides the tool the model calls to submit its UI.

The system prompt asks the model to produce one short sentence and make the tool call in the same
turn. It also explains A2UI behavior such as reusing an existing surface on follow-ups, making
buttons actionable, and using a root component.

At a high level, ADK runs an agent loop:

```text
send prompt + tool definitions to model
  ├─ model returns final text → finish
  └─ model calls a tool → execute tool → send tool result back to model → continue
```

A valid A2UI tool result is marked so the agent can finish without a redundant model call to
summarize the tool output.

## 8. Registering the route: [`api/_ui_agent.py`](../Backend/src/a2ui_agent_app/api/_ui_agent.py)

The helper `register_ui_agent(ui_agent, app)` wraps the ADK agent with `ag_ui_adk`:

```python
ag_ui_agent = _UiAgUiAgent(
    adk_agent=ui_agent,
    app_name="a2ui_agent_app",
    user_id="a2ui-client",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
    run_config_factory=lambda _input: RunConfig(streaming_mode=StreamingMode.NONE),
)
add_adk_fastapi_endpoint(app, ag_ui_agent, path="/")
```

The AG-UI adapter bridges two frameworks:

- It accepts an AG-UI run input from the browser.
- It invokes the ADK agent.
- It translates ADK progress and results into AG-UI events.

The adapter keeps conversation sessions in memory. A conversation is associated with its AG-UI
`threadId`; a follow-up on that thread can use ADK's stored history. Sessions expire after an
hour of inactivity. A server restart loses these sessions because no persistent database is
configured.

`StreamingMode.NONE` disables token-by-token streaming from the model. The HTTP response is
still a stream of AG-UI events. This distinction matters: LiteLLM's model streaming has produced
empty replies for some proxy error responses, while a non-streaming request produces a useful
exception.

`add_adk_fastapi_endpoint` registers the AG-UI endpoint at `POST /` and any other endpoints
provided by the installed `ag_ui_adk` version. The app explicitly registers `/health`; see the
library's installed version for adapter-specific auxiliary routes.

### 8.1 Why there is an `_UiAgUiAgent` wrapper

The wrapper overrides `run`, an async generator of AG-UI events:

```python
async with aclosing(super().run(input)) as events:
    async for event in events:
        if event.type == EventType.RUN_ERROR:
            yield event.model_copy(update={"message": _short_error(event.message)})
            return
        yield event
```

Most events pass through unchanged. On `RUN_ERROR`, the wrapper optionally shortens the message
and ends the stream. The AG-UI adapter may otherwise emit a `RUN_FINISHED` after `RUN_ERROR`;
the frontend treats a terminal error as the end of the run, so an event after it can hide the
original useful error.

`aclosing` guarantees the wrapped async generator is closed in the same task, including when an
error ends the stream or the client disconnects. That ensures ADK's tracing context is cleaned up
in the context where it was created. It also addresses the earlier
“Failed to detach context” cleanup error.

`_short_error` is narrowly for proxy/firewall failures. If an exception contains an HTML page, it
extracts the page title (for example, `Blocked by Cloudflare Gateway`) instead of sending the
entire HTML document through the UI. Plain error messages are returned unchanged.

## 9. One request, from browser to rendered UI

### Step 1: the frontend starts a run

The frontend uses `HttpAgent` from `@ag-ui/client` in
[`Frontend/src/agui/client.ts`](../Frontend/src/agui/client.ts). It sends an AG-UI request
containing fields such as:

```json
{
  "threadId": "conversation-id",
  "runId": "request-id",
  "messages": [
    {"id": "message-id", "role": "user", "content": "Make a signup form"}
  ],
  "state": {},
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

The exact request is defined by the AG-UI protocol and client library. `threadId` identifies the
conversation; `runId` identifies this particular execution.

### Step 2: FastAPI and the AG-UI adapter accept the request

`add_adk_fastapi_endpoint` owns the route implementation. It parses the incoming JSON as an
AG-UI `RunAgentInput` (a Pydantic model from the protocol packages). Invalid request structure
is rejected before a model call. The endpoint returns an event stream rather than waiting to
assemble one large response.

### Step 3: the adapter starts or resumes the conversation

The adapter uses the request's `threadId` to find the in-memory ADK session or create one. It
hands the new user input to the ADK runner. The browser may include the message history in the
run input, while the adapter is responsible for interpreting the run and maintaining its own
session state.

### Step 4: ADK prepares the model request

The request includes:

- The system instructions from `system-prompt.txt`.
- The catalog schema supplied through the A2UI toolset.
- The tool definition for `send_a2ui_json_to_client`.
- The current user message and prior session conversation.

### Step 5: LiteLLM calls Azure

ADK calls the `LiteLlm` adapter. LiteLLM uses `model_name` to select the Azure provider and
`provider_args` for the endpoint, API version, key, and optional generation parameters. The
configured timeout and retry count apply to the model request.

### Step 6: the model responds with text and a tool call

The intended response is a short sentence plus a function call to
`send_a2ui_json_to_client`. The function's `a2ui_json` argument is a JSON string containing an
array of A2UI messages, for example a `createSurface` followed by `updateComponents`.

### Step 7: the A2UI tool validates the proposed UI

The tool parses the JSON and checks it against the A2UI catalog and protocol. It does not send
invalid UI to the browser. If validation fails, the tool returns an error as its tool result.
ADK passes that error back to the model, which can correct the payload and call the tool again.
There is no application-level fixed retry loop around this tool in our code; ADK controls the
agent execution loop.

When valid, the tool result contains `validated_a2ui_json`. The result is associated with the
tool call, so the frontend can distinguish A2UI payloads from ordinary text.

### Step 8: AG-UI events stream back over HTTP

The adapter translates agent activity into AG-UI events, such as:

```text
RUN_STARTED
TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END
TOOL_CALL_RESULT
STATE_SNAPSHOT
RUN_FINISHED
```

Not every run contains every event. For example, an Azure failure ends in `RUN_ERROR`, and the
UI tool call produces tool-call events. These are Server-Sent Events (SSE), typically delivered
as `data: <JSON>\n\n` records while the HTTP response remains open.

### Step 9: the browser validates and renders

The frontend looks for the result of the A2UI tool call and parses its
`validated_a2ui_json` value. It validates the message shape in the client and passes valid
messages into the A2UI renderer. The renderer updates the visible surface.

For a follow-up or button action, the same thread lets the model see earlier conversation
context. The prompt tells it not to create the same surface again; it should update that surface
instead.

## 10. Validation: what is checked and why

| Check | Where | Why |
|---|---|---|
| Required `LLM` config parses into the expected shape | Pydantic `BackendConfig` and `LiteLlmConfig` | Detects malformed or missing config before the server starts. |
| `api_key`, `api_base`, `api_version` are non-empty | `_app.py` | Produces a clear startup error instead of a later provider error. |
| Catalog JSON can be read and parsed | `_app.py` | Both the model instructions and tool validation depend on a valid catalog. |
| Request conforms to AG-UI input structure | Installed `ag_ui_adk` FastAPI endpoint | Prevents malformed protocol input from reaching the agent. |
| A2UI JSON can be parsed and matches the catalog/protocol | A2UI `SendA2uiToClientToolset` | Stops unknown components or malformed UI from reaching the renderer. |
| Tool errors are returned to the model | ADK tool loop | Gives the model an opportunity to correct its output instead of displaying broken UI. |
| A2UI tool result matches the frontend schema | `Frontend/src/agui/client.ts` | Defense in depth before messages are given to the renderer. |
| HTML proxy error pages are shortened | `_short_error` in `api/_ui_agent.py` | Keeps an HTML block page from flooding the UI instead of showing the actual reason. |

The backend does not implement a separate authentication check. CORS only affects browser
behavior and does not prevent non-browser clients from making requests.

## 11. Errors and observable behavior

| Problem | Expected behavior |
|---|---|
| Invalid `.env`, absent required `LLM`, or missing Azure provider argument | Startup stops with a configuration message. |
| Missing or invalid catalog file | Startup stops and includes the catalog path in the error. |
| Port already in use | Uvicorn reports a bind error; another process is already listening there. |
| Malformed AG-UI request | The endpoint rejects it before calling the model. |
| Azure returns a provider error | The AG-UI stream ends with `RUN_ERROR`; HTML proxy pages are shortened. |
| A2UI tool validation fails | The model receives the validation error and can try to repair its tool call. |
| Backend restarts | In-memory session history is lost; start a new conversation. |
| Follow-up occurs within a live session | ADK can use stored thread history to continue the conversation. |

## 12. Useful commands

Run them from `Backend/`:

```bash
# Start the server
uv run a2ui-agent

# Test backend behavior without real Azure credentials
uv run pytest -q

# Check liveness after startup
curl http://localhost:10010/health
```

The tests replace LiteLLM with a fake model, so they can exercise the app, agent/tool behavior,
error handling and AG-UI events without spending Azure tokens or relying on network access.

## 13. Further reading

- [Backend README](../Backend/README.md)
- [AG-UI migration notes](./07-agui-migration.md)
- [A2UI custom component notes](./05-custom-component.md)
- [Reference implementation: `ksachdeva/adk-openui-example`](https://github.com/ksachdeva/adk-openui-example)