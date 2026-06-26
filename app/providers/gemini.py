"""Google Gemini via Vertex AI. Auth = Application Default Credentials
(gcloud auth application-default login locally; service account on Cloud Run).
No API key — presence of GCP_PROJECT means 'configured'."""
import os


def configured() -> bool:
    return bool(os.getenv("GCP_PROJECT"))


def chat(model: str, messages: list[dict], **kw) -> str:
    from google import genai  # lazy

    client = genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT"],
        location=os.getenv("GCP_REGION", "us-central1"),
    )
    prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return client.models.generate_content(model=model, contents=prompt).text
