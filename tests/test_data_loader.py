from dn import data_loader as dl
from dn.time_utils import arrival_after_departure, hhmm_to_min, min_to_hhmm


def test_time_utils():
    assert hhmm_to_min(1305) == 785
    assert hhmm_to_min(2400) == 1440
    assert hhmm_to_min("0600") == 360
    assert arrival_after_departure(1380, 30) == 1470
    assert min_to_hhmm(1500) == "01:00 +1"


def test_flights_rows():
    assert len(dl.load_flights()) == dl.EXPECTED_ROWS


def test_airports():
    ap = dl.load_airports()
    assert len(ap) == 322
    o = ap.loc["ORD"]
    assert (o.active_runways, o.gates, o.max_runway_ops_per_hour, o.min_turnaround_min,
            o.spare_gates_at_any_time) == (4, 150, 90, 45, 3)


def test_wake():
    assert dl.wake_nm("Heavy", "Large") == 5
    assert dl.wake_nm("Large", "Large") == 3
    assert dl.wake_nm("Super", "Small") == 8
    assert abs(dl.wake_minutes("Large", "Large") - 1.2) < 1e-9


def test_constants_match_workbook():
    dl.check_constants()


def test_timezone_same_day_arrival():
    # ATL 2100 -> BHM 2056 local, 56 min block: same day, not +1 day
    assert arrival_after_departure(1260, 1256, 56) == 1256
    assert arrival_after_departure(1380, 30, 75) == 1470
