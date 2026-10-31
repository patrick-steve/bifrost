import json

import pytest

from dn import config
from dn.agents import PRESSURE_LINE, ScriptedBackend
from dn.consensus_log import verify
from dn.contracts import satisfies_all
from dn.run import run_scenario


def B(**over):
    b = {r: ScriptedBackend() for r in config.ROLES}
    b.update({r: ScriptedBackend(v) for r, v in over.items()})
    return b


def events(log):
    return [e["event"] for e in log.entries]


def test_happy_path(tmp_path, showcase):
    o, log, prompts = run_scenario(showcase, B(), run_dir=tmp_path)
    assert o.status == "DONE" and o.turns_used == 3 and o.llm_calls == 9
    assert set(o.recommended.signatures) == set(config.ROLES)
    assert len(prompts) == 9 and verify(log.path)[0]
    # binding plan satisfies every published contract
    from dn.schemas import Turn1Contracts
    cs = [c for e in log.events("CONTRACTS") for c in Turn1Contracts(**e["payload"]["message"]).contracts]
    assert satisfies_all(o.plan, cs, showcase.public)


def test_missing_agent(tmp_path, showcase):
    o, log, _ = run_scenario(showcase, B(), run_dir=tmp_path, roles=("ATC", "AIRLINE"))
    assert o.status == "FALLBACK" and "MISSING_AGENT" in o.fallback.reason and o.plan.strategy == "DIVERT"
    assert "DONE" not in events(log)


def test_schema_garbage(tmp_path, showcase):
    o, log, _ = run_scenario(showcase, B(GROUND="garbage"), run_dir=tmp_path)
    assert o.status == "FALLBACK" and "SCHEMA_REJECT" in events(log)


def test_pressure_concession_rejected(tmp_path, showcase):
    o, log, _ = run_scenario(showcase, B(AIRLINE="concede"), run_dir=tmp_path,
                             injections={"AIRLINE": PRESSURE_LINE})
    assert "LOOSENING_ATTEMPT" in events(log)
    assert o.status == "FALLBACK"  # binding concessions = 0
    assert ("AIRLINE", "LOOSENING_ATTEMPT") in o.violations


def test_mandate_violation(tmp_path, showcase):
    o, log, _ = run_scenario(showcase, B(ATC="claim_gate"), run_dir=tmp_path)
    assert "MANDATE_VIOLATION" in events(log) and o.status == "FALLBACK"


def test_reject_at_turn3(tmp_path, showcase):
    o, log, _ = run_scenario(showcase, B(GROUND="reject"), run_dir=tmp_path)
    assert o.status == "FALLBACK" and "NO_CONSENSUS" in o.fallback.reason


@pytest.mark.parametrize("over", [{}, {"AIRLINE": "concede"}, {"ATC": "claim_gate"}, {"GROUND": "garbage"}])
def test_never_more_than_three_turns(tmp_path, showcase, over):
    o, log, _ = run_scenario(showcase, B(**over), run_dir=tmp_path)
    assert max(e["turn"] for e in log.entries) <= config.MAX_TURNS and o.llm_calls <= 9


def test_prompts_never_contain_sealed(tmp_path, showcase):
    from dn.scenario import unseal
    _, _, prompts = run_scenario(showcase, B(), run_dir=tmp_path)
    from dn.leakage import scan
    assert scan(prompts, unseal(showcase)) == []


class TightensThenAccepts(ScriptedBackend):
    """Airline states a hold limit of 1 min in turn 2, then accepts a plan with a 15 min hold."""

    def __call__(self, role, turn, system, user, draft_cls):
        from dn.agents.base import LimitDraft
        d = super().__call__(role, turn, system, user, draft_cls)
        if turn == 2:
            d.stated_limits = [LimitDraft(key="hold_limit_min", value=1)]
        return d


def test_turn2_limits_enforced_at_turn3(tmp_path, showcase):
    b = B()
    b["AIRLINE"] = TightensThenAccepts()
    o, log, _ = run_scenario(showcase, b, run_dir=tmp_path)
    assert o.status == "FALLBACK" and "SELF_CONTRADICTION" in events(log)


def test_blank_signature_fails_verification(tmp_path, showcase):
    import hashlib
    from dn.consensus_log import GENESIS, canonical_json, read, verify_entries
    _, log, _ = run_scenario(showcase, B(), run_dir=tmp_path)
    entries = read(log.path)
    i = next(i for i, e in enumerate(entries) if e["event"] == "COMMITMENT")
    entries[i]["payload"]["message"].update(plan_id="FORGED", signature="")
    prev = GENESIS
    for e in entries:
        e["prev_hash"] = prev
        e["hash"] = hashlib.sha256((prev + canonical_json({k: v for k, v in e.items() if k != "hash"})).encode()).hexdigest()
        prev = e["hash"]
    ok, seq, _ = verify_entries(entries)
    assert not ok and seq == i
