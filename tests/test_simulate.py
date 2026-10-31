from dn.baselines import fcfs
from dn.plan_space import by_id, enumerate_plans
from dn.simulate import simulate


def test_branches(showcase):  # W = 31 for the showcase
    p = by_id(enumerate_plans(showcase.public))
    r = simulate(showcase, p["GD35-G1"])  # W <= d
    assert (r["arrival_delay_min"], r["holding_min"], r["diverted"]) == (35, 0, False)
    r = simulate(showcase, p["GD20-G1"])  # d < W <= d + 15
    assert (r["arrival_delay_min"], r["holding_min"]) == (31, 11)
    assert r["holding_fuel_kg"] == round(11 / 60 * 2400, 1)
    # next leg: 368 + 31 + 45 = 444 vs 408 scheduled -> 36
    assert r["next_leg_departure_delay_min"] == 36
    r = simulate(showcase, p["HOLD-G1"])  # W > d + 15 -> diverted
    assert r["diverted"] and r["holding_min"] == 15 and r["next_leg_status"] == "aircraft unavailable"
    assert simulate(showcase, p["DIV-MDW"])["diverted"]


def test_fcfs_showcase_diverts_under_model(showcase):
    """Decision D1: FCFS (no ground delay) diverts under the model; 2015 flight was held on the ground."""
    r = simulate(showcase, fcfs(showcase))
    assert r["diverted"] and r["actual_2015"]["arrival_delay_min"] == 43
