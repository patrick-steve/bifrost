"""Deterministic, non-AI fallback rulebook (IMPLEMENTATION.md section 12).

Pure function of public data, published contracts and the public forecast.
"""
from __future__ import annotations

from . import config
from .contracts import describe, explain_empty, feasible
from .mandates import DIVERT_ESCALATION
from .schemas import FallbackResult, Plan, PublicScenario


def decide(public: PublicScenario, plan_space: list[Plan], contracts: list, forecast,
           reason: str, contracts_missing: bool = False) -> FallbackResult:
    F = [] if contracts_missing else feasible(plan_space, contracts, public)
    non_div = [p for p in F if p.strategy != "DIVERT"]
    if non_div:
        ds = sorted({p.ground_delay_min for p in non_div})
        ok = [d for d in ds if forecast.p_exceeds(d + config.HOLD_BUDGET_MIN) <= config.DIVERT_RISK_TARGET]
        d = ok[0] if ok else ds[-1]
        branch = "R1_MIN_DELAY_MEETS_RISK" if ok else "R1_LARGEST_DELAY_RISK_NOT_MET"
        at_d = [p for p in non_div if p.ground_delay_min == d]
        plan = next((p for p in at_d if p.gate == "G1"), None) or sorted(
            at_d, key=lambda p: int(p.gate[1:]))[0]
        esc = [] if ok else [f"Divert risk {forecast.p_exceeds(d + config.HOLD_BUDGET_MIN):.0%} above "
                             f"{config.DIVERT_RISK_TARGET:.0%} target at the largest feasible delay"]
        return FallbackResult(plan=plan, branch=branch, reason=reason, escalations=esc)

    explanation = [] if contracts_missing else [describe(c) for c in explain_empty(plan_space, contracts, public)]
    div = next((p for p in F if p.strategy == "DIVERT"), None)
    if div is None and public.alternate:
        div = next((p for p in plan_space if p.strategy == "DIVERT"), None)
    if div is not None:
        return FallbackResult(plan=div, branch="R2_DIVERT", reason=reason,
                              escalations=[DIVERT_ESCALATION], explanation=explanation)
    hold = next(p for p in plan_space if p.plan_id == "HOLD-G1")
    return FallbackResult(plan=hold, branch="R2_NO_ALTERNATE_HOLD", reason=reason,
                          escalations=["No safe option found, human decision required"],
                          explanation=explanation)
