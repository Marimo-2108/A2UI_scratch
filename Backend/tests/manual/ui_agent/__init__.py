"""The UI agent on its own, for the ADK dev UI / CLI (no A2A server, no browser renderer):

    cd Backend && uv run adk web tests/manual      # pick "ui_agent"
    cd Backend && uv run adk run tests/manual/ui_agent

Replies are raw text with an <a2ui-json> block; validation/repair only happens in the server.
"""

from google.adk.agents.readonly_context import ReadonlyContext

from a2ui_agent_app.a2ui import BASIC_CATALOG_ID, PROTOCOL_VERSION, make_generator
from a2ui_agent_app.agents import create_agent
from a2ui_agent_app.settings import Settings

_caps = {PROTOCOL_VERSION: {"supportedCatalogIds": [BASIC_CATALOG_ID]}}
_prompt = str(make_generator().create_processor(_caps).prompt_snippet)


async def catalog_instruction(context: ReadonlyContext) -> str:
    return _prompt


_settings = Settings()
_settings.apply_truststore()


root_agent = create_agent(_settings, catalog_instruction)
