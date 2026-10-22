"""Server settings; inherits the agent settings so both read the same .env."""

from pydantic import model_validator

from .agents.config import AgentConfig


class Settings(AgentConfig):
    agent_host: str = "localhost"
    # The dev container binds to 0.0.0.0, while the advertised URL still uses agent_host.
    agent_bind_host: str = ""
    agent_port: int = 10010
    web_origin_regex: str = r"http://localhost:\d+"
    use_system_truststore: bool = True

    @model_validator(mode="after")
    def _default_bind_host(self) -> "Settings":
        self.agent_bind_host = self.agent_bind_host or self.agent_host
        return self

    def apply_truststore(self) -> None:
        """Trust the OS certificate store, including corporate certificates; keep TLS verified."""
        if self.use_system_truststore:
            import truststore

            truststore.inject_into_ssl()
