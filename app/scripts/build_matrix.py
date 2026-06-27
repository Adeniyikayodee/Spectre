"""Verification runner for Stage 1: build the pleading-to-proof matrix from the real
witness statement folder and print each proposition with its status, confidence, and
the exact (document, paragraph) it cites.

    python -m app.scripts.build_matrix          # default: 5 propositions
    python -m app.scripts.build_matrix 4        # choose how many

Reviewers can run this to confirm the matrix is built from the real files and every
status links to a real document and paragraph.
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from app import bundle, evidence  # noqa: E402


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    docs = bundle.read_bundle()
    print(f"bundle: {bundle.bundle_dir()}")
    print(f"documents read: {len(docs)} ({sum(len(d['passages']) for d in docs)} passages)\n")

    matrix = evidence.build_matrix({"case_id": "verify"}, limit=limit)
    for p in matrix["propositions"]:
        print(f"[{p['id']}] {p['status'].upper():9} conf={p['confidence']}  {p['text'][:80]}")
        print(f"      element: {p['legal_element'][:80]}")
        for s in p["sources"]:
            quote = (s.get("quote") or "")[:90].replace("\n", " ")
            print(f"      - {s['kind']:10} {s['doc']} para {s['para']}: \"{quote}\"")
        if p.get("gap"):
            print(f"      gap: {p['gap']}")
        if p.get("contradictions"):
            print(f"      contradiction: {p['contradictions'][0]}")
        print()

    cited = sum(1 for p in matrix["propositions"] if p["sources"])
    print(f"propositions: {len(matrix['propositions'])} | with a real source link: {cited}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
