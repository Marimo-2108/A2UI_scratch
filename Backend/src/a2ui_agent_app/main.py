"""Run: uv run a2ui-agent"""

import logging
import sys

import uvicorn
from pydantic import ValidationError

from ._app import App
from ._config import BackendConfig


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    try:
        config = BackendConfig()
        app = App(config)
    except (ValidationError, RuntimeError) as e:
        sys.exit(f"Backend config error (check Backend/.env, see .env.example):\n{e}")
    uvicorn.run(app, host=config.agent_host, port=config.agent_port)


if __name__ == "__main__":
    main()
