"""Agent factory: each agent gets only its own view of the scenario."""
from __future__ import annotations

from .base import AgentError, ClaudeBackend, DomainAgent, PRESSURE_LINE, ScriptedBackend  # noqa: F401


def make_agents(scenario, mandates, forecast, plan_space, backends: dict, prompt_log=None,
                injections: dict | None = None, roles=("ATC", "AIRLINE", "GROUND")) -> dict:
    injections = injections or {}
    return {r: DomainAgent(r, scenario.for_agent(r), mandates[r], forecast, plan_space, backends[r],
                           prompt_log=prompt_log, injection=injections.get(r))
            for r in roles}
