from google.adk.agents.readonly_context import ReadonlyContext

from a2ui_agent_app._protocol import AgentContextProvider


class UiInstructionProvider:
    """Dynamic part of the prompt: the A2UI format + the catalog(s) negotiated for this request.

    Being a callable, ADK does not run `{state}` templating on it, so the JSON schema's braces
    are passed through untouched.
    """

    def __init__(self, context_provider: AgentContextProvider) -> None:
        self._context_provider = context_provider

    async def __call__(self, context: ReadonlyContext) -> str:
        return await self._context_provider.get_catalog_instructions(context)
