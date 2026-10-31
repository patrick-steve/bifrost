"""Run one scenario end to end.

    python -m dn.run --showcase --scripted        # no LLM, no API key
    python -m dn.run --showcase                   # Claude agents (needs ANTHROPIC_API_KEY)
    python -m dn.run --row 1234 --pressure
"""
from __future__ import annotations

import argparse
import json
import shutil

from . import config, mandates
from .agents import PRESSURE_LINE, ClaudeBackend, ScriptedBackend, make_agents
from .consensus_log import ConsensusLog, canonical_json, verify
from .coordinator import Coordinator
from .forecast import for_scenario
from .plan_space import enumerate_plans
from .scenario import build, showcase_index


def run_scenario(scenario, backends: dict, run_dir=None, forecast=None, injections=None,
                 roles=config.ROLES, fresh=True):
    run_dir = run_dir or config.RUNS_DIR / scenario.public.scenario_id
    if fresh and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    forecast = forecast or for_scenario(scenario.public)
    space = enumerate_plans(scenario.public)
    ms = mandates.issue_all()
    prompts: list = []
    agents = make_agents(scenario, ms, forecast, space, backends, prompt_log=prompts,
                         injections=injections, roles=roles)
    log = ConsensusLog(run_dir / "log.jsonl")
    outcome = Coordinator(scenario.for_coordinator(), forecast, space, ms, agents, log).run()
    with (run_dir / "prompts.jsonl").open("w") as f:
        for p in prompts:
            f.write(canonical_json(p) + "\n")
    return outcome, log, prompts


def backends_for(kind: str) -> dict:
    if kind == "scripted":
        return {r: ScriptedBackend() for r in config.ROLES}
    b = ClaudeBackend()
    return {r: b for r in config.ROLES}


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--showcase", action="store_true")
    g.add_argument("--row", type=int)
    ap.add_argument("--scripted", action="store_true", help="deterministic agents, no LLM")
    ap.add_argument("--pressure", action="store_true", help="inject the pressure line into the airline agent")
    a = ap.parse_args(argv)
    sc = build(a.row if a.row is not None else showcase_index())
    inj = {"AIRLINE": PRESSURE_LINE} if a.pressure else None
    backends = backends_for("scripted" if a.scripted else "claude")
    if a.pressure and a.scripted:
        backends["AIRLINE"] = ScriptedBackend("concede")
    outcome, log, _ = run_scenario(sc, backends, injections=inj)
    from .simulate import simulate

    print(json.dumps({"status": outcome.status, "plan": outcome.plan.plan_id,
                      "feasible_sizes": outcome.feasible_sizes, "escalations": outcome.escalations,
                      "violations": outcome.violations, "llm_calls": outcome.llm_calls,
                      "summary": outcome.recommended.summary if outcome.recommended else outcome.fallback.reason,
                      "sim": simulate(sc, outcome.plan)}, indent=2, default=str))
    print(verify(log.path)[2])


if __name__ == "__main__":
    main()
