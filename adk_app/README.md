# adk_app — the courtroom on Google ADK

A second orchestration of the same engine, built on the Google Agent Development Kit.
It reuses the verified tool logic in `app/` (research, graph, experience) and emits the
same SSE event contract, so the Lovable UI is unchanged. The original `app/` REST service
stays intact.

## Structure (maps to the ADK primitives)

```
SequentialAgent "courtroom"
  intake          LlmAgent (Claude)
  build_cases     ParallelAgent[ your_theory (Claude), opp_theory (Nemotron) ]
  authority_map   LlmAgent (Claude) + tools[find_cases, find_regulations]
  hearing         HearingAgent (custom BaseAgent, per issue):
                    LoopAgent[ your_advocate, opponent_advocate ]  (rounds)
                    ParallelAgent[ judge_uk (Gemini), judge_us (Claude), judge_ng (Nemotron) ]
                    referee (Claude)
  verdict         LlmAgent (Claude)
  appeal          LlmAgent (Claude)
  strategist      LlmAgent (Claude) + tool[remember_experience]
```

- **Models:** `models.py` — Claude via the ADK registry on Vertex in prod, via LiteLlm +
  the direct Anthropic key locally; Gemini native; Nemotron via LiteLlm + OpenRouter.
- **Nemotron caps:** `ratelimit.py` — a `before_model_callback` enforcing 50/day, 20/min.
- **Knowledge bases:** `knowledge.py` — `find_cases` (Perplexity + seeds), `find_regulations`
  (Cellar), `recall_experience`/`remember_experience` (BigQuery in prod, SQLite locally).

## Run locally

```bash
pip install -r adk_app/requirements.txt
# Claude runs on the direct Anthropic key; Gemini/Nemotron light up when those keys are set.
uvicorn adk_app.serve:app --reload
```

```bash
CID=$(curl -s -X POST localhost:8000/create_case -H 'content-type: application/json' \
      -d @app/fixtures/uk_contract.json | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -N "localhost:8000/run_hearing/stream?case_id=$CID"
```

## Deploy to Cloud Run

```bash
# Standard ADK API server:
adk deploy cloud_run --project=$GCP_PROJECT --region=$GCP_REGION adk_app

# Or the custom streaming app (this serve.py) via a container:
gcloud run deploy litigation-adk --source . --region $GCP_REGION \
  --command uvicorn --args adk_app.serve:app,--host,0.0.0.0,--port,8080 --timeout 3600
```

Set `GOOGLE_GENAI_USE_VERTEXAI=true` and `GCP_PROJECT` in prod to move Claude onto the
Vertex registry and the experience base onto BigQuery.
