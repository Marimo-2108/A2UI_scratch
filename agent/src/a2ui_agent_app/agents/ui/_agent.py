"""The UI Agent: answers every message with a small A2UI user interface."""

from google import genai
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types as genai_types

from a2ui_agent_app._protocol import AgentContextProvider
from a2ui_agent_app.agents._config import AgentConfig, GeminiConfig

from ._instruction_provider import UiInstructionProvider
from ._static_instructions import build_static_instructions

_AGENT_DESCRIPTION = """
Answers with agent-driven user interfaces (A2UI) instead of plain text.
""".strip()


def _make_gemini(config: GeminiConfig) -> Gemini:
    # 429 / 5xx ("high demand") are retried with exponential backoff.
    client = genai.Client(
        api_key=config.api_key.get_secret_value(),
        http_options=genai_types.HttpOptions(
            timeout=config.timeout_s * 1000,  # milliseconds, applies to each attempt
            retry_options=genai_types.HttpRetryOptions(
                attempts=3,
                initial_delay=1.5,
                max_delay=20,
                http_status_codes=[429, 500, 502, 503, 504],
            ),
        ),
    )
    return Gemini(model=config.model_name, client=client)


class UiAgent(LlmAgent):
    def __init__(
        self,
        context_provider: AgentContextProvider,
        config: AgentConfig,
    ) -> None:

        self._instruction_provider = UiInstructionProvider(context_provider)

        self._model: BaseLlm

        # based on the config let's figure out the model
        if config.gemini is not None:
            self._model = _make_gemini(config.gemini)
        elif config.lite_llm is not None:
            self._model = LiteLlm(
                model=config.lite_llm.model_name,
                **config.lite_llm.to_litellm_kwargs(),
            )
        else:
            raise ValueError("Invalid config: no LLM provider specified.")

        super().__init__(
            name="ui_agent",
            description=_AGENT_DESCRIPTION,
            model=self._model,
            instruction=self._instruction_provider,
            static_instruction=build_static_instructions(),
            generate_content_config=config.generate_content,
        )
