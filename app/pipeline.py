"""The game loop. Phases as functions over a case dict.

Paper lineage (see how_papers_inform_design.md — mechanisms, not citations):
  AgentCourt (Chen 2024)  roster + side-swap, 3-dimension scoring, post-verdict reflection.
  Irving (2018)           precommit, refute-one-flaw, state confidence, reward honest ignorance.
  Du (2023)               2-4 rounds then plateau, summarise before ruling, disagreement = uncertainty.
  Aletras (2016)          judge on the FACTS, tendency as a likelihood not a verdict, stated caveats.
"""
import os
import uuid

from . import agents, graph, guardrails, research

OPP = {"claimant": "defendant", "defendant": "claimant"}
HEARING_ROUNDS = int(os.getenv("HEARING_ROUNDS", "2"))  # Du: 2-4 then plateau; 2 is cheapest valid

ADVOCATE_RULES = (
    "Hearing rules (Irving et al.): PRECOMMIT your position with a confidence 0-1 before "
    "arguing; to win, REFUTE THE SINGLE STRONGEST opposing point — do not answer everything; "
    "state confidence on each point; if the law is genuinely unsettled, concede it and say why."
)
JUDGE_RULES = (
    "Rule on the FACTS first (Aletras: facts predict outcomes better than legal labels). Give a "
    "per-issue likelihood for claimant vs defendant — a pattern, NOT a verdict — and state your "
    "uncertainty. Concede if the issue is genuinely unsettled. Do not profile any named judge. "
    "Note the stronger advocate's cognitive agility, professional knowledge, and logical rigor."
)


# ---- P0 intake (AgentCourt planning step) -----------------------------------
def intake(payload: dict) -> dict:
    case = dict(payload)
    case["case_id"] = uuid.uuid4().hex[:12]
    if not case.get("issues"):
        raw = agents.ask(
            "intake",
            "Extract the distinct legal issues from the facts. One issue per line, no numbering.",
            f"Facts:\n{case['facts']}",
        )
        case["issues"] = [
            ln.strip("-•* ").strip() for ln in raw.splitlines() if ln.strip()
        ][:6] or ["(no issues extracted)"]
    case.setdefault("hearing", None)
    case.setdefault("appeal", None)
    case.setdefault("playbook", None)
    return case


def _adv_sys(side: str, case: dict) -> str:
    return (f"You are counsel for the {side} in a {case['forum']} across "
            f"{', '.join(case['jurisdictions'])}. Be specific and name the authority you rely on.")


# ---- P1-P4 the hearing ------------------------------------------------------
def run_hearing(case: dict) -> list[dict]:
    results = []
    you = case["side"]
    opp = OPP.get(you, "opponent")
    for issue in case["issues"]:
        # P1: precommit (Irving) — both sides lock a position before the exchange.
        your_pre = agents.ask("advocate_you", _adv_sys(you, case),
                              f"{ADVOCATE_RULES}\n\nIssue: {issue}\nPrecommit your position now, briefly.")
        opp_pre = agents.ask("advocate_opp", _adv_sys(opp, case),
                             f"{ADVOCATE_RULES}\n\nIssue: {issue}\nPrecommit your position now, briefly.")
        transcript = [f"{you}: {your_pre}", f"{opp}: {opp_pre}"]

        # P1: rounds (Du), alternating who refutes first to cancel order bias (Irving).
        for r in range(HEARING_ROUNDS):
            role, side = ("advocate_opp", opp) if r % 2 == 0 else ("advocate_you", you)
            reb = agents.ask(role, _adv_sys(side, case),
                             f"{ADVOCATE_RULES}\n\nIssue: {issue}\nLatest argument:\n{transcript[-1]}\n"
                             f"Refute its single strongest point. Be brief.")
            transcript.append(f"{side} (round {r + 1}): {reb}")

        # P2: analogous authorities, each annotated by the turning-point analyst.
        authorities = research.find_authorities(issue, case["jurisdictions"])
        _annotate_authorities(issue, authorities, you)

        # P3: summarise the exchange before the panel rules (Du saves tokens/context),
        #     then the three-model panel rules on the facts (Aletras framing).
        summary = agents.ask("referee", "Summarise this hearing exchange in <=5 neutral bullets.",
                             "\n\n".join(transcript))
        brief = f"Issue: {issue}\nFacts: {case['facts']}\n\nExchange:\n{summary}\n\n{JUDGE_RULES}"
        panel = {
            "uk": agents.ask("judge_uk", "You are a UK judge.", brief),
            "us": agents.ask("judge_us", "You are a US judge.", brief),
            "ng": agents.ask("judge_ng", "You are a Nigerian judge.", brief),
        }

        results.append({
            "issue": issue,
            "your_best": your_pre,
            "opponent_best": opp_pre,
            "transcript": transcript,
            "authorities": authorities,
            "panel_ruling": panel,
            **_tendency(panel),  # winner, confidence, likelihood, uncertainty
        })
    graph.mark_load_bearing(results)  # the authority the argument most relies on
    case["hearing"] = results
    graph.ingest(case)                # persist the citation graph to Aura (best-effort)
    return results


def _annotate_authorities(issue: str, authorities: list[dict], side: str) -> None:
    """Turning-point analyst (Claude): the pivot that actually decided each case, and
    whether it genuinely supports the citing side (a light entailment signal)."""
    for a in authorities:
        if not a.get("name"):  # placeholder / unparsed — no analyst call
            a.setdefault("turning_point", None)
            a.setdefault("supports", "unknown")
            continue
        raw = agents.ask(
            "turning_point", "You are a turning-point analyst.",
            f"Issue: {issue}\nAuthority: {a['name']} — {a.get('cite', '')}\n"
            f"What it held: {a.get('point', '')}\n\nOutput exactly two lines:\n"
            f"PIVOT: <the fact or argument that actually decided it>\n"
            f"SUPPORTS: yes|no|contested (does it genuinely support the {side} on this issue?)",
        )
        a["turning_point"] = _grab(raw, "PIVOT:")
        a["supports"] = (_grab(raw, "SUPPORTS:") or "unknown").lower()


def _grab(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.strip().upper().startswith(prefix.upper()):
            return line.split(":", 1)[1].strip()
    return None


def _tendency(panel: dict) -> dict:
    """Du: panel disagreement = uncertainty. Aletras: report a likelihood, not a verdict."""
    rulings = [v.lower() for v in panel.values()]
    if any(r.startswith("[stub") for r in rulings):
        return {"winner": "undecided", "confidence": "unknown (models not configured)",
                "likelihood": None, "uncertainty": "models not configured"}
    votes = {"claimant": 0, "defendant": 0}
    for r in rulings:
        for k in votes:
            if k in r:
                votes[k] += 1
    if not any(votes.values()):
        return {"winner": "undecided", "confidence": "low", "likelihood": None,
                "uncertainty": "panel gave no clear ruling"}
    winner = max(votes, key=votes.get)
    agree = max(votes.values())  # how many of the 3 judges agree = the spread signal
    confidence = {3: "high", 2: "medium"}.get(agree, "low")
    band = {3: "~75-90%", 2: "~55-70%", 1: "~50%"}[agree]
    uncertainty = ("panel unanimous, but a pattern not a verdict" if agree == 3
                   else "panel split — treat the issue as open")
    return {"winner": winner, "confidence": confidence,
            "likelihood": f"{winner} {band}", "uncertainty": uncertainty}


# ---- P5 appeal (our addition; grounded in the instruments) ------------------
def assess_appeal(case: dict) -> dict:
    mode = "arbitration" if case.get("forum") == "arbitration" else "litigation"
    rules = case.get("arbitration_rules") or "UNCITRAL / LCIA / ICC"
    if mode == "litigation":
        system = ("Find grounds of appeal: error of law, procedural unfairness, or a perverse "
                  "finding. State each ground and its realistic prospect.")
    else:
        system = ("Find grounds to challenge or resist enforcement of an award under the New York "
                  f"Convention, the UNCITRAL Model Law and the {rules} rules. Do not invent article "
                  "numbers — only name grounds you can cite from the instruments. State each ground "
                  "and its realistic prospect.")
    raw = agents.ask("appeal", system, f"Verdict so far:\n{_summary(case)}")
    case["appeal"] = {"mode": mode, "analysis": raw}
    return case["appeal"]


# ---- P6 playbook (AgentCourt post-verdict reflection) -----------------------
def build_playbook(case: dict) -> dict:
    raw = agents.ask(
        "strategist",
        "You are a litigation strategist writing a post-verdict reflection. Produce a lawyer-facing "
        "playbook: DO, AVOID, your vulnerabilities, the opponent's strongest line, and the predicted "
        "outcome per issue with its likelihood and uncertainty. Tie every claim to a cited authority.",
        _summary(case),
    )
    case["playbook"] = raw
    hearing = case.get("hearing") or []
    return {
        "playbook": raw,
        "outcomes": [{"issue": h["issue"], "winner": h["winner"],
                      "likelihood": h.get("likelihood"), "uncertainty": h.get("uncertainty")}
                     for h in hearing],
        "opponent_map": [{"issue": h["issue"], "argued": h["opponent_best"]} for h in hearing],
        "fault_tree": graph.fault_tree(case),
        "tendency_caveat": guardrails.TENDENCY_CAVEAT,
    }


def _summary(case: dict) -> str:
    if not case.get("hearing"):
        return "(hearing not yet run — call /run_hearing first)"
    return "\n".join(
        f"- {h['issue']}: {h.get('likelihood') or h['winner']} "
        f"(confidence {h['confidence']}; {h.get('uncertainty', '')})"
        for h in case["hearing"]
    )
