"""FastAPI surface: the REST contract for the front end.
CORS open for the Lovable/Momen front ends; every body carries the disclaimer."""
import json

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from . import experience, graph, guardrails, pipeline, store  # noqa: E402  (after load_dotenv)
from .router import provider_status  # noqa: E402

app = FastAPI(title="Litigation War-Game Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- schemas ----------------------------------------------------------------
class CreateCase(BaseModel):
    facts: str
    side: str
    jurisdictions: list[str]
    forum: str  # "litigation" | "arbitration"
    issues: list[str] | None = None
    arbitration_rules: str | None = None


class CaseRef(BaseModel):
    case_id: str


def _require(case_id: str) -> dict:
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, f"unknown case_id: {case_id}")
    return case


# ---- routes -----------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "Litigation War-Game Engine",
        "providers": provider_status(),
        "endpoints": ["/create_case", "/run_hearing", "/run_hearing/stream",
                      "/assess_appeal", "/get_playbook", "/get_case_map",
                      "/list_experience", "/reset_demo", "/health"],
        "disclaimer": guardrails.DISCLAIMER,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/create_case")
def create_case(body: CreateCase):
    case = pipeline.intake(body.model_dump())
    store.save_case(case)
    return guardrails.stamp({
        "case_id": case["case_id"],
        "issues": case["issues"],
        "coverage_note": guardrails.coverage_note(case["jurisdictions"]),
    })


@app.post("/run_hearing")
def run_hearing(body: CaseRef):
    case = _require(body.case_id)
    issues = pipeline.run_hearing(case)
    store.save_case(case)
    return guardrails.stamp({"case_id": case["case_id"], "issues": issues})


@app.get("/run_hearing/stream")
def run_hearing_stream(case_id: str):
    """Server-Sent Events: the hearing as it happens, for the courtroom UI."""
    case = _require(case_id)

    def gen():
        try:
            for event in pipeline.stream_hearing(case):
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            store.save_case(case)
        except Exception as e:  # surface as a stream error, never a mid-stream 500
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/assess_appeal")
def assess_appeal(body: CaseRef):
    case = _require(body.case_id)
    appeal = pipeline.assess_appeal(case)
    store.save_case(case)
    return guardrails.stamp({"case_id": case["case_id"], **appeal})


@app.get("/get_playbook")
def get_playbook(case_id: str):
    case = _require(case_id)
    return guardrails.stamp({"case_id": case_id, **pipeline.build_playbook(case)})


@app.get("/get_case_map")
def get_case_map(case_id: str):
    case = _require(case_id)
    return guardrails.stamp({"case_id": case_id, **graph.case_map(case)})


@app.get("/list_experience")
def list_experience():
    """The experience base, so the UI can show it growing across runs."""
    return {"count": experience.count(), "entries": experience.all_entries()}


@app.post("/reset_demo")
def reset_demo():
    experience.reset()
    store.reset()
    return {"ok": True, "experience": experience.count()}
