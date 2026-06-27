"""Model factory for the ADK agents, with dual routing:

  local (no GCP)  -> Claude via LiteLlm + the direct Anthropic key; Nemotron via OpenRouter.
  prod (Vertex)   -> Claude via the ADK model registry on Vertex; Gemini native.

Set GOOGLE_GENAI_USE_VERTEXAI=true to switch Claude onto Vertex.
"""
import os

from google.adk.models.lite_llm import LiteLlm

_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")

CLAUDE_OPUS = os.getenv("CLAUDE_MODEL_OPUS", "claude-opus-4-8")
CLAUDE_SONNET = os.getenv("CLAUDE_MODEL_SONNET", "claude-sonnet-4-6")
CLAUDE_VERTEX = os.getenv("CLAUDE_VERTEX_MODEL", "claude-sonnet-4@20250514")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

_registered = False


def _register_vertex_claude():
    global _registered
    if _registered:
        return
    from google.adk.models.anthropic_llm import Claude
    from google.adk.models.registry import LLMRegistry

    LLMRegistry.register(Claude)
    _registered = True


def claude(tier: str = "opus"):
    """Claude model for an LlmAgent: a Vertex model string in prod, a LiteLlm
    (direct Anthropic key) locally."""
    if _VERTEX:
        _register_vertex_claude()
        return CLAUDE_VERTEX
    model = CLAUDE_OPUS if tier == "opus" else CLAUDE_SONNET
    return LiteLlm(model=f"anthropic/{model}", api_key=os.getenv("ANTHROPIC_API_KEY"))


def gemini():
    """Native Gemini; ADK resolves it against Vertex or an AI Studio key."""
    return GEMINI_MODEL


def nemotron():
    """Nemotron through OpenRouter via LiteLLM (rate caps applied on the agent)."""
    return LiteLlm(
        model=f"openrouter/{NEMOTRON_MODEL}",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        api_base="https://openrouter.ai/api/v1",
    )
