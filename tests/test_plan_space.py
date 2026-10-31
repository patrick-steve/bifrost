from dn.plan_space import enumerate_plans


def test_predeparture_ord_count(showcase):
    plans = enumerate_plans(showcase.public)
    assert len(plans) == 101
    assert len({p.plan_id for p in plans}) == 101
    assert "GD25-G1" in {p.plan_id for p in plans} and "DIV-MDW" in {p.plan_id for p in plans}


def test_airborne_count(showcase):
    pub = showcase.public.model_copy(update={"decision_mode": "airborne"})
    assert len(enumerate_plans(pub)) == 4 + 1
