from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext


class CatalogContextProvider:
    """AgentContextProvider backed by the A2UI processor negotiated for each conversation.

    The brain registers a processor per ADK session (= A2A contextId) before running the agent;
    the agent's instruction provider then asks for that session's catalog prompt.
    """

    def __init__(self) -> None:
        self._processors: dict[str, Any] = {}

    def set_processor(self, session_id: str, processor: Any) -> None:
        self._processors[session_id] = processor

    async def get_catalog_instructions(self, context: ReadonlyContext) -> str:
        processor = self._processors.get(context.session.id)
        if processor is None:
            raise RuntimeError(f"No A2UI catalog negotiated for session {context.session.id!r}.")
        return str(processor.prompt_snippet)
