"""Outcome of a final plan under the sealed real 2015 delay (IMPLEMENTATION.md section 14)."""
from __future__ import annotations

import numpy as np

from .domain_costs import plan_outcomes
from .scenario import Scenario, unseal


def true_delay(scenario: Scenario) -> float:
    s = unseal(scenario)
    return s.weather_delay if scenario.public.disruption == "weather_at_destination" else s.late_aircraft_delay


def simulate(scenario: Scenario, plan) -> dict:
    pub, s = scenario.public, unseal(scenario)
    w = true_delay(scenario)
    o = plan_outcomes(plan, np.array([w]), pub.disruption)
    diverted = bool(o["diverted"][0])
    hold = float(o["hold"][0])
    arr_delay = None if diverted else float(o["arr_delay"][0])
    burn = scenario.airline_private.holding_burn_kg_per_h
    gp = scenario.ground_private
    next_leg_delay, overtime, missed = None, 0.0, 0
    if diverted:
        missed = sum(c.passengers for c in scenario.airline_private.connections)
    else:
        arrival = pub.scheduled_arrival_min + arr_delay
        done = arrival + gp.min_turnaround_min
        if gp.next_leg_departure_min is not None:
            next_leg_delay = max(0.0, done - gp.next_leg_departure_min)
        overtime = max(0.0, done - gp.shift_end_min)
        missed = sum(c.passengers for c in scenario.airline_private.connections
                     if arrival > c.latest_arrival_min)
    return {
        "plan_id": plan.plan_id,
        "true_delay_min": w,
        "diverted": diverted,
        "arrival_delay_min": arr_delay,
        "holding_min": hold,
        "holding_fuel_kg": round(hold / 60 * burn, 1),
        "next_leg_departure_delay_min": next_leg_delay,
        "next_leg_status": ("aircraft unavailable" if diverted and pub.next_leg else
                            None if pub.next_leg is None else "operates"),
        "missed_connection_pax_synthetic": int(missed),
        "ground_overtime_min_synthetic": float(overtime),
        "actual_2015": {"arrival_delay_min": s.arrival_delay,
                        "next_leg_departure_delay_min": s.next_leg_departure_delay},
        "label": "model estimate vs recorded 2015 outcome",
    }
