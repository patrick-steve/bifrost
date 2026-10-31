"""Dashboard server: a thin JSON API over the dn engine plus the static page.

    .venv/bin/uvicorn app.server:app --port 8000      then open http://localhost:8000
"""
from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dn import config, mandates
from dn.agents import PRESSURE_LINE, ScriptedBackend
from dn.baselines import fallback_only, fcfs, helper_contracts
from dn.consensus_log import ConsensusLog, read, verify
from dn.contracts import satisfied
from dn.coordinator import describe_plan
from dn.data_loader import load_rules_of_play, warm
from dn.forecast import for_scenario
from dn.plan_space import enumerate_plans
from dn.run import backends_for, run_scenario
from dn.scenario import build, showcase_index
from dn.simulate import simulate
from dn.time_utils import min_to_hhmm

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Bifrost")
_lock = threading.Lock()


@lru_cache(maxsize=128)
def scenario(index: int):
    return build(index)


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def scenario_list() -> list[dict]:
    path = config.RUNS_DIR / "scenarios.json"
    items = json.loads(path.read_text()) if path.exists() else []
    if not any(i["scenario_id"] == "showcase" for i in items):
        s = scenario(showcase_index())
        items.insert(0, {"index": showcase_index(), "scenario_id": "showcase", "kind": "showcase",
                         "label": f"{s.public.flight_number} {s.public.origin}-{s.public.destination} {s.public.date}"})
    return items


def _index_for(scenario_id: str) -> int:
    for i in scenario_list():
        if i["scenario_id"] == scenario_id:
            return i["index"]
    raise HTTPException(404, f"unknown scenario {scenario_id}")


# ------------------------------------------------------------------- reads
@app.get("/api/meta")
def meta():
    warm()
    return {"has_api_key": has_key(), "model": config.AGENT_MODEL, "scenarios": scenario_list(),
            "pressure_line": PRESSURE_LINE, "max_turns": config.MAX_TURNS}


def _private_summary(s) -> dict:
    a, g, t = s.airline_private, s.ground_private, s.atc_private
    arr = s.public.scheduled_arrival_min
    return {
        "ATC": [
            ["Booked arrivals in window", f"{len(t.booked_arrivals)} ({min_to_hhmm(t.window_start_min)} to {min_to_hhmm(t.window_end_min)})"],
            ["Heavy aircraft among them", str(sum(b.wake == 'Heavy' for b in t.booked_arrivals))],
            ["Arrival capacity in weather", f"{t.reduced_arrival_capacity_per_h:g} per hour"],
            ["Closed taxiway", t.taxiway_closed or "none"],
        ],
        "AIRLINE": [
            ["Holding fuel on arrival", f"{a.spare_fuel_min} min (reserve {a.final_reserve_min} min, budget {a.spare_fuel_min - a.final_reserve_min} min)"],
            ["Holding burn", f"{a.holding_burn_kg_per_h:,} kg per hour"],
            ["Crew duty already used", f"{a.crew_duty_used_h:.1f} h of 13 h"],
            ["Connecting passengers", f"{sum(c.passengers for c in a.connections)} on {len(a.connections)} flights"],
            ["Holding turbulence", a.holding_turbulence],
        ] + ([["Note", a.connections_note]] if a.connections_note else []),
        "GROUND": [
            ["Assigned gate", g.assigned_gate],
            ["Spare gates", ", ".join(x.gate for x in g.gates[1:]) or "none"],
            ["Gate G1 busy from", min_to_hhmm(g.gates[0].busy[0].start) if g.gates[0].busy else "free"],
            ["Minimum turnaround", f"{g.min_turnaround_min} min"],
            ["Ramp crew shift ends", min_to_hhmm(g.shift_end_min)],
        ],
    }


@app.get("/api/scenario/{scenario_id}")
def scenario_detail(scenario_id: str):
    s = scenario(_index_for(scenario_id))
    p = s.public
    f = for_scenario(p)
    hist = [int(x) for x in f.arr]
    ms = mandates.issue_all()
    return {
        "public": {
            **p.model_dump(mode="json"),
            "scheduled_departure": min_to_hhmm(p.scheduled_departure_min),
            "scheduled_arrival": min_to_hhmm(p.scheduled_arrival_min),
            "decision_time": min_to_hhmm(p.decision_time_min),
            "next_leg_departure": min_to_hhmm(p.next_leg.scheduled_departure_min) if p.next_leg else None,
        },
        "forecast": {**f.summary(), "label": f.label(), "sample": hist,
                     "hold_budget_min": config.HOLD_BUDGET_MIN},
        "mandates": {r: m.model_dump(mode="json") for r, m in ms.items()},
        "private": _private_summary(s),
        "plans": [{"plan_id": x.plan_id, "strategy": x.strategy, "gate": x.gate,
                   "ground_delay_min": x.ground_delay_min} for x in enumerate_plans(p)],
    }


# -------------------------------------------------------------------- runs
class RunRequest(BaseModel):
    scenario_id: str
    agents: str = "scripted"  # scripted | claude
    pressure: bool = False


def _run_id(scenario_id: str, agents: str, pressure: bool) -> str:
    return f"{scenario_id}{'-pressure' if pressure else ''}{'-claude' if agents == 'claude' else ''}"


def _run_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", run_id):
        raise HTTPException(400, "bad run id")
    return config.RUNS_DIR / "ui" / run_id


def _blocked_by(s, entries) -> dict:
    """For each plan: which party's PUBLISHED contracts rule it out, and in which turn (from the log)."""
    from pydantic import TypeAdapter

    from dn.schemas import Contract

    ta = TypeAdapter(Contract)
    published = []
    for e in entries:
        msg = (e.get("payload") or {}).get("message") or {}
        if e["event"] == "CONTRACTS":
            published += [(1, ta.validate_python(c)) for c in msg.get("contracts", [])]
        elif e["event"] == "RANKING":
            published += [(2, ta.validate_python(c)) for c in msg.get("extra_contracts", [])]
    out = {}
    for p in enumerate_plans(s.public):
        hits = [{"by": c.publisher, "turn": t, "type": c.type} for t, c in published if not satisfied(c, p, s.public)]
        uniq = {(h["by"], h["turn"]): h for h in hits}
        out[p.plan_id] = sorted(uniq.values(), key=lambda h: (h["turn"], h["by"]))
    return out


def _run_payload(run_id: str, scenario_id: str) -> dict:
    path = _run_dir(run_id) / "log.jsonl"
    if not path.exists():
        raise HTTPException(404, "no saved run for this scenario yet")
    entries = read(path)
    ok, seq, msg = verify(path)
    meta_path = _run_dir(run_id) / "meta.json"
    meta_ = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    s = scenario(_index_for(scenario_id))
    return {"run_id": run_id, "scenario_id": scenario_id, "entries": entries, "meta": meta_,
            "blocked_by": _blocked_by(s, entries),
            "verify": {"ok": ok, "seq": seq, "message": msg}}


@app.post("/api/run")
def run(req: RunRequest):
    if req.agents == "claude" and not has_key():
        raise HTTPException(400, "Claude agents need ANTHROPIC_API_KEY. Add it to .env and restart the server.")
    s = scenario(_index_for(req.scenario_id))
    backends = backends_for("claude" if req.agents == "claude" else "scripted")
    if req.pressure and req.agents != "claude":
        backends["AIRLINE"] = ScriptedBackend("concede")
    rid = _run_id(req.scenario_id, req.agents, req.pressure)
    with _lock:
        o, log, prompts = run_scenario(s, backends, run_dir=_run_dir(rid),
                                       injections={"AIRLINE": PRESSURE_LINE} if req.pressure else None)
    meta_ = {"agents": req.agents, "pressure": req.pressure, "wall_clock_s": o.wall_clock_s,
             "llm_calls": o.llm_calls, "status": o.status, "plan_id": o.plan.plan_id,
             "plan_text": describe_plan(o.plan),
             "model": config.AGENT_MODEL if req.agents == "claude" else "scripted (no AI)"}
    (_run_dir(rid) / "meta.json").write_text(json.dumps(meta_))
    return _run_payload(rid, req.scenario_id)


@app.get("/api/run/{run_id}")
def replay(run_id: str, scenario_id: str):
    return _run_payload(run_id, scenario_id)


class Approval(BaseModel):
    role: str  # controller | duty_manager | ramp_lead
    scenario_id: str


@app.post("/api/run/{run_id}/approve")
def approve(run_id: str, body: Approval):
    names = {"controller": "Arrival controller", "duty_manager": "Airline duty manager", "ramp_lead": "Ramp lead"}
    if body.role not in names:
        raise HTTPException(400, "unknown role")
    path = _run_dir(run_id) / "log.jsonl"
    if not path.exists():
        raise HTTPException(404, "run first")
    entries = read(path)
    final = next((e for e in reversed(entries) if e["event"] in ("DONE", "FALLBACK")), None)
    if final is None:
        raise HTTPException(409, "nothing to approve yet")
    if any(e["event"] == "HUMAN_APPROVAL" and e["payload"].get("role") == body.role for e in entries):
        raise HTTPException(409, f"{names[body.role]} already approved")
    with _lock:
        ConsensusLog(path).append(names[body.role], 4, "HUMAN_APPROVAL",
                                  {"role": body.role, "name": names[body.role],
                                   "plan_id": final["payload"]["plan"]["plan_id"]})
    return _run_payload(run_id, body.scenario_id)


@app.get("/api/reveal/{run_id}")
def reveal(run_id: str, scenario_id: str):
    s = scenario(_index_for(scenario_id))
    entries = read(_run_dir(run_id) / "log.jsonl")
    final = next(e for e in reversed(entries) if e["event"] in ("DONE", "FALLBACK"))
    from dn.schemas import Plan

    ours = Plan(**final["payload"]["plan"])
    fb = fallback_only(s)
    rows = {"ours": simulate(s, ours), "fcfs": simulate(s, fcfs(s)), "fallback_only": simulate(s, fb.plan)}
    plans = {"ours": ours.plan_id, "fcfs": fcfs(s).plan_id, "fallback_only": fb.plan.plan_id}
    return {"rows": rows, "plans": plans, "actual": rows["ours"]["actual_2015"],
            "true_delay_min": rows["ours"]["true_delay_min"], "disruption": s.public.disruption}


# ---------------------------------------------------------------- evaluation
def _eval_sets() -> list[str]:
    return [k for k in ("claude", "scripted") if (config.RUNS_DIR / f"eval_summary_{k}.csv").exists()]


@app.get("/api/eval")
def evaluation(which: str | None = None):
    sets = _eval_sets()
    if which in sets:
        md, csv = config.RUNS_DIR / f"eval_summary_{which}.md", config.RUNS_DIR / f"eval_summary_{which}.csv"
    elif sets:
        which = sets[0]
        md, csv = config.RUNS_DIR / f"eval_summary_{which}.md", config.RUNS_DIR / f"eval_summary_{which}.csv"
    else:
        md, csv = config.RUNS_DIR / "eval_summary.md", config.RUNS_DIR / "eval_summary.csv"
    if not csv.exists():
        return {"available": False}
    import pandas as pd

    df = pd.read_csv(csv)
    table = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    text = md.read_text() if md.exists() else ""
    integ = []
    m = re.search(r"## Integrity tests\n\n(.*?)\n\n", text, re.S)
    if m:
        for line in m.group(1).splitlines()[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 3:
                integ.append({"test": cells[0], "pass": cells[1] == "True", "detail": json.loads(cells[2] or "{}")})
    agents = "Claude agents" if "Agents: **Claude" in text else "Scripted agents (deterministic, no AI)"
    story = re.findall(r"^- (.*)$", text.split("## Story cases")[-1], re.M) if "## Story cases" in text else []
    head = re.search(r"Scenarios: (.*?)\. Agents", text)
    return {"available": True, "table": table, "integrity": integ, "agents": agents, "story": story,
            "sets": sets, "which": which,
            "scope": head.group(1) if head else ""}


@app.get("/api/rules")
def rules():
    df = load_rules_of_play()
    rows = [[str(v) for v in r] for r in df.itertuples(index=False)]
    plan = (config.ROOT / "PLAN.md").read_text()
    sec = plan.split("## 10.")[1].split("\n## ")[0]
    assumptions = [[c.strip() for c in line.strip("|").split("|")] for line in sec.splitlines()
                   if line.startswith("|") and not line.startswith("|---")][1:]
    return {"rules": rows, "rules_header": list(df.columns), "assumptions": assumptions}


@app.get("/")
def landing():
    return FileResponse(STATIC / "landing.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")
