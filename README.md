# Litigation War-Game Engine

An adversarial, multi-model moot court that turns a set of case facts into a
lawyer-facing strategy playbook. It works for either side, across the UK, the US,
and Nigeria, for both litigation and arbitration.

Two engines share the same tools and event contract: the FastAPI pipeline in `app/`
(documented below) and a Google ADK build in [`adk_app/`](adk_app/) that runs the same
phases as ADK Sequential, Parallel, and Loop agents.

## Run it (no keys required)

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
curl -s -X POST localhost:8000/run_hearing   -H 'content-type: application/json' -d "{\"case_id\":\"$CID\"}"
curl -s -X POST localhost:8000/assess_appeal -H 'content-type: application/json' -d "{\"case_id\":\"$CID\"}"
curl -s "localhost:8000/get_playbook?case_id=$CID"
curl -s "localhost:8000/get_case_map?case_id=$CID"
```

With no keys set, every model call returns a clearly marked `[stub:role]` string and
the API still returns the correct JSON shape. Add a key to `.env` and that role goes
live automatically, with no code change.

## What is built

| Component | Status |
|---|---|
| Router and four providers (Claude, Gemini, Nemotron, Perplexity) | Real calls when keys are set; clear stubs otherwise |
| Nemotron via NVIDIA-direct or OpenRouter, auto-detected; rate guard 50/day, 20/min, with cache | Implemented |
| Game pipeline P0 to P6 (precommit, two to four rounds, panel spread as confidence) | Runs end to end |
| Authorities: hand-checked seed set for the worked case, else Perplexity live retrieval and the turning-point analyst | Implemented |
| Neo4j citation graph and load-bearing fault tree | In-memory calculation; best-effort persistence to Aura |
| BigQuery store | Real append, guarded; a no-op until `GCP_PROJECT` is set |
| Experience base and post-verdict reflection (cross-run learning) | SQLite; a later run reads earlier runs' reflections |

## Live stream (front-end contract)

`GET /run_hearing/stream?case_id=...` is Server-Sent Events: the hearing as it
happens. The front end opens an `EventSource` and renders each typed event. The
blocking `POST /run_hearing` returns the same result as one JSON body.

| Event | Payload | Renders as |
|---|---|---|
| `clerk` | `text` | narrator line |
| `phase_start` | `phase`, `issue`, `label` | new issue panel |
| `agent_planning` | `role`, `issue`, `bases {legal, case, experience}` | knowledge bases queried |
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
runs; `POST /reset_demo` clears it.

## Methodology: the pleading-to-proof matrix

The matrix is not a single model call. It is a grounded retrieval-and-classification
pipeline in which the model may only cite passages it was handed, so no citation can be
invented. The code is in `app/bundle.py` and `app/evidence.py`.

Goal: for every pleaded proposition (each allegation or denial, with the legal element it
must prove), decide whether the evidence in the bundle supports it, and link that decision
to an exact document and paragraph.

1. **Index the bundle.** Each `.docx` is read read-only and split into its non-empty
   paragraphs. A citable passage is `(document, paragraph index, text)`. Documents are
   tagged pleading (Claim Form, Particulars) or evidence (everything else) by filename.
2. **Extract propositions.** An extraction agent (Claude) reads only the pleadings and
   returns structured rows `{text, party, legal_element}`. The matrix rows come straight
   from what was pleaded.
3. **Retrieve candidates (lexical pre-filter).** For each proposition, every evidence
   passage is scored by term overlap: the significant words (length over three) from the
   proposition and its legal element, counted against each passage. The top twelve are
   kept. If nothing overlaps, the proposition is marked missing (a gap) with no model call.
4. **Classify against the candidates.** A mapping agent (Claude) receives the proposition
   and the numbered candidate passages and returns JSON: a status, a confidence (0 to 1),
   the supporting and adverse passage numbers, any contradiction, and a gap. It may only
   refer to passages by the numbers it was given.
5. **Resolve citations.** Each cited number is mapped back to its real
   `(document, paragraph)` and the verbatim quote is copied from the bundle. Any number
   outside the candidate set is dropped, so a citation cannot be fabricated.

Status taxonomy: supported (evidence proves it), adverse (evidence cuts against it),
neutral (mixed or weak), missing (no relevant passage).

Two-part confidence: first, the evidence-link strength from stage four (how well the
passages back the proposition); second, added by the hearing, the panel spread (how split
the judges were once the proposition is stress-tested). The first is how strong the proof
is; the second is how contested it is.

Limitation: the retriever is keyword and term overlap, not embeddings. It is fast, cheap,
and fully traceable, but it can miss evidence phrased in different words, which is why a
proposition with no lexical match is flagged as a gap rather than assumed proven. Swapping
the pre-filter for vector embeddings is a drop-in change behind one function.

## Research grounding

The design lifts concrete mechanisms from four papers (PDFs in
[`research/`](research/)).

- AgentCourt (Chen et al., 2024, arXiv:2408.08089) is the courtroom-sandbox blueprint:
  lawyer and judge agents, side-swapping, three knowledge bases, and post-verdict
  reflection that grows an experience base.
- AI Safety via Debate (Irving, Christiano, and Amodei, 2018, arXiv:1805.00899) supplies
  the hearing rules: precommit a position, win by refuting the single strongest point,
  state confidence on each point, and use a panel.
- Multiagent Debate (Du et al., 2023, arXiv:2305.14325) sets the knobs: two to four
  rounds, summarise the exchange before the panel rules, and read panel disagreement as
  the uncertainty signal.
- ECtHR Prediction (Aletras et al., 2016, PeerJ Computer Science) frames judicial
  tendency honestly: a likelihood from the facts with stated uncertainty, not a verdict,
  and not a profile of any named judge.

## Integration notes

- Providers fail silently to stubs by design. After adding a key, run
  `python -m app.scripts.smoke --live` to confirm it pings.
- Gemini (the UK judge) needs Application Default Credentials, not a key. Set
  `GCP_PROJECT` and run `gcloud auth application-default login` locally, or grant the
  Cloud Run service account `roles/aiplatform.user`.
- A full panel verdict needs all three judge providers (Claude, Gemini, Nemotron). If
  any judge is a stub, confidence reads `models not configured`.
- The front-end `EventSource` must close on the `done` event, or the browser reconnects
  and reruns the hearing.
- Momen sends `jurisdictions` as a JSON array and `forum` as a string. CORS is open.
- A real-model hearing is about thirty sequential calls and takes a few minutes. The
  Cloud Run deploy sets `--timeout 3600`; locally there is no timeout.

## Provider readiness and deploy

```bash
python -m app.scripts.smoke          # which integrations are configured
python -m app.scripts.smoke --live   # ping the configured ones
./deploy.sh                          # Cloud Run; keys via Secret Manager (see deploy.sh)
```
