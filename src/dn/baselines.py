"""Baselines: FCFS, fallback-only, and the hindsight forecast hook (IMPLEMENTATION.md section 15)."""
from __future__ import annotations

from . import contracts as ct
from . import fallback
from .forecast import for_scenario, point_mass
from .plan_space import enumerate_plans
from .scenario import Scenario
from .simulate import true_delay


def helper_contracts(scenario: Scenario, plan_space) -> list:
    out = []
    for role, view in (("ATC", scenario.atc_private), ("AIRLINE", scenario.airline_private),
                       ("GROUND", scenario.ground_private)):
        out += ct.HELPERS[role](scenario.public, view, plan_space)
    return out


def fcfs(scenario: Scenario):
    """Today without coordination: depart on time, hold up to 15, divert; keep G1 if free."""
    pub = scenario.public
    space = enumerate_plans(pub)
    gate_c = ct.ground_helper(pub, scenario.ground_private, space)[0]
    holds = [p for p in space if p.strategy == "HOLD"]
    return next((p for p in holds if ct.satisfied(gate_c, p, pub)), holds[0])


def fallback_only(scenario: Scenario):
    space = enumerate_plans(scenario.public)
    return fallback.decide(scenario.public, space, helper_contracts(scenario, space),
                           for_scenario(scenario.public), reason="FALLBACK_ONLY_BASELINE")


def hindsight_forecast(scenario: Scenario):
    """Cheating baseline: the forecast is replaced by the true delay."""
    return point_mass(true_delay(scenario), airport=scenario.public.destination)
