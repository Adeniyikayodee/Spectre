"""Anthropic Claude — POST api.anthropic.com/v1/messages."""
import os


def configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def chat(model: str, messages: list[dict], max_tokens: int = 1500, **kw) -> str:
    from anthropic import Anthropic  # lazy

    system = " ".join(m["content"] for m in messages if m["role"] == "system") or None
    convo = [m for m in messages if m["role"] != "system"]
    client = Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=convo
    )
    return resp.content[0].text
