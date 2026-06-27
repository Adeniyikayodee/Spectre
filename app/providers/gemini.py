"""Google Gemini. Uses Vertex AI when GCP_PROJECT is set (ADC auth), otherwise the
AI Studio API key in GOOGLE_API_KEY."""
import os


def configured() -> bool:
    return bool(os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_API_KEY"))


def chat(model: str, messages: list[dict], **kw) -> str:
    from google import genai  # lazy

    if os.getenv("GCP_PROJECT"):  # Vertex AI (prod)
        client = genai.Client(
            vertexai=True,
            project=os.environ["GCP_PROJECT"],
            location=os.getenv("GCP_REGION", "us-central1"),
        )
    else:  # AI Studio API key (local)
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return client.models.generate_content(model=model, contents=prompt).text
