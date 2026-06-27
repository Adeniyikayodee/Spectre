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
