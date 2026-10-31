import pytest

from dn import config
from dn import scenario as sc
from dn.domain_costs import duty_after_next_leg


def test_showcase_public(showcase):
    p = showcase.public
    assert p.scenario_id == "showcase" and p.tail == "N767SK"
    assert (p.origin, p.destination) == ("DAY", "ORD")
    assert p.scheduled_arrival_min == 368 and p.decision_mode == "pre_departure"
    assert p.decision_time_min == 345
    assert p.disruption == "weather_at_destination"
    assert p.alternate == "MDW"
    assert p.next_leg.flight_number == "OO5164" and p.next_leg.destination == "CLE"
    assert p.next_leg.scheduled_departure_min == 408


def test_showcase_private(showcase):
    a = showcase.airline_private
    assert "Cleveland" in a.connections_note
    turn = showcase.public.destination_airport.min_turnaround_min

    def duty(d):
        return duty_after_next_leg(a.crew_duty_used_h, showcase.public.decision_time_min,
                                   368 + d + config.HOLD_BUDGET_MIN, turn, showcase.public.next_leg)
    assert duty(30) <= 13 < duty(35)
    assert [g.gate for g in showcase.ground_private.gates] == ["G1", "S1", "S2", "S3"]


def test_deterministic(showcase):
    again = sc.showcase()
    assert again.atc_private == showcase.atc_private
    assert again.airline_private == showcase.airline_private
    assert again.ground_private == showcase.ground_private


def test_alternate_none_or_same_state():
    assert sc.alternate_airport("ORD") == "MDW"


def test_unseal_guard(showcase):
    assert sc.unseal(showcase).weather_delay == 31  # tests may unseal


def test_unseal_blocked_elsewhere(showcase):
    ns = {"__name__": "dn.coordinator", "sc": sc, "s": showcase}
    with pytest.raises(PermissionError):
        exec("sc.unseal(s)", ns)
