"""Exercise the real ADK/A2UI/AG-UI path with a fake model; no keys or network calls."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import httpx
from a2ui.core.exceptions import A2uiCatalogError, A2uiValidationError
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr, ValidationError
from starlette.testclient import TestClient

from ag_ui.core import Event, EventType
from pydantic import TypeAdapter

from a2ui_agent_app.a2ui import BASIC_CATALOG_ID, action_to_text
from a2ui_agent_app.agents import AgentConfig, create_agent
from a2ui_agent_app.runner import UiRunner, catalog_instruction
from a2ui_agent_app.server import build_app
from a2ui_agent_app.settings import Settings

CAPS = {"v0.9": {"supportedCatalogIds": [BASIC_CATALOG_ID]}}
LLM = {
    "model_name": "azure/test-deployment",
    "provider_args": {
        "api_key": "test-key",
        "api_base": "https://example.openai.azure.com/",
        "api_version": "2024-12-01-preview",
    },
}


def ui_output(
    component: str = "Text", create: bool = True, catalog_id: str = BASIC_CATALOG_ID
) -> str:
    messages = [
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "form",
                "components": [{"id": "root", "component": component, "text": "Hello"}],
            },
        }
    ]
    if create:
        messages.insert(
            0,
            {
                "version": "v0.9",
                "createSurface": {"surfaceId": "form", "catalogId": catalog_id},
            },
        )
    return "Here is your UI.\n<a2ui-json>" + json.dumps(messages) + "</a2ui-json>"


class FakeLlm(BaseLlm):
    model: str = "fake-model"
    _outputs: list[str] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request.model_copy(deep=True))
        if not self._outputs:
            raise RuntimeError("No fake model output queued.")
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=self._outputs.pop(0))])
        )


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeLlm:
    fake = FakeLlm()
    monkeypatch.setattr("a2ui_agent_app.agents.agent.LiteLlm", lambda **kwargs: fake)
    return fake


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm=LLM,
        llm_max_retries=1,
        use_system_truststore=False,
    )


async def collect(runner: UiRunner, context: str, text: str, caps: dict):
    return [part async for part in runner.respond(context, text, caps)]


def request_text(request: LlmRequest) -> str:
    return "\n".join(
        part.text
        for content in request.contents
        for part in content.parts or []
        if part.text
    )


def test_retry_followup_and_session_isolation(model: FakeLlm, settings: Settings):
    model._outputs = [ui_output("Banana"), ui_output(), ui_output(create=False), ui_output()]
    runner = UiRunner(settings)

    async def scenario():
        first = await collect(runner, "one", "a signup form", CAPS)
        action = action_to_text({"name": "submit", "surfaceId": "form", "context": {"name": "Ada"}})
        followup = await collect(runner, "one", action, CAPS)
        other = await collect(runner, "two", "another form", CAPS)
        return first, followup, other

    first, followup, other = asyncio.run(scenario())
    assert any(isinstance(p, str) and "retrying 1/1" in p for p in first)
    assert any(isinstance(p, dict) and "createSurface" in p for p in first)
    assert not any(isinstance(p, dict) and "createSurface" in p for p in followup)
    assert any(isinstance(p, dict) and "updateComponents" in p for p in followup)
    assert any(isinstance(p, dict) and "createSurface" in p for p in other)
    assert "failed validation" in request_text(model._requests[1])
    assert "a signup form" in request_text(model._requests[2])
    assert 'USER_ACTION {"name": "submit"' in request_text(model._requests[2])
    assert "a signup form" not in request_text(model._requests[3])
    # The exact catalog schema reaches the agent without ADK treating JSON braces as placeholders.
    assert str(runner.generator.create_processor(CAPS).prompt_snippet) in request_text(model._requests[0])
    assert model._requests[0].config is not None
    assert "UI-generating assistant" in str(model._requests[0].config.system_instruction)


def test_inline_catalog_and_catalog_changes(model: FakeLlm, settings: Settings):
    runner = UiRunner(settings)
    inline = json.loads((Path(__file__).parents[1] / "fixtures/inline_caps.json").read_text())
    model._outputs = [
        ui_output(catalog_id=inline["v0.9"]["supportedCatalogIds"][0]),
        ui_output(create=False),
    ]

    async def scenario():
        await collect(runner, "one", "a dashboard", inline)
        await collect(runner, "one", "a basic form", CAPS)

    asyncio.run(scenario())
    custom_prompt = str(runner.generator.create_processor(inline).prompt_snippet)
    basic_prompt = str(runner.generator.create_processor(CAPS).prompt_snippet)
    assert custom_prompt != basic_prompt
    assert custom_prompt in request_text(model._requests[0])
    assert basic_prompt in request_text(model._requests[1])
    assert custom_prompt not in request_text(model._requests[1])


def test_validation_failure_is_bounded(model: FakeLlm, settings: Settings):
    model._outputs = [ui_output("Banana"), ui_output("Banana")]
    runner = UiRunner(settings)
    with pytest.raises(A2uiValidationError):
        asyncio.run(collect(runner, "one", "a form", CAPS))
    assert len(model._requests) == 2


def test_unsupported_catalog_does_not_call_model(model: FakeLlm, settings: Settings):
    with pytest.raises(A2uiCatalogError):
        asyncio.run(
            collect(UiRunner(settings), "one", "a form", {"v0.9": {"supportedCatalogIds": ["unknown"]}})
        )
    assert model._requests == []


def run_input(thread: str = "one", text: str = "a form") -> dict:
    return {
        "threadId": thread,
        "runId": f"run-{thread}",
        "protocolVersion": "1.0.0",
        "messages": [{"id": "user-1", "role": "user", "content": text}],
        "forwardedProps": {"a2uiClientCapabilities": CAPS},
    }


def events_of(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    adapter = TypeAdapter(Event)
    return [
        adapter.validate_json(line[5:])
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


def test_agui_endpoint_streams_ui_and_preserves_thread(model: FakeLlm, settings: Settings):
    model._outputs = [ui_output(), ui_output(create=False), ui_output()]
    with TestClient(build_app(settings)) as client:
        assert client.get("/.well-known/agent-card.json").status_code == 404
        events = events_of(client.post("/", json=run_input()))
        assert events[0].type == EventType.RUN_STARTED
        assert events[0].thread_id == "one"
        assert events[0].run_id == "run-one"
        assert events[-1].type == EventType.RUN_FINISHED
        assert events[-1].thread_id == "one"
        assert events[-1].run_id == "run-one"
        ui = [e.value for e in events if e.type == EventType.CUSTOM and e.name == "a2ui"]
        assert [next(k for k in m if k != "version") for m in ui] == [
            "createSurface", "updateComponents"
        ]
        starts = [e.message_id for e in events if e.type == EventType.TEXT_MESSAGE_START]
        ends = [e.message_id for e in events if e.type == EventType.TEXT_MESSAGE_END]
        assert starts == ends
        assert len(starts) == len(set(starts))

        body = run_input(text="submit the form")
        body["runId"] = "action-run"
        body["forwardedProps"]["a2uiAction"] = {
            "version": "v0.9",
            "action": {
                "name": "submit", "surfaceId": "form", "sourceComponentId": "submit",
                "timestamp": "2026-10-26T00:00:00Z", "context": {"name": "Ada"},
            },
        }
        followup = events_of(client.post("/", json=body))
        assert not any(
            e.type == EventType.CUSTOM and "createSurface" in e.value for e in followup
        )
        assert 'USER_ACTION {"name": "submit"' in request_text(model._requests[1])
        assert "a form" in request_text(model._requests[1])
        events_of(client.post("/", json=run_input("two", "another screen")))
        assert "a form" not in request_text(model._requests[2])


@pytest.mark.parametrize(
    "body",
    [
        {},
        {**run_input(), "forwardedProps": {}},
        {**run_input(), "threadId": ""},
        {**run_input(), "messages": []},
        {**run_input(), "messages": [{"id": "a", "role": "assistant", "content": "hi"}]},
        {**run_input(), "messages": [{"id": "u", "role": "user", "content": " "}]},
        {
            **run_input(),
            "forwardedProps": {"a2uiClientCapabilities": CAPS, "a2uiAction": {"action": {}}},
        },
        {"jsonrpc": "2.0", "method": "message/stream", "params": {}},
    ],
)
def test_agui_rejects_invalid_inputs_before_streaming(
    model: FakeLlm, settings: Settings, body: dict
):
    with TestClient(build_app(settings)) as client:
        response = client.post("/", json=body)
        assert response.status_code == 422
        assert response.json()["error"]
    assert not model._requests


def test_agui_invalid_json_and_cors(model: FakeLlm, settings: Settings):
    with TestClient(build_app(settings)) as client:
        assert client.post("/", content="{").status_code == 422
        response = client.options("/", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,accept",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "X-A2A-Extensions" not in response.headers.get("access-control-expose-headers", "")


def test_agui_endpoint_uses_inline_catalog(model: FakeLlm, settings: Settings):
    inline = json.loads((Path(__file__).parents[1] / "fixtures/inline_caps.json").read_text())
    model._outputs = [ui_output(catalog_id=inline["v0.9"]["supportedCatalogIds"][0])]
    body = run_input()
    body["forwardedProps"]["a2uiClientCapabilities"] = inline
    with TestClient(build_app(settings)) as client:
        events = events_of(client.post("/", json=body))
        assert events[-1].type == EventType.RUN_FINISHED
    assert str(UiRunner(settings).generator.create_processor(inline).prompt_snippet) in request_text(
        model._requests[0]
    )


def test_agui_rejects_overlapping_runs_and_releases_thread(
    model: FakeLlm, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def ask(self, context_id, text, catalog_prompt):
            if text == "wait":
                entered.set()
                await release.wait()
            return ui_output()

        monkeypatch.setattr(UiRunner, "_ask", ask)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=build_app(settings)), base_url="http://test"
        ) as client:
            first = asyncio.create_task(client.post("/", json=run_input(text="wait")))
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                rejected = await client.post("/", json=run_input())
                assert rejected.status_code == 409
                assert "already active" in rejected.json()["error"]
                independent = events_of(await client.post("/", json=run_input("two")))
                assert independent[-1].type == EventType.RUN_FINISHED
            finally:
                release.set()
                await first
            again = events_of(await client.post("/", json=run_input()))
            assert again[-1].type == EventType.RUN_FINISHED

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["model", "validation", "catalog"])
def test_agui_errors_are_terminal_and_allow_next_run(
    model: FakeLlm, settings: Settings, failure: str, caplog: pytest.LogCaptureFixture
):
    body = run_input()
    if failure == "validation":
        model._outputs = [ui_output("Banana"), ui_output("Banana")]
    elif failure == "catalog":
        body["forwardedProps"]["a2uiClientCapabilities"] = {
            "v0.9": {"supportedCatalogIds": ["unknown"]}
        }
    with TestClient(build_app(settings)) as client:
        events = events_of(client.post("/", json=body))
        assert events[0].type == EventType.RUN_STARTED
        assert events[-1].type == EventType.RUN_ERROR
        assert events[-1].message
        assert not any(e.type == EventType.RUN_FINISHED for e in events)
        assert not any(e.type == EventType.CUSTOM for e in events)
        model._outputs = [ui_output()]
        next_events = events_of(client.post("/", json=run_input()))
        assert next_events[-1].type == EventType.RUN_FINISHED
    assert "Failed to detach context" not in caplog.text


@pytest.mark.parametrize(
    ("llm", "message"),
    [
        (None, "LLM is not set"),
        (
            {**LLM, "provider_args": {**LLM["provider_args"], "api_key": ""}},
            "missing api_key",
        ),
        ({"model_name": LLM["model_name"]}, "missing api_key, api_base, api_version"),
    ],
)
def test_missing_credentials_fail_explicitly(llm: dict | None, message: str):
    config = AgentConfig(_env_file=None, llm=llm)
    with pytest.raises(RuntimeError, match=message):
        create_agent(config, catalog_instruction)


def test_provider_args_reach_litellm(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    monkeypatch.setattr(
        "a2ui_agent_app.agents.agent.LiteLlm",
        lambda **kwargs: captured.update(kwargs) or FakeLlm(),
    )
    llm = {**LLM, "provider_args": {**LLM["provider_args"], "timeout": 5}}
    config = AgentConfig(_env_file=None, llm=llm, generate_content={"temperature": 0.1})
    agent = create_agent(config, catalog_instruction)
    assert captured == {
        "model": "azure/test-deployment",
        **LLM["provider_args"],
        "timeout": 5,
        "num_retries": 3,
    }
    assert agent.generate_content_config.temperature == 0.1


def test_env_json_config_and_secret_masking(monkeypatch: pytest.MonkeyPatch):
    llm = {**LLM, "provider_args": {**LLM["provider_args"], "api_key": "test-secret"}}
    monkeypatch.setenv("LLM", json.dumps(llm))
    monkeypatch.setenv("GENERATE_CONTENT", '{"temperature": 0.2}')
    monkeypatch.setenv("AGENT_HOST", "example.local")
    monkeypatch.delenv("AGENT_BIND_HOST", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm is not None
    assert settings.llm.model_name == "azure/test-deployment"
    assert settings.llm.provider_args["api_key"] == "test-secret"
    assert settings.generate_content is not None
    assert settings.generate_content.temperature == 0.2
    assert settings.agent_bind_host == "example.local"
    assert "test-secret" not in repr(settings)
    with pytest.raises(ValidationError, match="model_name"):
        Settings(_env_file=None, llm={"model_name": "openai/gpt-4.1"})
