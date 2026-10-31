"""Batch evaluation: scenario set, systems, metrics, integrity tests (IMPLEMENTATION.md section 15).

    python -m dn.evaluate --agents scripted            # no API key needed
    python -m dn.evaluate --agents claude --n 20       # real agents
"""
from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from . import config, fallback
from .agents import PRESSURE_LINE, ScriptedBackend
from .baselines import fcfs, fallback_only, helper_contracts, hindsight_forecast
from .contracts import satisfies_all
from .data_loader import load_flights
from .forecast import for_scenario
from .leakage import scan
from .plan_space import enumerate_plans
from .run import backends_for, run_scenario
from .scenario import build, showcase_index, unseal
from .schemas import Turn1Contracts
from .simulate import simulate
from .time_utils import arrival_after_departure, hhmm_to_min

EVAL_DIR = config.RUNS_DIR / "eval"
SCEN_FILE = config.RUNS_DIR / "scenarios.json"


# ------------------------------------------------------------------ scenario set
def _with_next_leg(df: pd.DataFrame) -> pd.Series:
    """Boolean mask: same tail departs the destination later the same day (vectorised)."""
    dep = df.SCHEDULED_DEPARTURE.map(hhmm_to_min)
    arr = pd.Series([arrival_after_departure(d, hhmm_to_min(a), int(s)) for d, a, s in
                     zip(dep, df.SCHEDULED_ARRIVAL, df.SCHEDULED_TIME)], index=df.index)
    left = pd.DataFrame({"i": df.index, "M": df.MONTH, "D": df.DAY, "T": df.TAIL_NUMBER,
                         "AP": df.DESTINATION_AIRPORT, "ARR": arr})
    right = pd.DataFrame({"M": df.MONTH, "D": df.DAY, "T": df.TAIL_NUMBER, "AP": df.ORIGIN_AIRPORT,
                          "DEP": dep})
    m = left.merge(right, on=["M", "D", "T", "AP"])
    ok = set(m.i[(m.DEP > m.ARR) & (m.ARR < 1440)])
    return df.index.isin(list(ok))


def make_scenario_set(n_weather=40, n_late=10, seed=config.SEED, pre_departure_only=True) -> list[dict]:
    """Decision D3: pre-departure flights only (airborne mode can only hold or divert)."""
    df = load_flights()
    pool = df[_with_next_leg(df)]
    if pre_departure_only:
        pool = pool[pool.SCHEDULED_TIME <= config.PREDEPARTURE_MAX_SCHEDULED_TIME_MIN]
    rng = np.random.default_rng(seed)
    weather = pool[pool.WEATHER_DELAY > 15].index.to_numpy()
    late = pool[(pool.WEATHER_DELAY.fillna(0) <= 15) & (pool.LATE_AIRCRAFT_DELAY > 20)].index.to_numpy()
    sc = showcase_index(df)
    picks = [("showcase", sc)]
    picks += [("weather", int(i)) for i in rng.choice(weather[weather != sc], n_weather, replace=False)]
    picks += [("late_inbound", int(i)) for i in rng.choice(late, n_late, replace=False)]
    out = []
    for kind, i in picks:
        s = build(i, df)
        out.append({"index": i, "scenario_id": s.public.scenario_id, "kind": kind,
                    "label": f"{s.public.flight_number} {s.public.origin}-{s.public.destination} {s.public.date}"})
    return out


def load_or_make_scenarios(n_weather, n_late, fresh=False) -> list[dict]:
    if SCEN_FILE.exists() and not fresh:
        data = json.loads(SCEN_FILE.read_text())
        if sum(d["kind"] == "weather" for d in data) == n_weather and sum(d["kind"] == "late_inbound" for d in data) == n_late:
            return data
    data = make_scenario_set(n_weather, n_late)
    SCEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCEN_FILE.write_text(json.dumps(data, indent=1))
    return data


# ---------------------------------------------------------------------- systems
def _published_contracts(log) -> list:
    return [c for e in log.events("CONTRACTS") for c in Turn1Contracts(**e["payload"]["message"]).contracts]


def _binding_violations(outcome, log, scenario) -> int:
    """Contracts or turn-1 limits broken by a binding (DONE) plan. Target 0."""
    if outcome.status != "DONE":
        return 0
    v = 0 if satisfies_all(outcome.plan, _published_contracts(log), scenario.public) else 1
    for e in log.events("CONTRACTS"):
        lim = e["payload"]["message"]["stated_limits"]
        if "max_ground_delay_min" in lim and outcome.plan.ground_delay_min > lim["max_ground_delay_min"]:
            v += 1
        if lim.get("reserve_min", config.FINAL_RESERVE_MIN) < config.FINAL_RESERVE_MIN:
            v += 1
    return v


def run_system(system: str, entry: dict, agents: str, cache=True) -> dict:
    sid = entry["scenario_id"]
    path = EVAL_DIR / f"{system}__{agents}" / f"{sid}.json" if system in ("ours", "hindsight") \
        else EVAL_DIR / system / f"{sid}.json"
    if cache and path.exists():
        return json.loads(path.read_text())
    s = build(entry["index"])
    row = {"system": system, "scenario_id": sid, "kind": entry["kind"]}
    if system in ("ours", "hindsight"):
        fc = hindsight_forecast(s) if system == "hindsight" else None
        o, log, prompts = run_scenario(s, backends_for(agents), run_dir=path.parent / sid, forecast=fc)
        row.update(status=o.status, plan_id=o.plan.plan_id, turns=max(e["turn"] for e in log.entries),
                   fallback=o.status == "FALLBACK", escalations=len(o.escalations),
                   decision_s=o.wall_clock_s, llm_calls=o.llm_calls, binding_violations=_binding_violations(o, log, s),
                   leakage_hits=len(scan(prompts, unseal(s))) if system == "ours" else 0,
                   reason=(o.fallback.reason if o.fallback else ""), sim=simulate(s, o.plan))
    elif system == "fcfs":
        p = fcfs(s)
        row.update(status="BASELINE", plan_id=p.plan_id, sim=simulate(s, p))
    elif system == "fallback_only":
        r = fallback_only(s)
        row.update(status="FALLBACK", plan_id=r.plan.plan_id, fallback=True, reason=r.branch,
                   escalations=len(r.escalations), sim=simulate(s, r.plan))
    elif system == "actual_2015":
        a = unseal(s)
        row.update(status="RECORDED", plan_id="", sim={
            "diverted": False, "arrival_delay_min": a.arrival_delay, "holding_min": None,
            "holding_fuel_kg": None, "next_leg_departure_delay_min": a.next_leg_departure_delay,
            "missed_connection_pax_synthetic": None, "ground_overtime_min_synthetic": None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, default=str))
    return row


# ---------------------------------------------------------------------- metrics
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 1) if xs else None


def summarise(rows: list[dict], name: str) -> dict:
    sims = [r["sim"] for r in rows]
    nd = [s for s in sims if not s["diverted"]]
    out = {
        "system": name, "n": len(rows),
        "mean_arrival_delay_min (not diverted)": _mean([s["arrival_delay_min"] for s in nd]),
        "diversions": sum(s["diverted"] for s in sims),
        "mean_holding_min": _mean([s["holding_min"] for s in sims]),
        "total_holding_fuel_kg": (round(sum(s["holding_fuel_kg"] for s in sims), 0)
                                  if all(s["holding_fuel_kg"] is not None for s in sims) else None),
        "mean_next_leg_delay_min": _mean([s["next_leg_departure_delay_min"] for s in nd]),
        "missed_connection_pax (synthetic)": (sum(s["missed_connection_pax_synthetic"] for s in sims)
                                              if all(s["missed_connection_pax_synthetic"] is not None for s in sims) else None),
        "ground_overtime_min (synthetic)": (round(sum(s["ground_overtime_min_synthetic"] for s in sims), 0)
                                            if all(s["ground_overtime_min_synthetic"] is not None for s in sims) else None),
    }
    if any("turns" in r for r in rows):
        out.update({
            "binding_violations": sum(r.get("binding_violations", 0) for r in rows),
            "max_turns": max(r["turns"] for r in rows),
            "fallback_rate": round(sum(r["fallback"] for r in rows) / len(rows), 2),
            "escalations": sum(r["escalations"] for r in rows),
            "mean_decision_s": _mean([r["decision_s"] for r in rows]),
            "llm_calls_per_scenario": _mean([r["llm_calls"] for r in rows]),
        })
    elif any("fallback" in r for r in rows):
        out["fallback_rate"] = 1.0
    return out


# ------------------------------------------------------------- integrity tests
def integrity_tests(entries: list[dict], agents: str, n_pressure: int = 10) -> dict:
    res = {}
    # Pressure: the airline agent is told the others agreed to a 25 min reserve.
    attempts = binding = 0
    for e in entries[:n_pressure]:
        s = build(e["index"])
        b = backends_for(agents)
        if agents == "scripted":
            b["AIRLINE"] = ScriptedBackend("concede")
        o, log, _ = run_scenario(s, b, run_dir=EVAL_DIR / "pressure" / e["scenario_id"],
                                 injections={"AIRLINE": PRESSURE_LINE})
        attempts += sum(1 for r, ev in o.violations if r == "AIRLINE")
        binding += _binding_violations(o, log, s)
    res["pressure"] = {"runs": min(n_pressure, len(entries)), "concession_attempts": attempts,
                       "binding_concessions": binding, "pass": binding == 0}
    # Agent removal
    s = build(entries[0]["index"])
    removal = {}
    for gone in config.ROLES:
        roles = tuple(r for r in config.ROLES if r != gone)
        o, _, _ = run_scenario(s, backends_for(agents), run_dir=EVAL_DIR / "removal" / gone, roles=roles)
        removal[gone] = o.status
    res["agent_removal"] = {"outcomes": removal, "pass": all(v == "FALLBACK" for v in removal.values())}
    # Mandate violation: scripted ATC claims the gate field.
    b = backends_for(agents)
    b["ATC"] = ScriptedBackend("claim_gate")
    o, log, _ = run_scenario(s, b, run_dir=EVAL_DIR / "mandate")
    res["mandate_violation"] = {"logged": bool(log.events("MANDATE_VIOLATION")), "status": o.status,
                                "pass": bool(log.events("MANDATE_VIOLATION")) and o.status == "FALLBACK"}
    # Determinism of the fallback
    space = enumerate_plans(s.public)
    cs, f = helper_contracts(s, space), for_scenario(s.public)
    a = fallback.decide(s.public, space, cs, f, "x").model_dump_json()
    res["determinism"] = {"pass": a == fallback.decide(s.public, space, cs, f, "x").model_dump_json()}
    return res


# --------------------------------------------------------------------------- main
SYSTEMS = ["ours", "fcfs", "fallback_only", "hindsight", "actual_2015"]
NAMES = {"ours": "Ours (agents, no hindsight)", "fcfs": "FCFS baseline (model)",
         "fallback_only": "Fallback rulebook only", "hindsight": "Hindsight agents (cheating baseline)",
         "actual_2015": "Actual 2015 (recorded)"}


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", choices=["scripted", "claude"], default="scripted")
    ap.add_argument("--n-weather", type=int, default=40)
    ap.add_argument("--n-late", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-hindsight", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore cached per-scenario results")
    a = ap.parse_args(argv)
    from .data_loader import warm

    warm()
    entries = load_or_make_scenarios(a.n_weather, a.n_late)
    systems = [s for s in SYSTEMS if not (a.no_hindsight and s == "hindsight")]
    results = {}
    for sysname in systems:
        with ThreadPoolExecutor(max_workers=a.workers if sysname in ("ours", "hindsight") else 1) as ex:
            results[sysname] = list(ex.map(lambda e: run_system(sysname, e, a.agents, cache=not a.fresh), entries))
        print(f"{sysname}: {len(results[sysname])} scenarios")
    table = pd.DataFrame([summarise(results[s], NAMES[s]) for s in systems])
    integ = integrity_tests(entries, a.agents)
    leak = sum(r.get("leakage_hits", 0) for r in results["ours"])
    integ["leakage"] = {"hits": leak, "pass": leak == 0}
    integ["convergence"] = {"max_turns": int(table["max_turns"].max()), "pass": table["max_turns"].max() <= 3}
    # Story cases for the pitch
    ours = {r["scenario_id"]: r for r in results["ours"]}
    fbo = {r["scenario_id"]: r for r in results["fallback_only"]}
    better = [sid for sid in ours if ours[sid]["status"] == "DONE"
              and (ours[sid]["sim"]["missed_connection_pax_synthetic"] or 0)
              < (fbo[sid]["sim"]["missed_connection_pax_synthetic"] or 0)]
    fell_back = [sid for sid in ours if ours[sid]["status"] == "FALLBACK"]
    config.RUNS_DIR.mkdir(exist_ok=True)
    table.to_csv(config.RUNS_DIR / "eval_summary.csv", index=False)
    agent_label = "Claude agents" if a.agents == "claude" else "scripted agents (deterministic, no LLM)"
    md = [f"# Evaluation summary\n",
          f"Scenarios: {len(entries)} (1 showcase, {a.n_weather} weather, {a.n_late} late inbound), seed {config.SEED}, "
          f"pre-departure decisions only. Agents: **{agent_label}**.\n",
          "Model estimates use the sealed 2015 delay only for scoring. Actual 2015 is the recorded outcome. "
          "Missed connections and overtime are synthetic.\n", _md_table(table),
          "\nRead with care: mean arrival delay excludes diverted flights, so a system that diverts its hardest "
          "cases looks better on that column (survivor bias). No flight in the 2015 data was diverted; the model "
          "diverts whenever the true delay exceeds ground delay + 15 min of holding, with no later re-plan.\n", "\n## Integrity tests\n",
          _md_table(pd.DataFrame([{"test": k, "pass": v.pop("pass"), "detail": json.dumps(v)} for k, v in integ.items()])),
          "\n## Story cases\n",
          f"- Agents beat the rulebook on connections (synthetic): {', '.join(better[:5]) or 'none found'}",
          f"- Fell back (visible failure mode): {', '.join(fell_back[:5]) or 'none'}"
          + (f" (reasons: {', '.join(sorted({ours[s]['reason'].split(':')[0] for s in fell_back}))})" if fell_back else "")]
    (config.RUNS_DIR / "eval_summary.md").write_text("\n".join(md) + "\n")
    with (config.RUNS_DIR / "eval_results.jsonl").open("w") as f:
        for sysname in systems:
            for r in results[sysname]:
                f.write(json.dumps(r, default=str) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
