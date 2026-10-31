import numpy as np

from dn import forecast as fc


def test_ord_all_months_median():
    f = fc._population("WEATHER_DELAY", "DESTINATION_AIRPORT", "SCHEDULED_ARRIVAL")
    x = f[f.AIRPORT == "ORD"].X
    assert len(x) == 2928 and abs(np.median(x) - 31) <= 1


def test_exclusion_changes_n():
    a = fc.weather_forecast("ORD", 7, 368, exclude=None)
    b = fc.weather_forecast("ORD", 7, 368, exclude=(7, 15))
    assert a.level == b.level and b.n < a.n


def test_level_fallbacks():
    big = fc.weather_forecast("ORD", 7, 18 * 60)
    assert big.level == 1
    tiny = fc.weather_forecast("DAY", 7, 368)
    assert tiny.level in (2, 3, 4)
    nowhere = fc.weather_forecast("ZZZ", 7, 368)
    assert nowhere.level == 4


def test_p_exceeds():
    f = fc.Forecast("weather", "X", 1, 5, (0, 10, 20, 30, 40))
    assert f.p_exceeds(25) == 0.4 and f.p_exceeds(40) == 0.0


def test_hour_window_wraps_midnight():
    f = fc._population("WEATHER_DELAY", "DESTINATION_AIRPORT", "SCHEDULED_ARRIVAL")
    assert f.HOUR.max() <= 23


def test_overnight_excludes_arrival_day(showcase):
    pub = showcase.public.model_copy(update={"scheduled_arrival_min": 1440 + 30, "month": 1, "day": 31})
    a = fc.for_scenario(pub)
    b = fc.weather_forecast(pub.destination, 1, pub.scheduled_arrival_min, exclude=(1, 31))
    assert a.n <= b.n
    assert fc._next_day(12, 31) == (1, 1)
