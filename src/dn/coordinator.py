"""Coordinator: a plain 3-turn state machine. Holds NO private data (IMPLEMENTATION.md section 12).

It sees the public scenario, the public forecast, mandates and the signed messages agents send.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import config
from . import contracts as ct
from . import fallback
from .agents.base import AgentError
from .consensus_log import ConsensusLog, verify_signature
from .domain_costs import public_score
from .mandates import DIVERT_ESCALATION, check_commitment, check_contract
from .schemas import (
    LIMIT_KEYS, Event, FallbackResult, Plan, PublicScenario, RecommendedPlan,
)
from .time_utils import min_to_hhmm

REASON_TEXT = {
    "FUEL_RISK": "protects the fuel reserve", "CONNECTIONS": "protects passenger connections",
    "DUTY": "keeps the crew within duty limits", "OVERTIME": "avoids ground crew overtime",
    "THROUGHPUT": "keeps arrival throughput", "WAKE_SEPARATION": "keeps wake separation",
    "TURBULENCE": "avoids holding in turbulence", "GATE_CONFLICT": "avoids a gate conflict",
    "NEXT_LEG": "protects the next departure", "LATE_ARRIVAL": "limits arrival delay",
    "DIVERSION_RISK": "limits diversion risk",
}


@dataclass
class Outcome:
    status: str  # "DONE" | "FALLBACK"
    plan: Plan
    turns_used: int
    recommended: RecommendedPlan | None = None
    fallback: FallbackResult | None = None
    feasible_sizes: dict = field(default_factory=dict)
    borda: dict = field(default_factory=dict)
    escalations: list = field(default_factory=list)
    wall_clock_s: float = 0.0
    llm_calls: int = 0
    violations: list = field(default_factory=list)  # (role, event) of voided messages


class _Void(Exception):
    def __init__(self, event: Event, detail: str):
        super().__init__(detail)
        self.event, self.detail = event, detail


def describe_plan(p: Plan) -> str:
    if p.strategy == "DIVERT":
        return f"Divert to {p.plan_id.split('-', 1)[1]}"
    head = (f"Ground delay {p.ground_delay_min} min" if p.strategy == "GROUND_DELAY"
            else "Depart as planned, hold if needed")
    return (f"{head}, arrive {min_to_hhmm(p.target_arrival_min)} at gate {p.gate}, "
            f"hold at most {p.hold_limit_min} min then divert")


class Coordinator:
    def __init__(self, public: PublicScenario, forecast, plan_space: list[Plan], mandates: dict,
                 agents: dict, log: ConsensusLog):
        self.public, self.forecast, self.space = public, forecast, plan_space
        self.mandates, self.agents, self.log = mandates, agents, log
        self.contracts: list = []
        self.t1_limits: dict[str, dict] = {}
        self.calls = 0
        self.violations: list = []

    # ------------------------------------------------------------ utilities
    def _collect(self, turn: int, method: str, broadcast: dict) -> dict:
        """Parallel calls. Returns {role: message or None}."""
        out = {}
        present = {r: a for r, a in self.agents.items() if a is not None}

        def call(agent):
            return getattr(agent, method)(broadcast)

        ex = ThreadPoolExecutor(max_workers=3)
        try:
            futs = {r: ex.submit(call, a) for r, a in present.items()}
            for r, f in futs.items():
                self.calls += 1
                try:
                    out[r] = f.result(timeout=config.AGENT_TIMEOUT_S + 5)
                except AgentError as e:
                    self.log.append(r, turn, Event.SCHEMA_REJECT, {"code": e.code, "detail": e.detail[:300]})
                    out[r] = None
                except Exception as e:  # pydantic validation, timeouts, anything else
                    self.log.append(r, turn, Event.SCHEMA_REJECT, {"code": type(e).__name__, "detail": str(e)[:300]})
                    out[r] = None
        finally:
            ex.shutdown(wait=False, cancel_futures=True)  # never wait on a hung agent
        for r in config.ROLES:
            out.setdefault(r, None)
        return out

    def _void(self, role, turn, err: _Void):
        self.violations.append((role, err.event.value))
        self.log.append("COORDINATOR", turn, err.event, {"role": role, "detail": err.detail})

    def _check_common(self, role, msg, turn):
        if msg.role != role:
            raise _Void(Event.SCHEMA_REJECT, f"message role {msg.role} from {role}")
        if not verify_signature(role, msg):
            raise _Void(Event.SCHEMA_REJECT, "bad signature")
        for c in getattr(msg, "contracts", []) + getattr(msg, "extra_contracts", []):
            why = check_contract(self.mandates[role], c)
            if why:
                raise _Void(Event.MANDATE_VIOLATION, why)
        self._check_limits(role, msg.stated_limits, turn)

    def _tighten_limits(self, role, limits: dict):
        cur = self.t1_limits.setdefault(role, {})
        for k, v in limits.items():
            if k not in cur:
                cur[k] = v
            else:
                cur[k] = max(cur[k], v) if LIMIT_KEYS[k][0] == "min" else min(cur[k], v)

    def _check_limits(self, role, limits: dict, turn):
        """Workbook limits can never be loosened; later turns may never loosen turn-1 limits."""
        base = {"reserve_min": config.FINAL_RESERVE_MIN, "hold_limit_min": config.HOLD_BUDGET_MIN}
        ref = self.t1_limits.get(role, {})
        for k, v in limits.items():
            if k not in LIMIT_KEYS:
                raise _Void(Event.SCHEMA_REJECT, f"unknown limit {k}")
            direction = LIMIT_KEYS[k][0]
            for name, bound in (("workbook", base.get(k)), ("turn 1", ref.get(k))):
                if bound is None:
                    continue
                if (direction == "min" and v < bound) or (direction == "max" and v > bound):
                    raise _Void(Event.LOOSENING_ATTEMPT, f"{k}={v} looser than {name} value {bound}")

    def _fallback(self, reason, turn, missing=False, extra_esc=()) -> Outcome:
        fb = fallback.decide(self.public, self.space, self.contracts, self.forecast, reason,
                             contracts_missing=missing)
        fb = fb.model_copy(update={"escalations": list(extra_esc) + fb.escalations})
        self.log.append("FALLBACK_RULEBOOK", turn, Event.FALLBACK, fb)
        return Outcome("FALLBACK", fb.plan, turn, fallback=fb, escalations=fb.escalations)

    def _public_key(self, p: Plan):
        pd, ead = public_score(p, self.forecast, self.public.disruption)
        return (pd, ead, p.plan_id)

    # ----------------------------------------------------------------- run
    def run(self) -> Outcome:
        t0 = time.monotonic()
        out = self._run()
        out.wall_clock_s = round(time.monotonic() - t0, 2)
        out.llm_calls = self.calls
        out.violations = self.violations
        return out

    def _run(self) -> Outcome:
        log, pub = self.log, self.public
        for r, m in self.mandates.items():
            log.append(r, 0, Event.MANDATE_ISSUED, m)
        log.append("COORDINATOR", 0, Event.SCENARIO_PUBLIC, pub)
        log.append("COORDINATOR", 0, Event.FORECAST, {**self.forecast.summary(), "label": self.forecast.label()})
        sizes = {}

        # ---------------- Turn 1: contracts
        msgs = self._collect(1, "turn1", {"turn": 1, "plan_space_size": len(self.space)})
        missing = []
        for r in config.ROLES:
            m = msgs[r]
            if m is None:
                missing.append(r)
                continue
            try:
                self._check_common(r, m, 1)
            except _Void as e:
                self._void(r, 1, e)
                missing.append(r)
                continue
            self.t1_limits[r] = dict(m.stated_limits)
            self.contracts += m.contracts
            log.append(r, 1, Event.CONTRACTS, {"message": m.model_dump(mode="json")})
        if missing:
            o = self._fallback(f"MISSING_AGENT: {', '.join(missing)}", 1, missing=True)
            o.feasible_sizes = sizes
            return o
        F = ct.feasible(self.space, self.contracts, pub)
        sizes[1] = len(F)
        log.append("COORDINATOR", 1, Event.FEASIBLE_SET, {"size": len(F), "plan_ids": [p.plan_id for p in F]})
        if not F:
            o = self._fallback("NO_SAFE_OPTION", 1)
            o.feasible_sizes = sizes
            return o

        # ---------------- Turn 2: rankings in the overlap
        ordered = sorted(F, key=self._public_key)
        bc = ordered[: config.BROADCAST_MAX_PLANS]
        fcfs_eq = next((p.plan_id for p in F if p.strategy == "HOLD"), None)  # G1 first, then S1..
        must = [pid for pid in (fcfs_eq,) if pid] + [fallback.decide(pub, self.space, self.contracts, self.forecast, "preview").plan.plan_id]
        for pid in must:
            p = next((x for x in F if x.plan_id == pid), None)
            if p is not None and p not in bc:
                bc.append(p)
        bc_ids = [p.plan_id for p in bc]
        msgs = self._collect(2, "turn2", {"turn": 2, "plan_ids": bc_ids,
                                          "plans": [p.model_dump(mode="json") for p in bc]})
        rankings = {}
        for r in config.ROLES:
            m = msgs[r]
            try:
                if m is None:
                    raise _Void(Event.SCHEMA_REJECT, "no valid turn 2 message")
                self._check_common(r, m, 2)
                bad = [pid for pid in m.ranking if pid not in bc_ids]
                if bad or len(set(m.ranking)) != len(m.ranking):
                    raise _Void(Event.SCHEMA_REJECT, f"ranking outside broadcast or duplicated: {bad}")
            except _Void as e:
                if m is not None:
                    self._void(r, 2, e)
                o = self._fallback(f"INVALID_TURN2: {r} {e.event.value}", 2)
                o.feasible_sizes = sizes
                return o
            new = self.contracts + m.extra_contracts
            assert ct.is_tightening(self.contracts, new, self.space, pub)  # additions only tighten
            self.contracts = new
            self._tighten_limits(r, m.stated_limits)
            rankings[r] = m.ranking
            log.append(r, 2, Event.RANKING, {"message": m.model_dump(mode="json")})
        F2 = [p for p in ct.feasible(bc, self.contracts, pub)]
        sizes[2] = len(F2)
        log.append("COORDINATOR", 2, Event.FEASIBLE_SET, {"size": len(F2), "plan_ids": [p.plan_id for p in F2]})
        if not F2:
            o = self._fallback("NO_SAFE_OPTION_AFTER_TURN2", 2)
            o.feasible_sizes = sizes
            return o
        borda = {}
        for p in F2:
            per = {}
            for r, rank in rankings.items():
                k = len(rank)
                per[r] = round((k - rank.index(p.plan_id)) / k, 3) if p.plan_id in rank else 0.0
            borda[p.plan_id] = per
        # argmax of the minimum Borda score; ties: lower divert risk, lower expected delay, plan_id
        chosen = min(F2, key=lambda p: (-min(borda[p.plan_id].values()), *self._public_key(p)))
        log.append("COORDINATOR", 2, Event.SELECTED, {"plan": chosen.model_dump(mode="json"),
                                                       "borda_min": min(borda[chosen.plan_id].values()),
                                                       "borda": borda})

        # ---------------- Turn 3: sign
        msgs = self._collect(3, "turn3", {"turn": 3, "plan_id": chosen.plan_id,
                                          "plan": chosen.model_dump(mode="json")})
        sigs, rejects, esc = {}, [], []
        for r in config.ROLES:
            m = msgs[r]
            agent = self.agents.get(r)
            esc += getattr(agent, "last_private_flags", []) or []
            try:
                if m is None:
                    raise _Void(Event.SCHEMA_REJECT, "no valid turn 3 message")
                self._check_common(r, m, 3)
                if m.plan_id != chosen.plan_id:
                    raise _Void(Event.SCHEMA_REJECT, f"commitment for {m.plan_id}, selected {chosen.plan_id}")
                over = check_commitment(self.mandates[r], m.owned_fields)
                if over:
                    raise _Void(Event.MANDATE_VIOLATION, f"claimed fields outside mandate: {over}")
                self._tighten_limits(r, m.stated_limits)
                for k, v in self.t1_limits.get(r, {}).items():
                    field_name = LIMIT_KEYS[k][1]
                    if field_name and m.accept and getattr(chosen, field_name) > v:
                        raise _Void(Event.SELF_CONTRADICTION, f"accepts {field_name}={getattr(chosen, field_name)} "
                                                              f"above own stated {k}={v}")
                if m.accept and not ct.satisfies_all(chosen, self.contracts, pub):
                    raise _Void(Event.SCHEMA_REJECT, "accepted a plan outside contracts")
            except _Void as e:
                if m is not None:
                    self._void(r, 3, e)
                rejects.append(f"{r}:{e.event.value}")
                continue
            log.append(r, 3, Event.COMMITMENT, {"message": m.model_dump(mode="json")})
            if m.accept:
                sigs[r] = m.signature
            else:
                rejects.append(f"{r}:{m.reason_if_reject.value if m.reason_if_reject else 'REJECT'}")
        if rejects:
            o = self._fallback(f"NO_CONSENSUS: {', '.join(rejects)}", 3, extra_esc=esc)
            o.feasible_sizes, o.borda = sizes, borda
            return o
        if chosen.strategy == "DIVERT":
            esc.append(DIVERT_ESCALATION)
        reasons = sorted({rc.value for e in log.events("RANKING")
                          for rc in _reason_codes(e)} & set(REASON_TEXT))
        summary = (f"{describe_plan(chosen)}. Agreed by ATC, Airline and Ground in 3 turns. "
                   + ("Why: " + "; ".join(REASON_TEXT[r] for r in reasons) + "." if reasons else ""))
        rec = RecommendedPlan(plan=chosen, signatures=sigs, escalations=esc, summary=summary, turns_used=3)
        log.append("COORDINATOR", 3, Event.DONE, rec)
        return Outcome("DONE", chosen, 3, recommended=rec, feasible_sizes=sizes, borda=borda, escalations=esc)


def _reason_codes(entry):
    from .schemas import ReasonCode

    return [ReasonCode(x) for x in entry["payload"]["message"].get("reasons", [])]
