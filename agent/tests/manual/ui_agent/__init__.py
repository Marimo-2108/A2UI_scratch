"""The UI agent on its own, for the ADK dev UI / CLI (no A2A server, no browser renderer):

    cd agent && uv run adk web tests/manual      # pick "ui_agent"
    cd agent && uv run adk run tests/manual/ui_agent

Replies are raw text with an <a2ui-json> block; validation/repair only happens in the server.
"""

from google.adk.agents.readonly_context import ReadonlyContext

from a2ui_agent_app import AgentContextProvider
from a2ui_agent_app.a2ui_ext import BASIC_CATALOG_ID, PROTOCOL_VERSION
from a2ui_agent_app.agents import UiAgent
from a2ui_agent_app.server import Settings, make_generator


class MockContextProvider(AgentContextProvider):
    """Pretends every client supports just the basic catalog."""

    def __init__(self) -> None:
        caps = {PROTOCOL_VERSION: {"supportedCatalogIds": [BASIC_CATALOG_ID]}}
        self._prompt = str(make_generator().create_processor(caps).prompt_snippet)

    async def get_catalog_instructions(
        self,
        context: ReadonlyContext,
    ) -> str:
        return self._prompt


_settings = Settings()
_settings.apply_truststore()


root_agent = UiAgent(
    config=_settings.to_agent_config(),
    context_provider=MockContextProvider(),
)
