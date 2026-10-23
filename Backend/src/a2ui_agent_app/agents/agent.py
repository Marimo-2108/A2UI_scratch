"""Build the ADK agent. The host supplies the catalog instruction for the current request."""

from pathlib import Path

from google import genai
from google.adk.agents.llm_agent import InstructionProvider, LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .config import AgentConfig


def create_agent(config: AgentConfig, instruction: InstructionProvider) -> LlmAgent:
    model: BaseLlm
    generate_content = None

    if config.llm_provider == "gemini":
        if not config.gemini_api_key.get_secret_value():
            raise RuntimeError("GEMINI_API_KEY is not set (put it in Backend/.env).")
        model = Gemini(
            model=config.gemini_model,
            client=genai.Client(
                api_key=config.gemini_api_key.get_secret_value(),
                http_options=types.HttpOptions(
                    timeout=config.llm_timeout_s * 1000,
                    retry_options=types.HttpRetryOptions(
                        attempts=3,
                        initial_delay=1.5,
                        max_delay=20,
                        http_status_codes=[429, 500, 502, 503, 504],
                    ),
                ),
            ),
        )
        generate_content = types.GenerateContentConfig(
            temperature=config.gemini_temperature,
            thinking_config=types.ThinkingConfig(thinking_level=config.gemini_thinking_level),
        )
    else:
        if not config.openai_api_key.get_secret_value():
            raise RuntimeError("OPENAI_API_KEY is not set (put it in Backend/.env).")
        if not config.openai_model:
            raise RuntimeError("OPENAI_MODEL is not set (put it in Backend/.env).")
        if config.openai_reasoning_effort:
            # Reasoning models reject custom temperature; send effort instead.
            model = LiteLlm(
                model=f"openai/{config.openai_model}",
                api_key=config.openai_api_key.get_secret_value(),
                timeout=config.llm_timeout_s,
                num_retries=3,
                reasoning_effort=config.openai_reasoning_effort,
            )
        else:
            model = LiteLlm(
                model=f"openai/{config.openai_model}",
                api_key=config.openai_api_key.get_secret_value(),
                timeout=config.llm_timeout_s,
                num_retries=3,
            )
            generate_content = types.GenerateContentConfig(temperature=config.gemini_temperature)

    return LlmAgent(
        name="ui_agent",
        description="Answers with agent-driven user interfaces (A2UI) instead of plain text.",
        model=model,
        instruction=instruction,
        static_instruction=Path(__file__).with_name("system-prompt.txt").read_text(encoding="utf-8"),
        generate_content_config=generate_content,
    )
