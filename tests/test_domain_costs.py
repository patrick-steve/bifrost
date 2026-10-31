import numpy as np

from dn.domain_costs import plan_outcomes, public_score
from dn.forecast import Forecast
from dn.schemas import Plan

F5 = Forecast("weather", "X", 1, 5, (0, 10, 20, 30, 40))


def test_weather_outcomes_hand_computed():
    p = Plan(plan_id="GD10-G1", strategy="GROUND_DELAY", ground_delay_min=10, target_arrival_min=0,
             gate="G1", hold_limit_min=15)
    o = plan_outcomes(p, F5.arr, "weather_at_destination")
    # W:0,10 -> no hold; 20 -> hold 10; 30 -> divert (30 > 25); 40 -> divert
    assert o["diverted"].tolist() == [False, False, False, True, True]
    assert o["hold"].tolist() == [0, 0, 10, 15, 15]
    assert np.nanmean(o["arr_delay"]) == (10 + 10 + 20) / 3
    assert public_score(p, F5, "weather_at_destination") == (0.4, 40 / 3)


def test_late_inbound_never_diverts():
    p = Plan(plan_id="HOLD-G1", strategy="HOLD", target_arrival_min=0, gate="G1", hold_limit_min=15)
    o = plan_outcomes(p, F5.arr, "late_inbound_aircraft")
    assert not o["diverted"].any() and o["arr_delay"].tolist() == [0, 10, 20, 30, 40]


def test_next_leg_breach_is_crew_swap_not_contract(showcase):
    from dn.domain_costs import airline_expected_cost
    from dn.forecast import for_scenario
    from dn.plan_space import by_id, enumerate_plans
    p = by_id(enumerate_plans(showcase.public))
    f = for_scenario(showcase.public)
    a30 = airline_expected_cost(p["GD30-G1"], f, showcase.public, showcase.airline_private)
    a35 = airline_expected_cost(p["GD35-G1"], f, showcase.public, showcase.airline_private)
    assert not a30["next_leg_crew_swap"] and a35["next_leg_crew_swap"]
    assert not a35["duty_breach"]
