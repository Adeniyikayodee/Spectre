"""NVIDIA Nemotron. Both NVIDIA's own endpoint and OpenRouter are OpenAI-compatible,
so one adapter serves either — whichever key you receive lights it up:
  NVIDIA_API_KEY      -> https://integrate.api.nvidia.com/v1   (direct access)
  OPENROUTER_API_KEY  -> https://openrouter.ai/api/v1          (fallback)
Set NEMOTRON_MODEL to the exact slug NVIDIA gives you (router defaults it)."""
import os


def _backend() -> tuple[str, str] | None:
    if os.getenv("NVIDIA_API_KEY"):
        return "https://integrate.api.nvidia.com/v1", os.environ["NVIDIA_API_KEY"]
    if os.getenv("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1", os.environ["OPENROUTER_API_KEY"]
    return None


def configured() -> bool:
    return _backend() is not None


def chat(model: str, messages: list[dict], **kw) -> str:
    from openai import OpenAI  # lazy

    base_url, api_key = _backend()
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(model=model, messages=messages, **kw)
    return resp.choices[0].message.content
