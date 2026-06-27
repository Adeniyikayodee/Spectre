"""Provider readiness check. Prints which integrations are configured, and with
--live actually pings each configured provider with a 1-token call.

    python -m app.scripts.smoke          # config only (free, instant)
    python -m app.scripts.smoke --live   # real ping of configured providers
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from app import graph, store  # noqa: E402
from app.providers import claude, gemini, nemotron, perplexity  # noqa: E402
from app.router import call  # noqa: E402

PROVIDERS = [
    ("claude (Anthropic)", claude, "intake"),
    ("gemini (Vertex/AI Studio)", gemini, "judge_uk"),
    ("nemotron (NVIDIA/OpenRouter)", nemotron, "advocate_opp"),
    ("perplexity", perplexity, "research"),
]
DATA = [
    ("neo4j (Aura)", graph),
    ("bigquery", store),  # store.save_case is always available; configured via GCP_PROJECT
]


def main() -> int:
    live = "--live" in sys.argv
    print(f"{'integration':28} {'status':14} {'live' if live else ''}")
    print("-" * 52)

    failures = 0
    for name, mod, role in PROVIDERS:
        ok = mod.configured()
        status = "configured" if ok else "MISSING ENV"
        result = ""
        if live and ok:
            try:
                call(role, [{"role": "user", "content": "Reply with: ok"}], max_tokens=5)
                result = "ping OK"
            except Exception as e:
                result = f"FAIL {type(e).__name__}"
                failures += 1
        print(f"{name:28} {status:14} {result}")

    import os
    for name, _mod in DATA:
        env = "NEO4J_URI" if "neo4j" in name else "GCP_PROJECT"
        ok = bool(os.getenv(env))
        print(f"{name:28} {'configured' if ok else 'MISSING ENV':14}")

    print("-" * 52)
    print("App runs regardless — unconfigured providers degrade to clear stubs.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
