from dn import contracts as ct
from dn.plan_space import by_id, enumerate_plans
from dn.schemas import (AvailableArrivalMinutes, ForbidStrategy, GateChangeNotice, GateWindow,
                        GateWindowFree, LatestArrival, MaxGroundDelay)


def P(showcase):
    return by_id(enumerate_plans(showcase.public))


def test_each_type(showcase):
    p, pub = P(showcase), showcase.public
    gd25, hold, div = p["GD25-G1"], p["HOLD-S1"], p["DIV-MDW"]
    c = AvailableArrivalMinutes(publisher="ATC", minutes=[393])
    assert ct.satisfied(c, gd25, pub) and not ct.satisfied(c, hold, pub) and ct.satisfied(c, div, pub)
    c = MaxGroundDelay(publisher="AIRLINE", minutes=20)
    assert not ct.satisfied(c, gd25, pub) and ct.satisfied(c, hold, pub)
    c = ForbidStrategy(publisher="ATC", strategy="HOLD")
    assert ct.satisfied(c, gd25, pub) and not ct.satisfied(c, hold, pub)
    c = GateWindowFree(publisher="GROUND", windows=[GateWindow(gate="G1", free_from=300, free_to=437)])
    assert not ct.satisfied(c, gd25, pub)  # needs 393..438
    c2 = GateWindowFree(publisher="GROUND", windows=[GateWindow(gate="G1", free_from=300, free_to=438)])
    assert ct.satisfied(c2, gd25, pub)
    c = GateChangeNotice(publisher="GROUND", minutes=20)
    assert ct.satisfied(c, hold, pub)  # 368 - 345 = 23 >= 20
    c = GateChangeNotice(publisher="GROUND", minutes=30)
    assert not ct.satisfied(c, hold, pub) and ct.satisfied(c, p["HOLD-G1"], pub)
    c = LatestArrival(publisher="AIRLINE", minute=390)
    assert not ct.satisfied(c, gd25, pub) and ct.satisfied(c, hold, pub) and not ct.satisfied(c, div, pub)


def test_tighten_only(showcase):
    space, pub = enumerate_plans(showcase.public), showcase.public
    old = [MaxGroundDelay(publisher="AIRLINE", minutes=60)]
    assert ct.is_tightening(old, old + [ForbidStrategy(publisher="ATC", strategy="HOLD")], space, pub)
    assert not ct.is_tightening(old, [MaxGroundDelay(publisher="AIRLINE", minutes=90)], space, pub)


def test_explain_empty(showcase):
    space, pub = enumerate_plans(showcase.public), showcase.public
    cs = [MaxGroundDelay(publisher="AIRLINE", minutes=30),
          ForbidStrategy(publisher="ATC", strategy="HOLD"),
          AvailableArrivalMinutes(publisher="ATC", minutes=[368 + 60]),
          LatestArrival(publisher="AIRLINE", minute=368 + 60)]
    assert ct.feasible(space, cs[:3], pub)  # DIVERT still allowed
    assert not ct.feasible(space, cs, pub)
    core = ct.explain_empty(space, cs, pub)
    assert not ct.feasible(space, core, pub) and len(core) <= 3
    assert ct.explain_empty(space, cs[:1], pub) == []


def test_helpers_showcase(showcase):
    space, pub = enumerate_plans(showcase.public), showcase.public
    (mgd,) = ct.airline_helper(pub, showcase.airline_private, space)
    assert mgd.minutes == 30
    atc = ct.atc_helper(pub, showcase.atc_private, space)[0]
    assert atc.minutes and all(m in {p.target_arrival_min for p in space} for m in atc.minutes)
    allc = (atc, mgd, *ct.ground_helper(pub, showcase.ground_private, space))
    assert ct.feasible(space, allc, pub)
