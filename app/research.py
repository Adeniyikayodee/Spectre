"""Authorities for an issue. Prefers a hand-checked seed set (truthful, instant, no
spend); falls back to Perplexity live retrieval for non-seeded issues. Cellar (EU)
serves legislation."""
import copy
import json
import os

from . import agents

_SEEDS: list[dict] = []


def configured() -> bool:
    return bool(os.getenv("PERPLEXITY_API_KEY"))


def _seeded(issue: str) -> list[dict] | None:
    """Hand-checked authorities matched to the issue by keyword; a deep copy so the
    pipeline can annotate without mutating the shared seed."""
    global _SEEDS
    if not _SEEDS:
        path = os.path.join(os.path.dirname(__file__), "fixtures", "authorities.json")
        try:
            with open(path) as f:
                _SEEDS = json.load(f).get("seeds", [])
        except Exception:
            _SEEDS = []
    low = issue.lower()
    for seed in _SEEDS:
        if seed["when"].lower() in low:
            return copy.deepcopy(seed["authorities"])
    return None


def find_authorities(issue: str, jurisdictions: list[str]) -> list[dict]:
    """Up to 3 analogous authorities for an issue, each {name, cite, point}."""
    seeded = _seeded(issue)
    if seeded:
        return seeded
    if not configured():
        return [{"name": None, "cite": "(set PERPLEXITY_API_KEY for live authorities)",
                 "point": None}]
    juris = ", ".join(jurisdictions)
    raw = agents.ask(
        "research",
        "You are a legal precedent researcher. Real, citable cases only.",
        f"Up to 3 leading authorities on this issue: {issue}. Jurisdictions: {juris}. "
        f"Return ONE per line as: NAME | CITATION | the single point it decided. No preamble.",
    )
    out = []
    for line in raw.splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0]:
            out.append({"name": parts[0], "cite": parts[1],
                        "point": parts[2] if len(parts) > 2 else None})
    return out[:3] or [{"name": None, "cite": raw[:200], "point": None}]


def cellar_sparql(query: str) -> dict:
    """EU Publications Office SPARQL (no auth). Legislation layer only — UK/US/NG
    case law comes from Perplexity, not Cellar."""
    import httpx

    resp = httpx.post(
        "http://publications.europa.eu/webapi/rdf/sparql",
        data={"query": query, "format": "application/sparql-results+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cellar_search(issue: str, limit: int = 4) -> list[dict]:
    """Search the EU Cellar SPARQL endpoint for EU legal texts whose English title
    contains a keyword from the issue (falling back to 'contract'). Best-effort:
    returns [] on timeout or error. This is the EU legislation layer that the EU judge
    consults; UK/US/Nigeria case law still comes from Perplexity."""
    for kw in _cellar_keywords(issue):
        titles = _cellar_query(kw, limit)
        if titles:
            return [{"title": t, "matched": kw, "source": "Cellar (EU Publications Office)"}
                    for t in titles]
    return []


_CELLAR_STOP = {"whether", "against", "between", "concerning", "regarding", "applicable",
                "relating", "pursuant", "claimant", "defendant", "contract"}


def _cellar_keywords(text: str) -> list[str]:
    words = [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split()
             if len(w) > 5 and w not in _CELLAR_STOP]
    return (words[:1] or []) + ["contract"]  # one topical issue keyword, then a reliable fallback


def _cellar_query(keyword: str, limit: int) -> list[str]:
    import httpx

    sparql = (
        'PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> '
        'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> '
        'SELECT DISTINCT ?title WHERE { '
        '?work cdm:work_date_document ?d . FILTER(?d >= "2015-01-01"^^xsd:date) '
        '?exp cdm:expression_belongs_to_work ?work ; '
        'cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ; '
        'cdm:expression_title ?title . '
        f'FILTER(CONTAINS(LCASE(STR(?title)), "{keyword}")) }} LIMIT {limit}'
    )
    try:
        r = httpx.get("https://publications.europa.eu/webapi/rdf/sparql",
                      params={"query": sparql, "format": "application/sparql-results+json"},
                      timeout=25)
        return [b["title"]["value"] for b in r.json().get("results", {}).get("bindings", [])]
    except Exception:
        return []
