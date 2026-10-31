"""Decision negotiation demo UI (IMPLEMENTATION.md section 16).

    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dn import config, mandates
from dn.agents import PRESSURE_LINE, ScriptedBackend
from dn.baselines import fallback_only, fcfs
from dn.consensus_log import ConsensusLog, read, verify
from dn.coordinator import describe_plan
from dn.data_loader import load_rules_of_play
from dn.forecast import for_scenario
from dn.run import backends_for, run_scenario
from dn.scenario import build, showcase_index
from dn.schemas import Event, Plan
from dn.simulate import simulate
from dn.time_utils import min_to_hhmm

st.set_page_config(page_title="Disruption Negotiation", layout="wide")

ROLE_TITLE = {"ATC": "ATC (air navigation)", "AIRLINE": "Airline (operations control)",
              "GROUND": "Ground (handling)"}
HUMANS = [("Controller", "ATC"), ("Airline duty manager", "AIRLINE"), ("Ramp lead", "GROUND")]
VIOLATIONS = {Event.SCHEMA_REJECT.value, Event.MANDATE_VIOLATION.value,
              Event.SELF_CONTRADICTION.value, Event.LOOSENING_ATTEMPT.value}
LIMIT_TEXT = {"hold_limit_min": "Hold at most {v:g} min",
              "reserve_min": "Final reserve at least {v:g} min",
              "max_ground_delay_min": "Ground delay at most {v:g} min"}
SYN = ":gray-badge[synthetic]"


def clean(s) -> str:
    return str(s).replace("\u2014", "-")


# --------------------------------------------------------------------------- data
@st.cache_resource(show_spinner="Loading flight data")
def get_showcase_index() -> int:
    from dn.data_loader import warm

    warm()
    return showcase_index()


@st.cache_resource(show_spinner="Building scenario")
def get_scenario(index: int):
    return build(index)


@st.cache_resource
def get_forecast(index: int):
    return for_scenario(get_scenario(index).public)


def scenario_options() -> list[tuple[str, int]]:
    opts = [("showcase (N767SK, DAY to ORD, 15 Jul 2015)", get_showcase_index())]
    path = config.RUNS_DIR / "scenarios.json"
    if path.exists():
        try:
            for s in json.loads(path.read_text()):
                idx = int(s["index"])
                if all(idx != i for _, i in opts):
                    opts.append((f"{s.get('scenario_id', f'r{idx}')}", idx))
        except Exception as e:  # malformed file: keep the showcase usable
            st.sidebar.caption(f"Could not read scenarios.json: {e}")
    return opts


@st.cache_data
def assumptions_table() -> pd.DataFrame | None:
    plan = config.ROOT / "PLAN.md"
    if not plan.exists():
        return None
    rows, inside = [], False
    for line in plan.read_text().splitlines():
        if line.startswith("## "):
            inside = line.startswith("## 10.")
            continue
        if inside and line.startswith("|"):
            cells = [clean(c.strip()) for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
    return pd.DataFrame(rows[1:], columns=rows[0]) if len(rows) > 1 else None


# ------------------------------------------------------------------------ wording
def hhmm(m) -> str:
    return "n/a" if m is None else min_to_hhmm(int(m))


def contract_text(c: dict) -> str:
    t = c.get("type")
    if t == "available_arrival_minutes":
        mins = c.get("minutes", [])
        span = f" between {hhmm(min(mins))} and {hhmm(max(mins))}" if mins else ""
        txt = f"{len(mins)} arrival slots available{span}"
    elif t == "max_ground_delay":
        txt = f"Ground delay at most {c['minutes']} min"
    elif t == "forbid_strategy":
        txt = f"No {c['strategy'].replace('_', ' ').lower()} plans"
    elif t == "gate_window_free":
        ws = ", ".join(f"{w['gate']} {hhmm(w['free_from'])} to {hhmm(w['free_to'])}" for w in c["windows"])
        txt = f"Gates free: {ws}"
    elif t == "gate_change_notice":
        txt = f"Gate changes need {c['minutes']} min notice"
    elif t == "latest_arrival":
        txt = f"Arrive no later than {hhmm(c['minute'])}"
    else:
        txt = json.dumps(c)
    return txt + (f" (why: {c['reason']})" if c.get("reason") else "")


def limits_text(limits: dict) -> str:
    return "; ".join(LIMIT_TEXT.get(k, k + " {v:g}").format(v=v) for k, v in limits.items())


def plan_from(d: dict | None) -> Plan | None:
    return Plan(**d) if d else None


# ------------------------------------------------------------------------ sidebar
st.sidebar.title("Disruption negotiation")
opts = scenario_options()
label = st.sidebar.selectbox("Scenario", [o[0] for o in opts], index=0)
index = dict(opts)[label]
sc = get_scenario(index)
pub = sc.public
log_path = config.RUNS_DIR / pub.scenario_id / "log.jsonl"

has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
backend_choice = st.sidebar.radio(
    "Agent backend", ["Scripted (no AI)", "Claude agents"], index=0,
    captions=["Deterministic agents using their own cost tools",
              "Live LLM agents" if has_key else "Disabled: ANTHROPIC_API_KEY is not set"],
)
if backend_choice == "Claude agents" and not has_key:
    st.sidebar.warning("Claude agents need ANTHROPIC_API_KEY. Using scripted agents.")
    backend_choice = "Scripted (no AI)"
pressure = st.sidebar.checkbox("Pressure test", help=f'Injects into the Airline agent: "{PRESSURE_LINE}"')
c1, c2 = st.sidebar.columns(2)
run_clicked = c1.button("Run", type="primary", width="stretch")
replay_clicked = c2.button("Replay saved log", width="stretch")
st.sidebar.caption("Public facts come from the 2015 flights file. Private operator states are synthetic, "
                   "seeded per scenario (seed 42).")

if run_clicked:
    kind = "claude" if backend_choice == "Claude agents" else "scripted"
    with st.spinner("Agents negotiating (3 turns max)"):
        try:
            backends = backends_for(kind)
            if pressure and kind == "scripted":
                backends["AIRLINE"] = ScriptedBackend("concede")
            run_dir = config.RUNS_DIR / (sc.public.scenario_id + ("-pressure" if pressure else ""))
            outcome, log, _ = run_scenario(sc, backends, run_dir=run_dir, forecast=get_forecast(index),
                                           injections={"AIRLINE": PRESSURE_LINE} if pressure else None)
            st.session_state.shown = {"index": index, "path": str(log.path), "source": "run",
                                      "meta": {"backend": backend_choice, "pressure": pressure,
                                               "wall_clock_s": outcome.wall_clock_s,
                                               "llm_calls": outcome.llm_calls}}
        except Exception as e:
            st.session_state.pop("shown", None)
            st.error(f"Run failed: {type(e).__name__}: {e}")
if replay_clicked:
    if log_path.exists():
        st.session_state.shown = {"index": index, "path": str(log_path), "source": "replay", "meta": {}}
    else:
        st.session_state.pop("shown", None)
        st.warning(f"No saved log at {log_path}. Press Run first.")

shown = st.session_state.get("shown")
if shown and shown["index"] != index:
    shown = None
entries: list[dict] = read(shown["path"]) if shown and Path(shown["path"]).exists() else []


def ev(name: str) -> list[dict]:
    return [e for e in entries if e["event"] == name]


# --------------------------------------------------------------------------- tabs
tab_neg, tab_eval, tab_rules, tab_log = st.tabs(["Negotiation", "Evaluation", "Rules", "Log"])

with tab_neg:
    # ---- disruption card
    fc = get_forecast(index)
    q = fc.quantiles()
    with st.container(border=True):
        st.subheader(f"{pub.flight_number} ({pub.tail}): {pub.origin} to {pub.destination}, {pub.date}")
        m = st.columns(4)
        m[0].metric("Scheduled departure", hhmm(pub.scheduled_departure_min))
        m[1].metric("Scheduled arrival", hhmm(pub.scheduled_arrival_min))
        m[2].metric("Decision time", hhmm(pub.decision_time_min),
                    help=pub.decision_mode.replace("_", " "))
        m[3].metric("Disruption", "Weather at destination" if pub.disruption == "weather_at_destination"
                    else "Late inbound aircraft")
        nl = pub.next_leg
        st.markdown(
            f"**Destination:** {pub.destination_airport.name} ({pub.destination_airport.size_class}).  "
            f"**Alternate:** {pub.alternate or 'none'}.  **Wake:** {pub.wake_category}.  "
            f"**Decision mode:** {pub.decision_mode.replace('_', ' ')}.  \n"
            + (f"**Next leg (same aircraft):** {nl.flight_number} to {nl.destination}, departs "
               f"{hhmm(nl.scheduled_departure_min)}." if nl else "**Next leg:** none found in the data.")
        )
        st.markdown(f"**{fc.label()}.** Delay quantiles (min): "
                    + ", ".join(f"{k} {v:.0f}" for k, v in q.items()))
        if shown:
            meta = shown.get("meta") or {}
            bits = [f"Source: {'live run' if shown['source'] == 'run' else 'replayed log'}"]
            if meta:
                bits += [f"backend: {meta['backend']}", f"pressure test: {'on' if meta['pressure'] else 'off'}",
                         f"{meta['wall_clock_s']} s", f"{meta['llm_calls']} agent calls"]
            st.caption(", ".join(bits))

    if not entries:
        st.info("Press **Run** to negotiate this scenario, or **Replay saved log** to load the last run.")

    # ---- three agent columns
    ms = {e["actor"]: e["payload"] for e in ev("MANDATE_ISSUED")} or \
        {r: m.model_dump(mode="json") for r, m in mandates.issue_all().items()}
    cols = st.columns(3)
    for col, role in zip(cols, config.ROLES):
        with col:
            st.markdown(f"### {ROLE_TITLE[role]}")
            md = ms.get(role, {})
            with st.container(border=True):
                st.markdown(f"**Signed mandate** ({md.get('organisation', '')})  \n"
                            f"May set: {', '.join(md.get('may_set', [])) or 'nothing'}  \n"
                            f"May forbid: {', '.join(md.get('may_forbid', [])) or 'nothing'}  \n"
                            f"May not: {', '.join(md.get('may_not', []))}")
            with st.expander("Operator view, synthetic"):
                st.markdown(SYN)
                if role == "ATC":
                    p = sc.atc_private
                    st.markdown(f"- {len(p.booked_arrivals)} booked arrivals in window "
                                f"{hhmm(p.window_start_min)} to {hhmm(p.window_end_min)} (synthetic)\n"
                                f"- Reduced arrival capacity {p.reduced_arrival_capacity_per_h:g}/h (synthetic)\n"
                                f"- Taxiway closed: {p.taxiway_closed or 'none'} (synthetic)")
                elif role == "AIRLINE":
                    p = sc.airline_private
                    conns = "\n".join(f"  - {c.label}: {c.passengers} pax, latest arrival "
                                      f"{hhmm(c.latest_arrival_min)}" for c in p.connections) or "  - none"
                    st.markdown(f"- Spare fuel {p.spare_fuel_min} min, final reserve {p.final_reserve_min} min\n"
                                f"- Holding burn {p.holding_burn_kg_per_h} kg/h\n"
                                f"- Crew duty used {p.crew_duty_used_h:.2f} h (synthetic)\n"
                                f"- Holding turbulence: {p.holding_turbulence} (synthetic)\n"
                                f"- Connections (synthetic):\n{conns}"
                                + (f"\n- Note: {p.connections_note} (synthetic)" if p.connections_note else ""))
                else:
                    p = sc.ground_private
                    gates = "\n".join(f"  - {g.gate}: busy " + (", ".join(
                        f"{hhmm(b.start)} to {hhmm(b.end)}" for b in g.busy) or "never") for g in p.gates)
                    st.markdown(f"- Assigned gate {p.assigned_gate}, turnaround {p.min_turnaround_min} min\n"
                                f"- Shift ends {hhmm(p.shift_end_min)} (synthetic)\n"
                                f"- Next leg departs {hhmm(p.next_leg_departure_min)}\n"
                                f"- Gate occupancy (synthetic):\n{gates}")

            for e in entries:
                if e["turn"] not in (1, 2, 3):
                    continue
                pl = e["payload"]
                mine_msg = e["actor"] == role and "message" in pl
                if mine_msg:
                    msg = pl["message"]
                    with st.container(border=True):
                        if e["event"] == Event.CONTRACTS.value:
                            st.markdown("**Turn 1: contracts**")
                            for c in msg.get("contracts", []):
                                st.markdown(f"- {contract_text(c)}")
                            if msg.get("stated_limits"):
                                st.markdown(f"Stated limits: {limits_text(msg['stated_limits'])}")
                            if msg.get("notes_for_humans"):
                                st.caption(f"Note: {clean(msg['notes_for_humans'])}")
                        elif e["event"] == Event.RANKING.value:
                            st.markdown("**Turn 2: ranking**")
                            st.markdown("  \n".join(f"{i}. {pid}" for i, pid in enumerate(msg["ranking"], 1)))
                            for c in msg.get("extra_contracts", []):
                                st.markdown(f"- Extra: {contract_text(c)}")
                            if msg.get("reasons"):
                                st.markdown("Reasons: " + ", ".join(msg["reasons"]))
                            if msg.get("justification"):
                                st.caption(clean(msg["justification"]))
                        elif e["event"] == Event.COMMITMENT.value:
                            st.markdown("**Turn 3: commitment**")
                            if msg["accept"]:
                                st.success(f"Accepts {msg['plan_id']}, signs for "
                                           f"{', '.join(msg.get('owned_fields', [])) or 'nothing'}")
                            else:
                                st.warning(f"Rejects {msg['plan_id']}: {msg.get('reason_if_reject') or 'no reason'}")
                elif e["event"] in VIOLATIONS:
                    who = pl.get("role") if e["actor"] == "COORDINATOR" else e["actor"]
                    if who == role:
                        code = pl.get("code")
                        st.error(f"Turn {e['turn']}: {e['event']}" + (f" ({code})" if code else "")
                                 + f"  \n{clean(pl.get('detail', ''))}")

    if entries:
        # ---- coordinator strip
        st.markdown("### Coordinator")
        with st.container(border=True):
            fs = ev("FEASIBLE_SET")
            sel = ev("SELECTED")
            k = st.columns(4)
            for i, t in enumerate((1, 2)):
                e = next((x for x in fs if x["turn"] == t), None)
                k[i].metric(f"Feasible plans after turn {t}", e["payload"]["size"] if e else "n/a")
            if sel:
                sp = plan_from(sel[-1]["payload"]["plan"])
                k[2].metric("Selected plan", sp.plan_id)
                k[3].metric("Lowest Borda score", sel[-1]["payload"].get("borda_min"))
                st.markdown(f"**Selected:** {describe_plan(sp)}")
                borda = sel[-1]["payload"].get("borda", {})
                if borda:
                    df = pd.DataFrame(borda).T.reindex(columns=list(config.ROLES))
                    df["min"] = df.min(axis=1)
                    df = df.sort_values("min", ascending=False)
                    df.index.name = "plan"
                    st.caption("Borda scores per agent (1 = top choice). The coordinator picks the plan "
                               "whose least happy agent is happiest.")
                    st.dataframe(df, width="stretch")
            else:
                k[2].metric("Selected plan", "none")

        # ---- result card
        st.markdown("### Result")
        done, fb = ev("DONE"), ev("FALLBACK")
        final_plan = None
        if done:
            p = done[-1]["payload"]
            final_plan = plan_from(p["plan"])
            with st.container(border=True):
                st.success(f"**Recommended plan: {final_plan.plan_id}**  \n{clean(p['summary'])}")
                st.markdown(f"Signed by: {', '.join(sorted(p.get('signatures', {})))}")
                for x in p.get("escalations", []):
                    st.warning(f"Escalation: {clean(x)}")
        elif fb:
            p = fb[-1]["payload"]
            final_plan = plan_from(p["plan"])
            st.warning(
                f"**Fallback rulebook decided: {final_plan.plan_id}**  \n{describe_plan(final_plan)}  \n"
                f"Branch: `{p['branch']}`  \nReason: `{clean(p['reason'])}`"
                + "".join(f"  \n- {clean(x)}" for x in p.get("explanation", []))
                + "".join(f"  \nEscalation: {clean(x)}" for x in p.get("escalations", []))
            )
        else:
            st.info("The log has no final decision yet.")

        if final_plan is not None:
            approvals = {e["payload"].get("human_role"): e for e in ev(Event.HUMAN_APPROVAL.value)}
            st.markdown("**Human sign-off** (the system recommends, people decide)")
            acols = st.columns(3)
            for col, (human, org) in zip(acols, HUMANS):
                with col:
                    if human in approvals:
                        st.success(f"{human} approved {approvals[human]['payload'].get('plan_id')} "
                                   f"at {approvals[human]['ts'][11:19]} UTC")
                    elif st.button(f"Approve as {human}", key=f"approve_{org}", width="stretch"):
                        ConsensusLog(shown["path"]).append(
                            human, 4, Event.HUMAN_APPROVAL.value,
                            {"human_role": human, "organisation_role": org,
                             "plan_id": final_plan.plan_id, "decision": "approved"})
                        st.rerun()

            # ---- reveal
            with st.expander("What actually happened in 2015", expanded=False):
                rows = []
                for name, plan in (("Our plan", final_plan), ("FCFS (no coordination)", fcfs(sc)),
                                   ("Fallback only (no agents)", fallback_only(sc).plan)):
                    s = simulate(sc, plan)
                    rows.append({"System": name, "Plan": plan.plan_id,
                                 "Arrival delay (min)": s["arrival_delay_min"],
                                 "Holding (min)": s["holding_min"], "Holding fuel (kg)": s["holding_fuel_kg"],
                                 "Diverted": "yes" if s["diverted"] else "no",
                                 "Next-leg departure delay (min)": s["next_leg_departure_delay_min"],
                                 "Missed connections, pax (synthetic)": s["missed_connection_pax_synthetic"],
                                 "Ground overtime, min (synthetic)": s["ground_overtime_min_synthetic"]})
                a = s["actual_2015"]
                rows.append({"System": "Actual 2015 (recorded)", "Plan": "as flown",
                             "Arrival delay (min)": a["arrival_delay_min"],
                             "Next-leg departure delay (min)": a["next_leg_departure_delay_min"]})
                st.dataframe(pd.DataFrame(rows).set_index("System"), width="stretch")
                st.caption(f"model estimate vs recorded 2015 outcome. True {fc.kind.replace('_', ' ')} delay "
                           f"used by the model: {s['true_delay_min']:g} min (revealed only here, never to agents).")

with tab_eval:
    p = config.RUNS_DIR / "eval_summary.md"
    if p.exists():
        st.markdown(clean(p.read_text()))
    else:
        st.info("No evaluation yet. Run `python -m dn.evaluate` to write runs/eval_summary.md.")

with tab_rules:
    st.subheader("Rules of play (workbook, verbatim)")
    try:
        st.dataframe(load_rules_of_play(), width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Could not load the workbook: {e}")
    st.subheader("Assumptions we chose (PLAN.md section 10)")
    at = assumptions_table()
    if at is not None:
        st.dataframe(at, width="stretch", hide_index=True)
    else:
        st.info("PLAN.md not found.")

with tab_log:
    if not shown or not Path(shown["path"]).exists():
        st.info("No log loaded. Run or replay a scenario first.")
    else:
        ok, bad, msg = verify(shown["path"])
        if ok:
            st.success(msg)
        else:
            st.error(f"{msg}: " + json.dumps(entries[bad])[:500] if bad is not None and bad < len(entries) else msg)
        st.caption(shown["path"])
        st.code(Path(shown["path"]).read_text(), language="json")
