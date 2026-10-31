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
