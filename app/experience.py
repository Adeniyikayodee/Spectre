"""Experience base (AgentCourt knowledge construction). A small persistent store of
post-trial reflections that grows across runs, so a later case reads what an earlier
one learned. SQLite, zero-config; keyword retrieval (not embeddings) for the demo.

A fresh connection per call keeps it safe under the SSE threadpool."""
import os
import sqlite3
import time
from contextlib import closing

_DB = os.getenv("EXPERIENCE_DB", "experience.db")


def _conn():
    c = sqlite3.connect(_DB)
    c.execute(
        "CREATE TABLE IF NOT EXISTS experience ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, side TEXT, issue TEXT, "
        "kind TEXT, text TEXT, tags TEXT, ts REAL)"
    )
    return c


def add(case_id: str, side: str, issue: str, kind: str, text: str, tags: str = "") -> None:
    with closing(_conn()) as c:
        c.execute(
            "INSERT INTO experience (case_id, side, issue, kind, text, tags, ts) "
            "VALUES (?,?,?,?,?,?,?)",
            (case_id, side, issue, kind, text, tags.lower(), time.time()),
        )
        c.commit()


def search(query: str, side: str | None = None, limit: int = 3) -> list[dict]:
    """Relevant prior reflections, ranked by keyword overlap with the query."""
    words = {w for w in _norm(query).split() if len(w) > 3}
    if not words:
        return []
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT issue, kind, text, side, tags FROM experience ORDER BY ts DESC"
        ).fetchall()
    scored = []
    for issue, kind, text, s, tags in rows:
        if side and s != side:
            continue
        hay = _norm(f"{issue} {text} {tags}")
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, {"issue": issue, "kind": kind, "text": text, "side": s}))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit]]


def all_entries(limit: int = 200) -> list[dict]:
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT case_id, side, issue, kind, text, ts FROM experience "
            "ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"case_id": r[0], "side": r[1], "issue": r[2], "kind": r[3],
             "text": r[4], "ts": r[5]} for r in rows]


def count() -> int:
    with closing(_conn()) as c:
        return c.execute("SELECT COUNT(*) FROM experience").fetchone()[0]


def reset() -> None:
    with closing(_conn()) as c:
        c.execute("DELETE FROM experience")
        c.commit()


def _norm(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in (s or ""))
