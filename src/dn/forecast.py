"""No-hindsight delay forecast built from other days' history (IMPLEMENTATION.md section 5)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from .data_loader import load_flights
from .time_utils import hhmm_to_min

MIN_N = 30
QUANTILES = (10, 25, 50, 75, 90)


@dataclass(frozen=True)
class Forecast:
    kind: str  # "weather" | "late_inbound" | "hindsight"
    airport: str
    level: int  # 1..4; 0 = hindsight point mass
    n: int
    sample: tuple

    @property
    def arr(self) -> np.ndarray:
        return np.asarray(self.sample, dtype=float)

    def quantiles(self) -> dict:
        return {f"P{q}": float(np.percentile(self.arr, q)) for q in QUANTILES}

    def p_exceeds(self, x: float) -> float:
        return float((self.arr > x).mean())

    def summary(self) -> dict:
        return {"kind": self.kind, "airport": self.airport, "level": self.level, "n": self.n,
                **{k: round(v, 1) for k, v in self.quantiles().items()}}

    def label(self) -> str:
        if self.level == 0:
            return "Hindsight point mass (cheating baseline)"
        return f"Forecast from {self.n} flights (level {self.level}), your own day excluded"


def point_mass(w: float, kind: str = "hindsight", airport: str = "") -> Forecast:
    return Forecast(kind=kind, airport=airport, level=0, n=1, sample=(float(w),))


@lru_cache(maxsize=2)
def _population(column: str, airport_col: str, time_col: str) -> pd.DataFrame:
    df = load_flights()
    p = df[df[column] > 0]
    return pd.DataFrame({
        "AIRPORT": p[airport_col].to_numpy(), "MONTH": p.MONTH.to_numpy(), "DAY": p.DAY.to_numpy(),
        "HOUR": p[time_col].map(hhmm_to_min).to_numpy() // 60, "X": p[column].to_numpy(dtype=float),
    })


def _levels(pop: pd.DataFrame, airport: str, month: int, hour: int, exclude) -> tuple[int, np.ndarray]:
    if exclude is not None:
        pop = pop[~((pop.MONTH == exclude[0]) & (pop.DAY == exclude[1]))]
    near = (pop.HOUR - hour).abs() <= 2
    at = pop.AIRPORT == airport
    for level, mask in ((1, at & (pop.MONTH == month) & near), (2, at & near), (3, at)):
        x = pop.X[mask].to_numpy()
        if len(x) >= MIN_N:
            return level, x
    return 4, pop.X.to_numpy()


def weather_forecast(dest: str, month: int, sched_arrival_min: int, exclude=None) -> Forecast:
    pop = _population("WEATHER_DELAY", "DESTINATION_AIRPORT", "SCHEDULED_ARRIVAL")
    level, x = _levels(pop, dest, month, (sched_arrival_min % 1440) // 60, exclude)
    return Forecast("weather", dest, level, len(x), tuple(x.tolist()))


def late_inbound_forecast(origin: str, month: int, sched_departure_min: int, exclude=None) -> Forecast:
    """Inbound lateness is forecast at the origin, by scheduled departure hour (deviation noted in TASKS.md)."""
    pop = _population("LATE_AIRCRAFT_DELAY", "ORIGIN_AIRPORT", "SCHEDULED_DEPARTURE")
    level, x = _levels(pop, origin, month, (sched_departure_min % 1440) // 60, exclude)
    return Forecast("late_inbound", origin, level, len(x), tuple(x.tolist()))


def for_scenario(public) -> Forecast:
    excl = (public.month, public.day)
    if public.disruption == "weather_at_destination":
        return weather_forecast(public.destination, public.month, public.scheduled_arrival_min, excl)
    return late_inbound_forecast(public.origin, public.month, public.scheduled_departure_min, excl)
