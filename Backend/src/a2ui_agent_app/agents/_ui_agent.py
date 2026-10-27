from pathlib import Path

from a2ui.adk.send_a2ui_to_client_toolset import SendA2uiToClientToolset
from a2ui.core import CatalogApi
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types as genai_types


class UiAgent(LlmAgent):
    """Answers with A2UI. The toolset adds the catalog schema to the prompt, gives the model a
    `send_a2ui_json_to_client` tool, validates its JSON and returns errors to the model to fix."""

    def __init__(
        self,
        llm: LiteLlm,
        catalog: CatalogApi,
        generate_content_config: genai_types.GenerateContentConfig | None = None,
    ) -> None:
        super().__init__(
            name="ui_agent",
            description="Answers with agent-driven user interfaces (A2UI) instead of plain text.",
            model=llm,
            static_instruction=(Path(__file__).parent / "system-prompt.txt").read_text(encoding="utf-8"),
            tools=[SendA2uiToClientToolset(a2ui_enabled=True, a2ui_catalog=catalog, a2ui_examples="")],
            generate_content_config=generate_content_config,
        )
