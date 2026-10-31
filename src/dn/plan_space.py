"""Public plan enumeration (IMPLEMENTATION.md section 6). Needs no private data."""
from __future__ import annotations

from . import config
from .schemas import Plan, PublicScenario


def gate_ids(public: PublicScenario) -> list[str]:
    return ["G1"] + [f"S{i}" for i in range(1, public.destination_airport.spare_gates_at_any_time + 1)]


def enumerate_plans(public: PublicScenario) -> list[Plan]:
    arr = public.scheduled_arrival_min
    plans: list[Plan] = []
    delays = []
    if public.decision_mode == "pre_departure":
        delays = list(range(config.GROUND_DELAY_STEP_MIN, config.GROUND_DELAY_MAX_MIN + 1,
                            config.GROUND_DELAY_STEP_MIN))
    for gate in gate_ids(public):
        for d in delays:
            plans.append(Plan(plan_id=f"GD{d}-{gate}", strategy="GROUND_DELAY", ground_delay_min=d,
                              target_arrival_min=arr + d, gate=gate, hold_limit_min=config.HOLD_BUDGET_MIN))
        plans.append(Plan(plan_id=f"HOLD-{gate}", strategy="HOLD", ground_delay_min=0,
                          target_arrival_min=arr, gate=gate, hold_limit_min=config.HOLD_BUDGET_MIN))
    if public.alternate:
        plans.append(Plan(plan_id=f"DIV-{public.alternate}", strategy="DIVERT"))
    return plans


def by_id(plans: list[Plan]) -> dict[str, Plan]:
    return {p.plan_id: p for p in plans}
