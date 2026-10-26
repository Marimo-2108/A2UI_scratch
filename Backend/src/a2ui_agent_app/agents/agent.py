"""Build the ADK agent. The host supplies the catalog instruction for the current request."""

from pathlib import Path

from google.adk.agents.llm_agent import InstructionProvider, LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .config import AgentConfig

_REQUIRED_PROVIDER_ARGS = ("api_key", "api_base", "api_version")
# A stalled model fails with a clear error instead of hanging; override in provider_args.
_DEFAULT_PROVIDER_ARGS = {"timeout": 60, "num_retries": 3}


def create_agent(config: AgentConfig, instruction: InstructionProvider) -> LlmAgent:
    if config.llm is None:
        raise RuntimeError("LLM is not set (put it in Backend/.env, see .env.example).")
    missing = [k for k in _REQUIRED_PROVIDER_ARGS if not config.llm.provider_args.get(k)]
    if missing:
        raise RuntimeError(f"LLM provider_args is missing {', '.join(missing)} (set it in Backend/.env).")

    model = LiteLlm(
        model=config.llm.model_name,
        **{**_DEFAULT_PROVIDER_ARGS, **config.llm.provider_args},
    )

    return LlmAgent(
        name="ui_agent",
        description="Answers with agent-driven user interfaces (A2UI) instead of plain text.",
        model=model,
        instruction=instruction,
        static_instruction=Path(__file__).with_name("system-prompt.txt").read_text(encoding="utf-8"),
        generate_content_config=config.generate_content,
    )
