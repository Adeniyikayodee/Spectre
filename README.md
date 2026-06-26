# Litigation War-Game Engine

An adversarial, multi-model moot court that produces a lawyer-facing strategy
playbook. Works for either side, across the UK, the US, and Nigeria, for both
litigation and arbitration.

Design: [`litigation_engine_design.md`](litigation_engine_design.md) ·
Build plan: [`BUILD_PLAN.md`](BUILD_PLAN.md)

## Run it (60 seconds, no keys needed)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # leave blank to run on stubs; fill keys to go live
uvicorn app.main:app --reload
```

```bash
curl localhost:8000/health
# end-to-end on the worked case:
CID=$(curl -s -X POST localhost:8000/create_case \
      -H 'content-type: application/json' \
      -d @app/fixtures/uk_contract.json | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s -X POST localhost:8000/run_hearing  -H 'content-type: application/json' -d "{\"case_id\":\"$CID\"}"
curl -s -X POST localhost:8000/assess_appeal -H 'content-type: application/json' -d "{\"case_id\":\"$CID\"}"
curl -s "localhost:8000/get_playbook?case_id=$CID"
curl -s "localhost:8000/get_case_map?case_id=$CID"
```

With no keys set, every model call returns a clearly-marked `[stub:role]` string and
the API still returns the correct JSON shape. Add a key to `.env` and that role goes
live automatically — no code change.

## What's wired vs. stubbed

| Component | Status |
|---|---|
| Router and four providers (Claude, Gemini, Nemotron, Perplexity) | Real calls when keys are set; clear stubs otherwise |
| Nemotron via NVIDIA-direct or OpenRouter, auto-detected; rate guard 50/day, 20/min, with cache | Implemented |
| Game pipeline P0–P6 (precommit, two to four rounds, panel spread as confidence) | Runs end to end |
| Authorities: hand-checked seed set for the worked case, else Perplexity live retrieval and the turning-point analyst | Implemented |
| Neo4j citation graph and load-bearing fault tree | In-memory calculation; best-effort persistence to Aura |
| BigQuery store | Real append, guarded; a no-op until `GCP_PROJECT` is set |
| Experience base + post-verdict reflection (cross-run learning) | SQLite; a later run reads earlier runs' reflections |

## Live stream (front-end contract)

`GET /run_hearing/stream?case_id=...` is Server-Sent Events: the hearing as it
happens. The front end opens an `EventSource` and renders each typed event. The
blocking `POST /run_hearing` returns the same result as one JSON body.

| Event | Payload | Renders as |
|---|---|---|
| `clerk` | `text` | narrator line |
| `phase_start` | `phase`, `issue`, `label` | new issue panel |
| `agent_planning` | `role`, `issue`, `bases {legal, case, experience}` | which knowledge bases were queried |
| `retrieval` | `knowledge_base`, `issue`, `query`, `hits[]` | the retrieval panel |
| `agent_message` | `role`, `side`, `issue`, `round`, `text`, `confidence` | a speech bubble |
| `panel_ruling` | `issue`, `jurisdiction`, `text` | lights the UK/US/NG judge |
| `score_update` | `issue`, `scores {cognitive_agility, professional_knowledge, logical_rigor, overall}` | the scoreboard |
| `verdict` | `outcomes[]` | the verdict screen |
| `reflection_write` | `base`, `side`, `kind`, `text` | the experience base growing |
| `done` | none | close the stream |
| `error` | `message` | a toast |

Browser `EventSource` is GET-only, hence the query param. CORS is open; for hosted
Lovable, point it at a public URL (Cloud Run, or `ngrok http 8000` while developing).

`GET /list_experience` returns the experience base so the UI can show it grow across
runs; `POST /reset_demo` clears it. Run the same case twice: the second hearing reads
the reflections the first wrote (a `retrieval` event with `knowledge_base: "experience"`).

## Integration notes (read before going live)

- **Providers fail silently to stubs by design.** After adding any key, run
  `python -m app.scripts.smoke --live` to confirm it actually pings. A bad key shows
  a clear `[stub:role]` in output, never a crash.
- **Gemini (UK judge) needs ADC, not a key.** Set `GCP_PROJECT` *and* either run
  `gcloud auth application-default login` (local) or grant the Cloud Run service
  account `roles/aiplatform.user`. Without ADC the call degrades to a stub.
- **A full panel verdict needs all three judge providers** (Claude + Gemini +
  Nemotron). If any judge is a stub, confidence reads `models not configured`.
- **Lovable EventSource must close on `done`.** `es.addEventListener("done", () =>
  es.close())` — otherwise the browser auto-reconnects and re-runs the whole hearing.
- **Momen request shape:** `POST /create_case` needs `jurisdictions` as a JSON array
  and `forum` as a string. CORS is open, so no proxy is needed.
- **Latency:** a real-model hearing is ~30 sequential calls (a few minutes). Deploy
  sets Cloud Run `--timeout 3600`; locally there is no timeout.

## Provider readiness

```bash
python -m app.scripts.smoke          # which integrations are configured
python -m app.scripts.smoke --live   # actually ping the configured ones
```

## Deploy

```bash
./deploy.sh    # Cloud Run; keys via Secret Manager. See header of deploy.sh.
```
