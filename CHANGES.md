# CHANGES

Additive evidence layer for the pleading-to-proof matrix. Scope locked to the
litigation case-theory stress test. Built into `app/` first (the deployed, verified
engine); an ADK mirror in `adk_app/` is a later stage.

## Stage 1: read the bundle and build the matrix

### Added
- `app/bundle.py` — reads the witness statement folder read only and indexes each
  `.docx` into citable passages `(document, paragraph)`. Reason: the matrix needs real,
  citable sources from the existing folder.
- `app/evidence.py` — the two agents. `extract_propositions` pulls pleaded propositions
  with their legal element; `map_evidence` links each to supporting and adverse passages
  with a status, confidence, contradictions, and gaps. Reason: this produces the matrix.
- `app/scripts/build_matrix.py` — a runner that builds the matrix on the real folder and
  prints each status with its real source link. Reason: the reviewer verification check.

### Changed
- `app/router.py` — added two roles, `evidence_extract` and `evidence_map`, both on
  Claude Sonnet. Reason: the evidence agents need model roles; kept cheap per the limits.
- `requirements.txt` — added `python-docx`. Reason: to read the `.docx` bundle.

### Left untouched (deliberately)
- The witness statement folder `WITHNESSSTATEMENS/` — read only; not moved, renamed, or
  edited. Reason: binding rule.
- `app/pipeline.py`, `app/main.py`, the stream, and `adk_app/` — not touched in Stage 1.
  Reason: feeding the matrix into the hearing and the endpoints is Stage 2.

### Assumptions
- The evidence source is the actual folder `WITHNESSSTATEMENS/`, a commercial IT-services
  contract dispute (a "TechFlow" Master Services Agreement matter), not the Post Office
  bundle the prompt names. The folder is the binding source, so it is used as-is.
- Pleaded propositions come from the pleadings (`01_Claim_Form`, `02_Particulars_of_Claim`);
  every other document is evidence.
- A citable passage is one non-empty Word paragraph, cited as `(filename, paragraph index)`.
- Mapping uses a cheap keyword pre-filter to pick candidate passages, then the agent cites
  only from those by number; embeddings would be more thorough.
- The demo runs on a handful of propositions (default 5) to stay fast and cheap.

## Stage 2: connect the matrix to the stream and the UI

### Added
- `app/fixtures/techflow.json` — the demo case matching the actual bundle (a TechFlow
  Master Services Agreement dispute). Reason: ground the hearing to the real folder.
- `frontend/index.html` — a single-file working UI: the courtroom (three-judge bench,
  two counsel tables, clerk, gallery) and a side panel that builds the matrix and logs
  the hearing from the live event stream. Reason: the watchable demo, and the spec for Lovable.

### Changed
- `app/evidence.py` — added `stream_matrix`, which emits one `evidence_mapped` event per
  proposition and sets the case issues from the propositions so the hearing argues the
  matrix. `build_matrix` now drains it (one code path). Reason: stream the matrix to the UI.
- `app/main.py` — added `GET /build_matrix/stream` (SSE) and `GET /get_matrix`. Reason:
  the UI needs to build and read the matrix; GET stream matches the existing run_hearing/stream.

### Left untouched (deliberately)
- The hearing pipeline logic, the panel, the referee, the appeal, the experience base.
  Reason: they already work; this stage only feeds the matrix in and surfaces it.
- The witness folder — still read only and untracked.

### Assumptions
- SSE endpoints are GET (not POST) so the browser EventSource can consume them, matching
  the existing run_hearing/stream; the REST contract's "POST" is served as a GET stream.
- The frontend is a thin view: all logic stays in the backend; it renders the real stream.
- Lovable and Momen are browser-based builders that cannot be driven from a terminal, so
  this working local UI is delivered directly and also serves as the Lovable spec.

## Fix: Neo4j writes via the HTTP Query API

- `app/graph.py` — `ingest` now writes through Aura's HTTP Query API (port 443) instead of
  the Bolt driver (port 7687), because Bolt is not reachable from every host while the
  official Query API always is. The citation graph now persists from the live flow
  (verified: one hearing wrote 1 Issue and 3 Authority nodes to Aura). Reason: make the
  Neo4j evidence real and host-independent. The in-memory display graph is unchanged.

## Feature: EU judge and the Cellar legislation layer

- `app/research.py` — `cellar_search` queries the EU Cellar SPARQL endpoint for EU legal
  texts whose English title contains a topical keyword from the issue (fallback "contract").
  Best-effort. Reason: give the EU jurisdiction a real legislation source so Cellar is used.
- `app/router.py` — added the `judge_eu` role (Claude Sonnet).
- `app/pipeline.py` — the panel adds an EU seat only when EU is a jurisdiction; the EU judge
  reads the Cellar results before ruling and a `retrieval` event surfaces them. Panel-spread
  confidence now scales to any bench size (fixes a four-judge edge case). Reason: add EU to
  the judges so the engine calls Cellar.
- `app/fixtures/techflow.json`, `frontend/index.html` — EU added to the demo jurisdictions
  and a fourth judge figure added to the 3D bench.
- Verified: a four-judge hearing ruled with an EU seat, and Cellar returned real EU acts
  matched on a topical keyword.
