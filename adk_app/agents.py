"""The courtroom as ADK agents.

  SequentialAgent (top)  -> intake, build_cases, authority_map, hearing, verdict, appeal, playbook
  ParallelAgent          -> the two advocates, and the three-judge panel
  LoopAgent              -> the argue/rebut rounds per issue
  BaseAgent (custom)     -> iterates issues (ADK has no native map-over-list)

Instructions use single-brace {state_vars}; the paper-derived rules are concatenated
as plain text (no literal braces, which ADK would treat as state keys)."""
import os
from typing import AsyncGenerator

from google.adk.agents import (BaseAgent, LlmAgent, LoopAgent, ParallelAgent,
                               SequentialAgent)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from app.pipeline import ADVOCATE_RULES, JUDGE_RULES
from . import models
from .knowledge import (find_cases, find_regulations, recall_experience,
                        remember_experience)
from .ratelimit import nemotron_rate_guard

ROUNDS = int(os.getenv("HEARING_ROUNDS", "3"))

SCORE_INSTRUCTION = (
    "You are a senior legal expert. Score the exchange ({your_round} vs {opp_round}) on "
    "issue {current_issue} across three dimensions: cognitive agility, professional "
    "knowledge, logical rigor. Reply with a JSON object whose keys are cognitive_agility, "
    "professional_knowledge, logical_rigor and overall, each valued 1 (claimant stronger), "
    "0 (tie), or -1 (defendant stronger)."
)

# ---- per-case phases --------------------------------------------------------
intake = LlmAgent(
    name="intake", model=models.claude("sonnet"),
    instruction="From the case facts in {facts}, confirm the distinct legal issues and "
                "list them plainly, one per line.",
    output_key="intake_summary",
)

your_theory = LlmAgent(
    name="your_theory", model=models.claude("opus"),
    instruction="You are counsel for the {side} in a {forum} across {jurisdictions}. "
                "Give your overall theory of the case on the issues {issues}. " + ADVOCATE_RULES,
    output_key="your_case_theory",
)
opp_theory = LlmAgent(
    name="opp_theory", model=models.nemotron(),
    before_model_callback=nemotron_rate_guard,
    instruction="You are opposing counsel. Give the opponent's overall theory of the case "
                "on the issues {issues}. " + ADVOCATE_RULES,
    output_key="opp_case_theory",
)
build_cases = ParallelAgent(name="build_cases", sub_agents=[your_theory, opp_theory])

authority_map = LlmAgent(
    name="authority_map", model=models.claude("sonnet"),
    tools=[find_cases, find_regulations],
    instruction="For each issue in {issues}, call find_cases with the issue and the "
                "jurisdictions {jurisdictions} to retrieve authorities, then name the "
                "turning point in each. Summarise the authority map.",
    output_key="authorities",
)

# ---- per-issue hearing parts ------------------------------------------------
your_round = LlmAgent(
    name="your_advocate", model=models.claude("opus"),
    tools=[recall_experience],
    instruction="You are counsel for the {side}. Issue: {current_issue}. Your theory: "
                "{your_case_theory}. First call recall_experience for the issue and use any "
                "lessons. " + ADVOCATE_RULES + " Refute the single strongest opposing point "
                "and state your confidence.",
    output_key="your_round",
)
opp_round = LlmAgent(
    name="opponent_advocate", model=models.nemotron(),
    before_model_callback=nemotron_rate_guard,
    instruction="You are opposing counsel. Issue: {current_issue}. Refute the single "
                "strongest point in {your_round}. " + ADVOCATE_RULES,
    output_key="opp_round",
)
hearing_rounds = LoopAgent(
    name="hearing_rounds", sub_agents=[your_round, opp_round], max_iterations=ROUNDS,
)

judge_uk = LlmAgent(
    name="judge_uk", model=models.gemini(),
    instruction="You are a UK judge. " + JUDGE_RULES + " Issue: {current_issue}. "
                "Exchange: {your_round} versus {opp_round}.",
    output_key="ruling_uk",
)
judge_us = LlmAgent(
    name="judge_us", model=models.claude("opus"),
    instruction="You are a US judge. " + JUDGE_RULES + " Issue: {current_issue}. "
                "Exchange: {your_round} versus {opp_round}.",
    output_key="ruling_us",
)
judge_ng = LlmAgent(
    name="judge_ng", model=models.nemotron(),
    before_model_callback=nemotron_rate_guard,
    instruction="You are a Nigerian judge. " + JUDGE_RULES + " Issue: {current_issue}. "
                "Exchange: {your_round} versus {opp_round}.",
    output_key="ruling_ng",
)
panel = ParallelAgent(name="panel", sub_agents=[judge_uk, judge_us, judge_ng])

referee = LlmAgent(
    name="referee", model=models.claude("sonnet"),
    instruction=SCORE_INSTRUCTION, output_key="scores",
)


class HearingAgent(BaseAgent):
    """Iterates issues; per issue runs the rounds loop, the panel, and the referee."""
    rounds: LoopAgent
    panel: ParallelAgent
    referee: LlmAgent
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name, rounds, panel, referee):
        super().__init__(name=name, rounds=rounds, panel=panel, referee=referee,
                         sub_agents=[rounds, panel, referee])

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        issues = ctx.session.state.get("issues") or []
        results = []
        for issue in issues:
            ctx.session.state["current_issue"] = issue
            async for e in self.rounds.run_async(ctx):
                yield e
            async for e in self.panel.run_async(ctx):
                yield e
            async for e in self.referee.run_async(ctx):
                yield e
            results.append({
                "issue": issue,
                "your_round": ctx.session.state.get("your_round"),
                "opp_round": ctx.session.state.get("opp_round"),
                "panel": {"uk": ctx.session.state.get("ruling_uk"),
                          "us": ctx.session.state.get("ruling_us"),
                          "ng": ctx.session.state.get("ruling_ng")},
                "scores": ctx.session.state.get("scores"),
            })
        ctx.session.state["hearing"] = results


hearing = HearingAgent(name="hearing", rounds=hearing_rounds, panel=panel, referee=referee)

# ---- verdict, appeal, playbook ---------------------------------------------
verdict = LlmAgent(
    name="verdict", model=models.claude("sonnet"),
    instruction="From the hearing results {hearing}, give the likely outcome per issue, "
                "the opponent's strongest line, and the main vulnerabilities. Frame it as a "
                "pattern with stated uncertainty, never a verdict.",
    output_key="verdict",
)
appeal = LlmAgent(
    name="appeal", model=models.claude("opus"),
    instruction="For a {forum} matter, find grounds of appeal (error of law, procedural "
                "unfairness, perverse finding) or, in arbitration, grounds to challenge the "
                "award under the New York Convention, the UNCITRAL Model Law and the LCIA or "
                "ICC rules. Do not invent article numbers. Base it on {verdict}.",
    output_key="appeal",
)
strategist = LlmAgent(
    name="strategist", model=models.claude("opus"),
    tools=[remember_experience],
    instruction="Write the lawyer-facing playbook from {verdict}: DO, AVOID, your "
                "vulnerabilities, the opponent's strongest line, and the predicted outcome "
                "per issue with confidence, every claim tied to a cited authority. Then call "
                "remember_experience to file one key lesson for future cases.",
    output_key="playbook",
)

root_agent = SequentialAgent(
    name="courtroom",
    sub_agents=[intake, build_cases, authority_map, hearing, verdict, appeal, strategist],
)
