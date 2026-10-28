"""Exercise the real ADK + ag_ui_adk + A2UI SDK path with a fake model; no keys or network calls."""

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr, ValidationError

from a2ui_agent_app._app import App
from a2ui_agent_app._config import BackendConfig

CATALOG_ID = "https://scratch.local/a2ui/catalogs/stats-v1.json"
LLM = {
    "model_name": "azure/test-deployment",
    "provider_args": {
        "api_key": "test-key",
        "api_base": "https://example.openai.azure.com/",
        "api_version": "2024-12-01-preview",
    },
}


def ui_call(component: str = "Text", create: bool = True) -> list[types.Part]:
    """A model turn: one sentence, then a call to the A2UI SDK tool."""
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
            0, {"version": "v0.9", "createSurface": {"surfaceId": "form", "catalogId": CATALOG_ID}}
        )
    call = types.FunctionCall(
        name="send_a2ui_json_to_client", args={"a2ui_json": json.dumps(messages)}
    )
    return [types.Part(text="Here is your UI."), types.Part(function_call=call)]


class FakeLlm(BaseLlm):
    model: str = "fake-model"
    _outputs: list[list[types.Part] | Exception] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request.model_copy(deep=True))
        output = self._outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        yield LlmResponse(content=types.Content(role="model", parts=output))


@pytest.fixture
def config() -> BackendConfig:
    return BackendConfig(_env_file=None, llm=LLM, use_system_truststore=False)


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeLlm:
    fake = FakeLlm()
    monkeypatch.setattr("a2ui_agent_app._app.LiteLlm", lambda **kwargs: fake)
    return fake


def run(client: TestClient, messages: list[dict], run_id: str = "run-1") -> list[dict]:
    body = {
        "threadId": "thread-1",
        "runId": run_id,
        "state": {},
        "messages": messages,
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    response = client.post("/", json=body)
    assert response.status_code == 200, response.text
    return [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]


def tool_results(events: list[dict]) -> list[dict]:
    return [json.loads(e["content"]) for e in events if e["type"] == "TOOL_CALL_RESULT"]


def user(text: str, id: str = "user-1") -> dict:
    return {"id": id, "role": "user", "content": text}


def test_invalid_ui_is_returned_to_model_and_fixed(model: FakeLlm, config: BackendConfig):
    model._outputs = [ui_call("Banana"), ui_call()]
    events = run(TestClient(App(config)), [user("a signup form")])

    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"
    first, second = tool_results(events)
    assert "Banana" in first["error"]
    assert [next(k for k in m if k != "version") for m in second["validated_a2ui_json"]] == [
        "createSurface",
        "updateComponents",
    ]
    # The catalog schema reaches the model, and the validation error is sent back to it.
    assert "BEGIN A2UI JSON SCHEMA" in str(model._requests[0].config.system_instruction)
    assert "StatCard" in str(model._requests[0].config.system_instruction)
    assert "Banana" in str(model._requests[1].contents[-1])
    # A successful tool call ends the turn; no extra model call to summarize it.
    assert len(model._requests) == 2


def test_static_instruction_reaches_model(
    model: FakeLlm, config: BackendConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    prompt = "Generate a UI for a caf\u00e9.\n"
    (tmp_path / "system-prompt.txt").write_text(prompt, encoding="utf-8")
    monkeypatch.setattr("a2ui_agent_app.agents._ui_agent.__file__", str(tmp_path / "_ui_agent.py"))
    model._outputs = [ui_call()]

    events = run(TestClient(App(config)), [user("a form")])

    assert events[-1]["type"] == "RUN_FINISHED"
    assert prompt in str(model._requests[0].config.system_instruction)


def test_follow_up_keeps_conversation(model: FakeLlm, config: BackendConfig):
    client = TestClient(App(config))
    model._outputs = [ui_call()]
    run(client, [user("a signup form")])

    model._outputs = [ui_call(create=False)]
    events = run(
        client,
        [user("a signup form"), user('USER_ACTION {"name": "submit"}', "user-2")],
        "run-2",
    )

    assert events[-1]["type"] == "RUN_FINISHED"
    assert "validated_a2ui_json" in tool_results(events)[0]
    history = str(model._requests[-1].contents)
    assert "a signup form" in history and "USER_ACTION" in history


@pytest.mark.parametrize(
    "message",
    ["Blocked by gateway", "<html><head><title>Blocked by gateway</title></head></html>"],
)
def test_model_failure_is_reported_by_adapter(model: FakeLlm, config: BackendConfig, message: str):
    client = TestClient(App(config))
    model._outputs = [RuntimeError(message)]
    events = run(client, [user("a form")])

    assert [e["type"] for e in events] == ["RUN_STARTED", "RUN_ERROR", "RUN_FINISHED"]
    assert message in events[1]["message"]

    model._outputs = [ui_call()]
    assert run(client, [user("a form")], "run-2")[-1]["type"] == "RUN_FINISHED"


def test_health_and_cors(model: FakeLlm, config: BackendConfig):
    client = TestClient(App(config))
    assert client.get("/health").json() == {"status": "ok"}
    preflight = client.options(
        "/",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_provider_args_reach_litellm(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    monkeypatch.setattr(
        "a2ui_agent_app._app.LiteLlm", lambda **kwargs: captured.update(kwargs) or FakeLlm()
    )
    llm = {**LLM, "provider_args": {**LLM["provider_args"], "timeout": 5}}
    App(BackendConfig(_env_file=None, llm=llm, generate_content={"temperature": 0.1}))
    assert captured == {
        "model": "azure/test-deployment",
        **LLM["provider_args"],
        "timeout": 5,
        "num_retries": 3,
    }


@pytest.mark.parametrize("missing", ["api_key", "api_base", "api_version"])
def test_missing_provider_args_fail_explicitly(missing: str):
    llm = {**LLM, "provider_args": {**LLM["provider_args"], missing: ""}}
    with pytest.raises(RuntimeError, match=missing):
        App(BackendConfig(_env_file=None, llm=llm))


def test_missing_catalog_fails_explicitly():
    with pytest.raises(RuntimeError, match="Cannot load A2UI catalog"):
        App(BackendConfig(_env_file=None, llm=LLM, a2ui_catalog_path="missing.json"))


def test_env_config_and_secret_masking(monkeypatch: pytest.MonkeyPatch):
    llm = {**LLM, "provider_args": {**LLM["provider_args"], "api_key": "test-secret"}}
    monkeypatch.setenv("LLM", json.dumps(llm))
    monkeypatch.setenv("GENERATE_CONTENT", '{"temperature": 0.2}')
    config = BackendConfig(_env_file=None)
    assert config.llm.provider_args["api_key"] == "test-secret"
    assert config.generate_content is not None and config.generate_content.temperature == 0.2
    assert "test-secret" not in repr(config)
    monkeypatch.delenv("LLM")
    with pytest.raises(ValidationError, match="llm"):
        BackendConfig(_env_file=None)
