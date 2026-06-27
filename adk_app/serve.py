"""Streaming surface for the ADK courtroom. Runs the SequentialAgent through an ADK
Runner and maps each ADK event to the same SSE contract the Lovable UI already uses
(agent_message, panel_ruling, score_update, verdict, playbook_ready, done)."""
import json
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from .agent import root_agent  # noqa: E402

APP_NAME = "courtroom"
app = FastAPI(title="Litigation War-Game Engine (ADK)")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)
_CASES: dict[str, dict] = {}

# ADK agent author -> our SSE event type.
_EVENT = {
    "intake": "phase_start",
    "your_theory": "agent_message", "opp_theory": "agent_message",
    "authority_map": "retrieval",
    "your_advocate": "agent_message", "opponent_advocate": "agent_message",
    "judge_uk": "panel_ruling", "judge_us": "panel_ruling", "judge_ng": "panel_ruling",
    "referee": "score_update", "verdict": "verdict",
    "appeal": "agent_message", "strategist": "playbook_ready",
}


class CreateCase(BaseModel):
    facts: str
    side: str
    jurisdictions: list[str]
    forum: str
    issues: list[str] | None = None
    arbitration_rules: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "engine": "adk"}


@app.post("/create_case")
def create_case(body: CreateCase):
    cid = uuid.uuid4().hex[:12]
    _CASES[cid] = body.model_dump()
    return {"case_id": cid, "issues": body.issues or []}


@app.get("/run_hearing/stream")
async def run_hearing_stream(case_id: str):
    case = _CASES.get(case_id)
    if not case:
        raise HTTPException(404, f"unknown case_id: {case_id}")

    uid, sid = "lawyer", case_id
    await _session_service.create_session(
        app_name=APP_NAME, user_id=uid, session_id=sid,
        state={
            "facts": case["facts"], "side": case["side"], "forum": case["forum"],
            "jurisdictions": ", ".join(case["jurisdictions"]),
            "issues": case.get("issues") or [],
        },
    )
    message = types.Content(role="user", parts=[types.Part(text="Run the hearing.")])

    async def gen():
        try:
            async for ev in _runner.run_async(user_id=uid, session_id=sid, new_message=message):
                text = ""
                if ev.content and ev.content.parts:
                    text = "".join(p.text or "" for p in ev.content.parts
                                   if getattr(p, "text", None))
                if not text.strip():
                    continue
                payload = {"type": _EVENT.get(ev.author, "agent_message"),
                           "author": ev.author, "text": text}
                yield f"event: {payload['type']}\ndata: {json.dumps(payload)}\n\n"
            yield 'event: done\ndata: {"type": "done"}\n\n'
        except Exception as e:
            yield f'event: error\ndata: {json.dumps({"type": "error", "message": str(e)})}\n\n'

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
