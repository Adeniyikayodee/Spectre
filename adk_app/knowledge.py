"""The three knowledge bases as ADK tools, reusing the verified logic in app/.
Experience persists to BigQuery when GCP_PROJECT is set (prod), else SQLite (local).
ADK reads each tool's signature and docstring to build its schema."""
import os

from app import experience as _sqlite_exp
from app import research


def find_cases(issue: str, jurisdictions: list[str]) -> dict:
    """Find analogous case-law authorities for a legal issue across jurisdictions.

    Args:
        issue: the legal issue to research.
        jurisdictions: e.g. ["UK", "US", "Nigeria"].

    Returns:
        A dict with key 'authorities': a list of {name, cite, point}.
    """
    return {"authorities": research.find_authorities(issue, jurisdictions)}


def find_regulations(query: str) -> dict:
    """Look up EU legislation via the Cellar SPARQL endpoint (legislation layer only).

    Args:
        query: a SPARQL query string.

    Returns:
        A dict with 'results', or a 'note' if Cellar is unavailable.
    """
    try:
        return {"results": research.cellar_sparql(query)}
    except Exception as e:
        return {"note": f"Cellar unavailable ({e}); EU legislation only, not case law."}


def recall_experience(query: str) -> dict:
    """Retrieve lessons from past trials relevant to the query (the experience base).

    Args:
        query: the issue or topic to find prior lessons for.

    Returns:
        A dict with 'lessons': a list of prior reflections.
    """
    if os.getenv("GCP_PROJECT"):
        rows = _bq_search(query)
        if rows is not None:
            return {"lessons": rows}
    return {"lessons": _sqlite_exp.search(query, limit=3)}


def remember_experience(case_id: str, side: str, issue: str, lesson: str) -> dict:
    """File a post-trial reflection into the experience base so future cases reuse it.

    Args:
        case_id: the case identifier.
        side: which side the lesson is for.
        issue: the issue it relates to.
        lesson: the reflection text.

    Returns:
        A dict with 'status'.
    """
    _sqlite_exp.add(case_id, side, issue, "self_reflection", lesson, issue)
    if os.getenv("GCP_PROJECT"):
        _bq_add(case_id, side, issue, lesson)
    return {"status": "written"}


# --- BigQuery backend (guarded; no-op without GCP) ---------------------------
_bq = None
_bq_init = False


def _client():
    global _bq, _bq_init
    if _bq_init:
        return _bq
    _bq_init = True
    try:
        from google.cloud import bigquery

        c = bigquery.Client()
        ds = os.getenv("BQ_DATASET", "litigation")
        c.create_dataset(ds, exists_ok=True)
        c.query(
            f"CREATE TABLE IF NOT EXISTS `{c.project}.{ds}.experience` "
            "(case_id STRING, side STRING, issue STRING, lesson STRING, ts TIMESTAMP)"
        ).result()
        _bq = (c, ds)
    except Exception:
        _bq = None
    return _bq


def _bq_add(case_id, side, issue, lesson):
    bundle = _client()
    if not bundle:
        return
    from datetime import datetime, timezone

    c, ds = bundle
    try:
        c.insert_rows_json(f"{c.project}.{ds}.experience", [{
            "case_id": case_id, "side": side, "issue": issue, "lesson": lesson,
            "ts": datetime.now(timezone.utc).isoformat(),
        }])
    except Exception:
        pass


def _bq_search(query):
    bundle = _client()
    if not bundle:
        return None
    c, ds = bundle
    try:
        rows = c.query(
            f"SELECT side, issue, lesson FROM `{c.project}.{ds}.experience` "
            "ORDER BY ts DESC LIMIT 50"
        ).result()
        words = [w for w in query.lower().split() if len(w) > 3]
        hits = [dict(r) for r in rows
                if any(w in f"{r['issue']} {r['lesson']}".lower() for w in words)]
        return hits[:3]
    except Exception:
        return None
