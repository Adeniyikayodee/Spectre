"""System of record. Always in-memory; also appends to BigQuery when GCP_PROJECT
is set. The BQ path is real but fully guarded — no GCP, clean no-op; any failure
never breaks a request."""
import json
import os
from datetime import datetime, timezone

_CASES: dict[str, dict] = {}
_bq = None          # (client, dataset) once initialised
_bq_init = False


def save_case(case: dict) -> None:
    _CASES[case["case_id"]] = case
    _persist(case)


def get_case(case_id: str) -> dict | None:
    return _CASES.get(case_id)


def reset() -> None:
    _CASES.clear()


def _client():
    global _bq, _bq_init
    if _bq_init:
        return _bq
    _bq_init = True
    if not os.getenv("GCP_PROJECT"):
        return None
    try:
        from google.cloud import bigquery  # lazy

        client = bigquery.Client()
        ds = os.getenv("BQ_DATASET", "litigation")
        client.create_dataset(ds, exists_ok=True)
        client.query(
            f"CREATE TABLE IF NOT EXISTS `{client.project}.{ds}.cases` "
            "(case_id STRING, ts TIMESTAMP, side STRING, forum STRING, payload STRING)"
        ).result()
        _bq = (client, ds)
    except Exception:
        _bq = None
    return _bq


def _persist(case: dict) -> None:
    bundle = _client()
    if not bundle:
        return
    client, ds = bundle
    try:
        client.insert_rows_json(f"{client.project}.{ds}.cases", [{
            "case_id": case["case_id"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "side": case.get("side"),
            "forum": case.get("forum"),
            "payload": json.dumps(case, default=str),
        }])
    except Exception:
        pass
