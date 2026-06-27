"""The only seam to models. call(role, messages) -> str.
Swap a model = edit one line in ROLES."""
import hashlib
import os
import threading
import time

from .providers import claude, gemini, nemotron, perplexity


class ProviderNotConfigured(Exception):
    """Key/env missing for the provider that serves this role."""


class RateLimited(Exception):
    """Nemotron cap hit (50/day, 20/min)."""


# Exact Nemotron slug — override with the one NVIDIA gives you, no code change:
#   export NEMOTRON_MODEL=nvidia/...   (works on both NVIDIA direct and OpenRouter)
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

# role -> (provider, model). Opus for advocate/judge-US/appeal/strategist (depth),
# Sonnet for high-volume cheap roles, Gemini=UK judge, Nemotron=opponent+NG judge.
ROLES = {
    "intake":       ("claude",     "claude-sonnet-4-6"),
    "evidence_extract": ("claude", "claude-sonnet-4-6"),
    "evidence_map":     ("claude", "claude-sonnet-4-6"),
    "advocate_you": ("claude",     "claude-opus-4-8"),
    "advocate_opp": ("nemotron",   NEMOTRON_MODEL),
    "research":     ("perplexity", "sonar-pro"),
    "turning_point":("claude",     "claude-sonnet-4-6"),
    "judge_uk":     ("gemini",     "gemini-2.5-pro"),
    "judge_us":     ("claude",     "claude-opus-4-8"),
    "judge_ng":     ("nemotron",   NEMOTRON_MODEL),
    "referee":      ("claude",     "claude-sonnet-4-6"),
    "reflector":    ("claude",     "claude-sonnet-4-6"),
    "appeal":       ("claude",     "claude-opus-4-8"),
    "strategist":   ("claude",     "claude-opus-4-8"),
}

_PROVIDERS = {
    "claude": claude,
    "gemini": gemini,
    "nemotron": nemotron,   # NVIDIA direct (NVIDIA_API_KEY) or OpenRouter — auto-detected
    "perplexity": perplexity,
}

_cache: dict[str, str] = {}
_lock = threading.Lock()
_nemotron_calls: list[float] = []


def _rate_guard() -> None:
    day_cap = int(os.getenv("NEMOTRON_DAILY_CAP", "50"))
    min_cap = int(os.getenv("NEMOTRON_MINUTE_CAP", "20"))
    now = time.time()
    with _lock:
        global _nemotron_calls
        _nemotron_calls = [t for t in _nemotron_calls if now - t < 86_400]
        if sum(1 for t in _nemotron_calls if now - t < 60) >= min_cap:
            raise RateLimited("Nemotron minute cap")
        if len(_nemotron_calls) >= day_cap:
            raise RateLimited("Nemotron daily cap")
        _nemotron_calls.append(now)


def call(role: str, messages: list[dict], **kw) -> str:
    if role not in ROLES:
        raise KeyError(f"unknown role: {role}")
    provider, model = ROLES[role]
    mod = _PROVIDERS[provider]
    if not mod.configured():
        raise ProviderNotConfigured(f"{provider} not configured (role {role})")

    key = hashlib.sha256(f"{role}|{messages}".encode()).hexdigest()
    if key in _cache:                      # dodge repeat spend, protect Nemotron caps
        return _cache[key]
    if provider == "nemotron":
        _rate_guard()

    out = mod.chat(model, messages, **kw)
    _cache[key] = out
    return out


def provider_status() -> dict[str, bool]:
    return {name: mod.configured() for name, mod in _PROVIDERS.items()}
