from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI

from ..agents import UiAgent


def register_ui_agent(ui_agent: UiAgent, app: FastAPI) -> None:
    ag_ui_agent = ADKAgent(
        adk_agent=ui_agent,
        app_name="a2ui_agent_app",
        user_id="a2ui-client",
        session_timeout_seconds=3600,
        use_in_memory_services=True,
    )

    add_adk_fastapi_endpoint(app, ag_ui_agent, path="/")
