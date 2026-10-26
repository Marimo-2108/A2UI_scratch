"""Which models can my Azure OpenAI resource use?   uv run python tests/manual/list_models.py

Uses the LLM provider_args from .env. Prints model names only (never the key).
Note: these are the models available to the resource; LLM.model_name needs your *deployment* name.
"""

from openai import AzureOpenAI

from a2ui_agent_app.settings import Settings

settings = Settings()
settings.apply_truststore()
if settings.llm is None:
    raise SystemExit("LLM is not set (put it in Backend/.env, see .env.example).")

args = settings.llm.provider_args
client = AzureOpenAI(
    api_key=args.get("api_key"),
    azure_endpoint=args.get("api_base"),
    api_version=args.get("api_version"),
)
names = sorted(m.id for m in client.models.list())
print(f"azure: {len(names)} models")
for n in names:
    print(" ", n)
