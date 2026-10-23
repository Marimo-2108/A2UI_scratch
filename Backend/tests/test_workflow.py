"""Exercise the real ADK/A2UI/A2A path with a fake model; no keys or network calls."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from a2ui.core.exceptions import A2uiCatalogError, A2uiValidationError
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr, ValidationError
from starlette.testclient import TestClient

from a2ui_agent_app.a2ui import BASIC_CATALOG_ID, EXTENSION_URI, action_to_text
from a2ui_agent_app.agents import AgentConfig, create_agent
from a2ui_agent_app.runner import UiRunner, catalog_instruction
from a2ui_agent_app.server import build_app
from a2ui_agent_app.settings import Settings

CAPS = {"v0.9": {"supportedCatalogIds": [BASIC_CATALOG_ID]}}


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
        llm_provider="openai",
        openai_api_key="test-key",
        openai_model="test-model",
        openai_reasoning_effort="",
        gemini_max_retries=1,
        use_system_truststore=False,
    )


async def collect(runner: UiRunner, context: str, text: str, caps: dict):
    return [part.model_dump() async for part in runner.respond(context, text, caps)]


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
    assert any("retrying 1/1" in p.get("text", "") for p in first)
    assert any("createSurface" in p.get("data", {}) for p in first)
    assert not any("createSurface" in p.get("data", {}) for p in followup)
    assert any("updateComponents" in p.get("data", {}) for p in followup)
    assert any("createSurface" in p.get("data", {}) for p in other)
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


def test_a2a_endpoint_streams_ui_and_rejects_missing_extension(model: FakeLlm, settings: Settings):
    model._outputs = [ui_output()]
    body = {
        "jsonrpc": "2.0",
        "id": "test",
        "method": "message/stream",
        "params": {
            "message": {
                "kind": "message",
                "messageId": "test",
                "role": "user",
                "parts": [{"kind": "text", "text": "a form"}],
                "metadata": {"a2uiClientCapabilities": CAPS},
            }
        },
    }
    with TestClient(build_app(settings)) as client:
        assert client.get("/.well-known/agent-card.json").json()["skills"][0]["id"] == "generate_ui"
        response = client.post("/", json=body, headers={"X-A2A-Extensions": EXTENSION_URI})
        assert response.status_code == 200
        assert '"createSurface"' in response.text
        assert '"input-required"' in response.text
        response = client.post("/", json=body)
        assert "I only speak A2UI" in response.text
    assert len(model._requests) == 1


@pytest.mark.parametrize(
    ("provider", "missing", "message"),
    [
        ("gemini", {"gemini_api_key": ""}, "GEMINI_API_KEY"),
        ("openai", {"openai_api_key": ""}, "OPENAI_API_KEY"),
        ("openai", {"openai_model": ""}, "OPENAI_MODEL"),
    ],
)
def test_missing_credentials_fail_explicitly(provider: str, missing: dict, message: str):
    config = AgentConfig(
        _env_file=None,
        **{
            "llm_provider": provider,
            "gemini_api_key": "test-key",
            "openai_api_key": "test-key",
            "openai_model": "test-model",
            **missing,
        },
    )
    with pytest.raises(RuntimeError, match=message):
        create_agent(config, catalog_instruction)


def test_existing_env_names_and_secret_masking(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "OPENAI")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "low")
    monkeypatch.setenv("AGENT_HOST", "example.local")
    monkeypatch.delenv("AGENT_BIND_HOST", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "openai"
    assert settings.gemini_thinking_level == "LOW"
    assert settings.agent_bind_host == "example.local"
    assert "test-secret" not in repr(settings)
    with pytest.raises(ValidationError, match="llm_provider"):
        Settings(_env_file=None, llm_provider="unknown")
