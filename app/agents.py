"""Thin prompt wrappers over the router. ask() degrades to a clearly-marked
stub when a provider isn't configured, so the whole pipeline runs with zero keys."""
from .router import call


def ask(role: str, system: str, user: str, **kw) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        return call(role, messages, **kw)
    except Exception as e:  # ProviderNotConfigured, RateLimited, network, etc.
        return f"[stub:{role}] model not called ({type(e).__name__}: {e})"
