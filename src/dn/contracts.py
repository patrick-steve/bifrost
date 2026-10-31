"""Constraint contracts: evaluation, feasibility, tighten-only, explanations, per-role helpers."""
from __future__ import annotations

from . import config
from .data_loader import wake_minutes
from .schemas import (
    AvailableArrivalMinutes, ForbidStrategy, GateChangeNotice, GateWindow, GateWindowFree,
    LatestArrival, MaxGroundDelay, Plan, PublicScenario,
)


def satisfied(c, plan: Plan, public: PublicScenario) -> bool:
    div = plan.strategy == "DIVERT"
    if isinstance(c, AvailableArrivalMinutes):
        return div or plan.target_arrival_min in set(c.minutes)
    if isinstance(c, MaxGroundDelay):
        return plan.ground_delay_min <= c.minutes
    if isinstance(c, ForbidStrategy):
        return plan.strategy != c.strategy
    if isinstance(c, GateWindowFree):
        if div:
            return True
        start = plan.target_arrival_min
        end = start + public.destination_airport.min_turnaround_min
        return any(w.gate == plan.gate and w.free_from <= start and end <= w.free_to for w in c.windows)
    if isinstance(c, GateChangeNotice):
        return div or plan.gate == "G1" or plan.target_arrival_min - public.decision_time_min >= c.minutes
    if isinstance(c, LatestArrival):
        return (not div) and plan.target_arrival_min <= c.minute
    raise TypeError(f"unknown contract {type(c).__name__}")


def satisfies_all(plan, contracts, public) -> bool:
    return all(satisfied(c, plan, public) for c in contracts)


def feasible(plan_space: list[Plan], contracts, public) -> list[Plan]:
    return [p for p in plan_space if satisfies_all(p, contracts, public)]


def violated_by(plan, contracts, public) -> list:
    return [c for c in contracts if not satisfied(c, plan, public)]


def is_tightening(old, new, plan_space, public) -> bool:
    """True if every plan allowed by `new` was already allowed by `old`."""
    old_ids = {p.plan_id for p in feasible(plan_space, old, public)}
    return all(p.plan_id in old_ids for p in feasible(plan_space, new, public))


def explain_empty(plan_space, contracts, public) -> list:
    """Smallest (greedy) set of contracts whose intersection is empty; [] if not empty."""
    chosen = []
    for c in contracts:
        chosen.append(c)
        if not feasible(plan_space, chosen, public):
            break
    else:
        return []
    for c in list(chosen):
        trial = [x for x in chosen if x is not c]
        if trial and not feasible(plan_space, trial, public):
            chosen = trial
    return chosen


def describe(c) -> str:
    d = c.model_dump(exclude={"reason", "publisher"})
    t = d.pop("type")
    if t == "available_arrival_minutes":
        return f"{c.publisher}: arrival only at {len(c.minutes)} listed minutes"
    if t == "gate_window_free":
        return f"{c.publisher}: gate free windows for {len({w.gate for w in c.windows})} gates"
    return f"{c.publisher}: {t} {d}"


# ------------------------------------------------------------------ helpers
def atc_helper(public: PublicScenario, atc, plan_space) -> list:
    """Candidate target minutes meeting wake spacing both sides and the reduced hourly capacity."""
    ours = public.wake_category
    booked = sorted(atc.booked_arrivals, key=lambda b: b.minute)
    targets = sorted({p.target_arrival_min for p in plan_space if p.target_arrival_min is not None})
    def spaced(m: int) -> bool:
        leaders = [b for b in booked if b.minute <= m]
        followers = [b for b in booked if b.minute >= m]
        if leaders and m - leaders[-1].minute < wake_minutes(leaders[-1].wake, ours):
            return False
        return not (followers and followers[0].minute - m < wake_minutes(ours, followers[0].wake))

    ok = []
    for t in targets:
        # A target is the start of a 5-minute slot; ATC sequences the aircraft to any spaced minute in it.
        if not any(spaced(m) for m in range(t, t + config.GROUND_DELAY_STEP_MIN)):
            continue
        if sum(t - 30 <= b.minute < t + 30 for b in booked) + 1 > atc.reduced_arrival_capacity_per_h:
            continue
        ok.append(t)
    return [AvailableArrivalMinutes(publisher="ATC", minutes=ok,
                                    reason="Wake spacing and reduced weather capacity")]


def airline_helper(public: PublicScenario, airline, plan_space) -> list:
    from .domain_costs import duty_after_next_leg

    best = -1
    for d in sorted({p.ground_delay_min for p in plan_space if p.strategy != "DIVERT"}):
        arr = public.scheduled_arrival_min + d + config.HOLD_BUDGET_MIN
        duty = duty_after_next_leg(airline.crew_duty_used_h, public.decision_time_min, arr,
                                   public.destination_airport.min_turnaround_min, public.next_leg)
        if duty <= config.CREW_MAX_DUTY_H:
            best = d
    out = []
    if best >= 0:
        out.append(MaxGroundDelay(publisher="AIRLINE", minutes=best,
                                  reason="Crew duty limit 13 h including next leg"))
    else:  # no ground delay keeps the crew legal: only diversion remains
        out.append(ForbidStrategy(publisher="AIRLINE", strategy="GROUND_DELAY", reason="Crew duty limit"))
        out.append(ForbidStrategy(publisher="AIRLINE", strategy="HOLD", reason="Crew duty limit"))
    return out


def ground_helper(public: PublicScenario, ground, plan_space) -> list:
    lo = public.scheduled_arrival_min - 60
    hi = public.scheduled_arrival_min + config.GROUND_DELAY_MAX_MIN + ground.min_turnaround_min + 240
    windows = []
    for g in ground.gates:
        cur = lo
        for b in sorted(g.busy, key=lambda b: b.start):
            if b.start > cur:
                windows.append(GateWindow(gate=g.gate, free_from=cur, free_to=b.start))
            cur = max(cur, b.end)
        if cur < hi:
            windows.append(GateWindow(gate=g.gate, free_from=cur, free_to=hi))
    return [GateWindowFree(publisher="GROUND", windows=windows, reason="Gate occupancy"),
            GateChangeNotice(publisher="GROUND", minutes=config.GATE_CHANGE_NOTICE_MIN,
                             reason="Gate change notice 20 min")]


HELPERS = {"ATC": atc_helper, "AIRLINE": airline_helper, "GROUND": ground_helper}
