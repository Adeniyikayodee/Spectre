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
