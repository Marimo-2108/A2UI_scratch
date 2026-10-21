from typing import Protocol

from google.adk.agents.readonly_context import ReadonlyContext


class AgentContextProvider(Protocol):
    async def get_catalog_instructions(
        self,
        context: ReadonlyContext,
    ) -> str:
        """Get the A2UI format rules + catalog schema(s) the current client can render.

        Negotiated per request from the client's a2uiClientCapabilities, so it can differ
        between conversations (e.g. a client that sends its own inline catalog).
        """
        ...
