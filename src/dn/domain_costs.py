"""Deterministic cost tools (IMPLEMENTATION.md section 9).

`plan_outcomes` uses only public plan fields and a forecast sample, so the coordinator and
fallback may use it too. The per-role cost functions take that role's private state.
"""
from __future__ import annotations

import numpy as np

from . import config


def plan_outcomes(plan, w: np.ndarray, disruption: str) -> dict:
    """Vectorised model outcome for each sampled delay w.

    weather: W <= d -> arrive at d; d < W <= d+15 -> hold W-d; W > d+15 -> divert after 15 min hold.
    late inbound: the aircraft leaves when it is ready, arrival delay = max(W, d), no hold, no divert.
    """
    w = np.asarray(w, dtype=float)
    if plan.strategy == "DIVERT":
        return {"diverted": np.ones_like(w, bool), "hold": np.zeros_like(w),
                "arr_delay": np.full_like(w, np.nan)}
    d = plan.ground_delay_min
    if disruption == "late_inbound_aircraft":
        return {"diverted": np.zeros_like(w, bool), "hold": np.zeros_like(w), "arr_delay": np.maximum(w, d)}
    diverted = w > d + plan.hold_limit_min
    hold = np.where(diverted, plan.hold_limit_min, np.clip(w - d, 0, plan.hold_limit_min))
    arr = np.where(diverted, np.nan, np.maximum(w, d))
    return {"diverted": diverted, "hold": hold, "arr_delay": arr}


def _nanmean(x) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.nanmean(x)) if np.any(~np.isnan(x)) else float("nan")


def public_score(plan, forecast, disruption: str) -> tuple[float, float]:
    """(p_divert, expected arrival delay if not diverted). Lower is better. Public data only."""
    o = plan_outcomes(plan, forecast.arr, disruption)
    ead = _nanmean(o["arr_delay"])
    return float(o["diverted"].mean()), (ead if ead == ead else float("inf"))


def duty_after_next_leg(duty_used_h, decision_time_min, arrival_min, turnaround_min, next_leg) -> float:
    """Crew duty (h) at the end of the next leg; crew follows the aircraft."""
    if next_leg is None:
        end = arrival_min
    else:
        dep = max(next_leg.scheduled_departure_min, arrival_min + turnaround_min)
        end = dep + (next_leg.scheduled_time_min or config.DEFAULT_NEXT_LEG_BLOCK_MIN)
    return duty_used_h + (end - decision_time_min) / 60


# ----------------------------------------------------------------------- ATC
def atc_holding_load(plan, forecast, public, atc_private) -> dict:
    o = plan_outcomes(plan, forecast.arr, public.disruption)
    displaced = 0
    if plan.target_arrival_min is not None:
        displaced = sum(abs(b.minute - plan.target_arrival_min) <= 2 for b in atc_private.booked_arrivals)
    exp_hold = float(o["hold"].mean())
    return {"expected_holding_min": round(exp_hold, 2), "displaced_arrivals": int(displaced),
            "holding_load": round(exp_hold + displaced, 2)}


# ------------------------------------------------------------------- airline
def airline_expected_cost(plan, forecast, public, airline_private) -> dict:
    o = plan_outcomes(plan, forecast.arr, public.disruption)
    arr_abs = public.scheduled_arrival_min + o["arr_delay"]  # nan when diverted
    missed = np.zeros(len(arr_abs))
    for c in airline_private.connections:
        missed += np.where(np.isnan(arr_abs) | (arr_abs > c.latest_arrival_min), c.passengers, 0)
    exp_hold = float(o["hold"].mean())
    duty = None
    breach = False
    if plan.strategy != "DIVERT":
        worst_arr = public.scheduled_arrival_min + plan.ground_delay_min + plan.hold_limit_min
        duty = duty_after_next_leg(airline_private.crew_duty_used_h, public.decision_time_min, worst_arr,
                                   public.destination_airport.min_turnaround_min, public.next_leg)
        breach = duty > config.CREW_MAX_DUTY_H
    return {
        "p_divert": round(float(o["diverted"].mean()), 3),
        "expected_holding_min": round(exp_hold, 2),
        "expected_holding_fuel_kg": round(exp_hold / 60 * airline_private.holding_burn_kg_per_h, 1),
        "expected_arrival_delay_min": round(_nanmean(o["arr_delay"]), 1),
        "expected_missed_connection_pax": round(float(missed.mean()), 2),
        "worst_case_duty_h": None if duty is None else round(duty, 2),
        "duty_breach": bool(breach),
        "holding_turbulence": airline_private.holding_turbulence,
    }


# -------------------------------------------------------------------- ground
def ground_expected_cost(plan, forecast, public, ground_private) -> dict:
    o = plan_outcomes(plan, forecast.arr, public.disruption)
    done = public.scheduled_arrival_min + o["arr_delay"] + ground_private.min_turnaround_min
    nl = 0.0
    if ground_private.next_leg_departure_min is not None:
        nl = _nanmean(np.maximum(0, done - ground_private.next_leg_departure_min))
    ot = _nanmean(np.maximum(0, done - ground_private.shift_end_min))
    return {
        "gate_change": plan.gate not in (None, ground_private.assigned_gate),
        "expected_next_leg_delay_min": round(nl, 1) if nl == nl else None,
        "expected_overtime_min": round(ot, 1) if ot == ot else None,
        "worst_case_overtime_min": (None if plan.strategy == "DIVERT" else max(
            0, plan.target_arrival_min + plan.hold_limit_min + ground_private.min_turnaround_min
            - ground_private.shift_end_min)),
    }
