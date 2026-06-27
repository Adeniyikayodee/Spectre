"""Neo4j Aura citation graph + fault tree. Aura is the persistent store (best-effort
ingest); the display graph and load-bearing calc are derived in-memory so /get_case_map
works with or without a DB.

Load-bearing authority = the one the whole argument most relies on: the authority
supporting the most issues across the case (the case whose fall does the most damage)."""
import os


def configured() -> bool:
    return bool(os.getenv("NEO4J_URI"))


def _driver():
    from neo4j import GraphDatabase  # lazy

    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )


def mark_load_bearing(hearing: list[dict]) -> list[dict]:
    """Flag, per issue, the authority with the highest cross-issue reliance."""
    reliance: dict[str, int] = {}
    for h in hearing:
        for a in h.get("authorities", []):
            cite = a.get("cite")
            if cite:
                reliance[cite] = reliance.get(cite, 0) + 1
    for h in hearing:
        best, best_r = None, -1
        for a in h.get("authorities", []):
            a["load_bearing"] = False
            r = reliance.get(a.get("cite"), 0)
            if r > best_r:
                best, best_r = a, r
        if best is not None:
            best["load_bearing"] = True
    return hearing


def ingest(case: dict) -> None:
    """Write Issue -[:SUPPORTED_BY]-> Authority into Aura. Best-effort: a DB hiccup
    never breaks a request — the in-memory graph still serves."""
    if not configured():
        return
    try:
        driver = _driver()
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as s:
            for h in case.get("hearing") or []:
                s.run("MERGE (i:Issue {case_id:$cid, text:$t})",
                      cid=case["case_id"], t=h["issue"])
                for a in h.get("authorities", []):
                    if not a.get("cite"):
                        continue
                    s.run(
                        "MATCH (i:Issue {case_id:$cid, text:$t}) "
                        "MERGE (a:Authority {cite:$cite}) "
                        "SET a.name=$name, a.load_bearing=$lb "
                        "MERGE (i)-[:SUPPORTED_BY]->(a)",
                        cid=case["case_id"], t=h["issue"], cite=a["cite"],
                        name=a.get("name"), lb=bool(a.get("load_bearing")),
                    )
        driver.close()
    except Exception:
        pass


def case_map(case: dict) -> dict:
    """Citation graph for display: issues -> supporting authorities."""
    nodes, edges = [], []
    issues = case.get("issues", [])
    for i, issue in enumerate(issues):
        nodes.append({"id": f"issue:{i}", "label": issue, "type": "issue"})
    for h in (case.get("hearing") or []):
        iid = f"issue:{issues.index(h['issue'])}"
        for j, a in enumerate(h.get("authorities", [])):
            aid = f"auth:{iid}:{j}"
            nodes.append({
                "id": aid, "type": "authority",
                "label": a.get("name") or (a.get("cite") or "")[:60],
                "cite": a.get("cite"), "jurisdiction": a.get("jurisdiction"),
                "turning_point": a.get("turning_point"),
                "load_bearing": a.get("load_bearing", False),
            })
            edges.append({"from": iid, "to": aid, "rel": "SUPPORTED_BY"})
    return {"nodes": nodes, "edges": edges,
            "backend": "neo4j" if configured() else "in-memory (set NEO4J_URI to persist)"}


def fault_tree(case: dict) -> list[dict]:
    """The load-bearing authority per issue — what the argument can't afford to lose."""
    return [
        {"issue": h["issue"], "authority": a.get("cite"), "name": a.get("name")}
        for h in (case.get("hearing") or [])
        for a in h.get("authorities", [])
        if a.get("load_bearing")
    ]
