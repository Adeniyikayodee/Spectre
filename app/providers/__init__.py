"""Model provider adapters. Each exposes:
    configured() -> bool          # is the key/env present?
    chat(model, messages) -> str  # normalize provider call to text in / text out
All SDK imports are lazy so the app runs with none of them installed.
"""
