"""Which models can my API key use?   uv run python list_models.py [openai|gemini]

Prints model names only (never the key). Useful because vendors retire/rename models often.
"""

import sys

from config import settings


def openai_models() -> list[str]:
    from openai import OpenAI

    return sorted(m.id for m in OpenAI(api_key=settings.openai_api_key).models.list())


def gemini_models() -> list[str]:
    from google import genai

    c = genai.Client(api_key=settings.gemini_api_key)
    return sorted(m.name.split("/")[-1] for m in c.models.list())


which = sys.argv[1] if len(sys.argv) > 1 else settings.llm_provider
names = openai_models() if which == "openai" else gemini_models()
print(f"{which}: {len(names)} models")
for n in names:
    print(" ", n)
