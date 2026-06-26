"""FastAPI surface. The REST contract from BUILD_PLAN.md §6.
CORS open for the Lovable/Momen front ends; every body carries the disclaimer."""
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from . import graph, guardrails, pipeline, store  # noqa: E402  (after load_dotenv)
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
        "endpoints": ["/create_case", "/run_hearing", "/assess_appeal",
                      "/get_playbook", "/get_case_map", "/health"],
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
