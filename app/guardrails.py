"""Ethics enforced in code, not just slides. Every response carries the
decision-support stamp; Nigeria coverage is flagged."""

DISCLAIMER = (
    "Decision support, not legal advice. A qualified lawyer must verify every "
    "output, including that each cited authority truly supports the proposition "
    "it is cited for."
)


TENDENCY_CAVEAT = (
    "Judicial tendency is a precedent-pattern likelihood with stated uncertainty — not a "
    "verdict and not a named judge's bias. Court-formulated facts are not neutral and only some "
    "disputes reach judgment (selection effect), so similar facts can yield opposite outcomes "
    "(Aletras et al. 2016)."
)


def stamp(payload: dict) -> dict:
    out = dict(payload)
    out["disclaimer"] = DISCLAIMER
    return out


def coverage_note(jurisdictions: list[str]) -> str | None:
    if any(j.lower() in ("nigeria", "ng") for j in jurisdictions):
        return ("Coverage note: Nigerian case law is thin in open data; results "
                "lean on live retrieval and NG confidence should be read with caution.")
    return None
