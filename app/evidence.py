"""The evidence layer: build the pleading-to-proof matrix from the real bundle.

Two agents, both Claude:
  extract_propositions  reads the pleadings and pulls each pleaded proposition
                        with the legal element it must prove.
  map_evidence          links each proposition to supporting and adverse passages,
                        sets a status and a confidence, and flags contradictions and gaps.

Grounding rule: the mapping agent may only cite candidate passages we hand it, by
number. We resolve those numbers back to the real (document, paragraph) and copy the
verbatim quote from the bundle. A number it invents that is not in the list is dropped,
so no citation can be fabricated.
"""
import json
import re

from . import agents, bundle

EXTRACT_SYS = (
    "You read litigation pleadings and extract the pleaded propositions. For each, give "
    "the proposition in plain words, the party asserting it, and the single legal element "
    "it must prove. Stay close to the pleaded words. Return ONLY a JSON list of objects "
    'with keys "text", "party", "legal_element".'
)

MAP_SYS = (
    "You map one pleaded proposition to the evidence. You are given numbered candidate "
    "passages. Decide a status: supported (evidence proves it), adverse (evidence cuts "
    "against it), neutral (mixed or weak), or missing (no relevant passage). Cite ONLY the "
    "candidate numbers given; never invent a citation. Return ONLY a JSON object with keys "
    '"status", "confidence" (0 to 1), "supporting" (list of candidate numbers), "adverse" '
    '(list of candidate numbers), "contradiction" (short note or empty), "gap" (what further '
    "witness, expert, or document is needed, or null)."
)


def build_matrix(case: dict, limit: int = 5) -> dict:
    """Read the bundle, extract a handful of propositions, map each to evidence."""
    docs = bundle.read_bundle()
    propositions = extract_propositions(bundle.pleadings_text(docs), limit)
    evidence = bundle.evidence_passages(docs)
    cells = [_map_one(p, i, evidence, docs) for i, p in enumerate(propositions)]
    return {
        "case_id": case.get("case_id"),
        "built_from": str(bundle.bundle_dir()),
        "documents": [d["name"] for d in docs],
        "propositions": cells,
    }


def extract_propositions(pleadings_text: str, limit: int) -> list[dict]:
    raw = agents.ask("evidence_extract", EXTRACT_SYS,
                     f"Pleadings:\n{pleadings_text[:12000]}\n\nExtract up to {limit} propositions.")
    items = _json(raw, default=[])
    out = []
    for it in items[:limit]:
        if isinstance(it, dict) and it.get("text"):
            out.append({"text": it["text"], "party": it.get("party", "claimant"),
                        "legal_element": it.get("legal_element", "")})
    return out


def _map_one(prop: dict, index: int, evidence: list[dict], docs: list[dict]) -> dict:
    """Map a single proposition. Pre-filter to the most relevant passages (cheap keyword
    overlap), then ask the mapping agent to judge and cite from only those."""
    candidates = _prefilter(prop, evidence, k=12)
    base = {"id": f"P{index + 1}", "text": prop["text"], "party": prop["party"],
            "legal_element": prop["legal_element"]}
    if not candidates:  # no plausibly relevant evidence: a gap, no model call needed
        return {**base, "status": "missing", "confidence": 0.0, "sources": [],
                "contradictions": [], "gap": "No supporting evidence found in the bundle."}

    digest = "\n".join(f"[{n + 1}] {c['doc']} para {c['para']}: {c['text']}"
                       for n, c in enumerate(candidates))
    raw = agents.ask("evidence_map", MAP_SYS,
                     f"Proposition ({prop['party']}): {prop['text']}\n"
                     f"Legal element: {prop['legal_element']}\n\nCandidate passages:\n{digest}")
    cell = _json(raw, default={})
    sources = (_resolve(cell.get("supporting"), candidates, docs, "supporting")
               + _resolve(cell.get("adverse"), candidates, docs, "adverse"))
    contradiction = cell.get("contradiction")
    return {
        **base,
        "status": cell.get("status", "neutral"),
        "confidence": cell.get("confidence"),
        "sources": sources,
        "contradictions": [contradiction] if contradiction else [],
        "gap": cell.get("gap"),
    }


def _prefilter(prop: dict, evidence: list[dict], k: int) -> list[dict]:
    """Top-k evidence passages by keyword overlap with the proposition (a cheap retrieval;
    embeddings would be more thorough, noted as an assumption)."""
    words = {w for w in _norm(f"{prop['text']} {prop['legal_element']}").split() if len(w) > 3}
    scored = []
    for e in evidence:
        score = sum(1 for w in words if w in _norm(e["text"] + " " + e["doc"]))
        if score:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:k]]


def _resolve(numbers, candidates: list[dict], docs: list[dict], kind: str) -> list[dict]:
    """Turn candidate numbers into real source links, dropping any out-of-range number."""
    out = []
    for num in numbers or []:
        try:
            cand = candidates[int(num) - 1]
        except (ValueError, TypeError, IndexError):
            continue
        out.append({"doc": cand["doc"], "para": cand["para"], "kind": kind,
                    "quote": bundle.get_passage(docs, cand["doc"], cand["para"])})
    return out


def _json(raw: str, default):
    """Pull the first JSON value out of a model response, defensively."""
    try:
        match = re.search(r"(\[.*\]|\{.*\})", raw, re.S)
        return json.loads(match.group()) if match else default
    except Exception:
        return default


def _norm(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in (s or ""))
