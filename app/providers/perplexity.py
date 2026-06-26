"""Perplexity live search (OpenAI-compatible). Returns answer text; .citations
carries sources when present."""
import os


def configured() -> bool:
    return bool(os.getenv("PERPLEXITY_API_KEY"))


def chat(model: str, messages: list[dict], **kw) -> str:
    from openai import OpenAI  # lazy

    client = OpenAI(
        base_url="https://api.perplexity.ai",
        api_key=os.environ["PERPLEXITY_API_KEY"],
    )
    resp = client.chat.completions.create(model=model, messages=messages)
    text = resp.choices[0].message.content
    cites = getattr(resp, "citations", None)
    if cites:
        text += "\n\nSources:\n" + "\n".join(f"- {c}" for c in cites)
    return text
