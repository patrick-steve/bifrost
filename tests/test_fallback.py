from dn import fallback
from dn.baselines import helper_contracts
from dn.forecast import Forecast, for_scenario
from dn.plan_space import enumerate_plans
from dn.schemas import ForbidStrategy, LatestArrival, MaxGroundDelay


def test_branches(showcase):
    pub, space = showcase.public, enumerate_plans(showcase.public)
    calm = Forecast("weather", "ORD", 1, 4, (0, 0, 0, 0))
    r = fallback.decide(pub, space, [], calm, "t")
    assert r.branch == "R1_MIN_DELAY_MEETS_RISK" and r.plan.plan_id == "HOLD-G1"
    stormy = Forecast("weather", "ORD", 1, 3, (200, 300, 400))
    r = fallback.decide(pub, space, [MaxGroundDelay(publisher="AIRLINE", minutes=30)], stormy, "t")
    assert r.branch == "R1_LARGEST_DELAY_RISK_NOT_MET" and r.plan.plan_id == "GD30-G1" and r.escalations
    empty = [ForbidStrategy(publisher="ATC", strategy="HOLD"), MaxGroundDelay(publisher="AIRLINE", minutes=0),
             LatestArrival(publisher="AIRLINE", minute=0)]
    r = fallback.decide(pub, space, empty, calm, "t")
    assert r.branch == "R2_DIVERT" and r.plan.strategy == "DIVERT" and r.explanation
    r = fallback.decide(pub, space, [], calm, "t", contracts_missing=True)
    assert r.branch == "R2_DIVERT"
    no_alt = pub.model_copy(update={"alternate": None})
    r = fallback.decide(no_alt, enumerate_plans(no_alt), empty, calm, "t")
    assert r.branch == "R2_NO_ALTERNATE_HOLD" and r.plan.plan_id == "HOLD-G1"


def test_deterministic(showcase):
    pub, space = showcase.public, enumerate_plans(showcase.public)
    cs, f = helper_contracts(showcase, space), for_scenario(pub)
    a = fallback.decide(pub, space, cs, f, "x").model_dump_json()
    b = fallback.decide(pub, space, cs, f, "x").model_dump_json()
    assert a == b
