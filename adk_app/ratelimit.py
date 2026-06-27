"""Nemotron rate guard as an ADK before_model_callback (50/day, 20/min).
Returning an LlmResponse short-circuits the model call; returning None proceeds."""
import os
import threading
import time

_lock = threading.Lock()
_calls: list[float] = []


def nemotron_rate_guard(callback_context, llm_request):
    day = int(os.getenv("NEMOTRON_DAILY_CAP", "50"))
    minute = int(os.getenv("NEMOTRON_MINUTE_CAP", "20"))
    now = time.time()
    with _lock:
        global _calls
        _calls = [t for t in _calls if now - t < 86_400]
        over = (sum(1 for t in _calls if now - t < 60) >= minute) or (len(_calls) >= day)
        if over:
            from google.adk.models.llm_response import LlmResponse
            from google.genai import types

            return LlmResponse(content=types.Content(
                role="model",
                parts=[types.Part(text="[rate-limited: Nemotron cap reached]")],
            ))
        _calls.append(now)
    return None
