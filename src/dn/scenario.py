"""Turn one flights.csv row into public state, three private states and a sealed outcome.

Synthetic private values are seeded by (SEED, row index) so every run is reproducible.
"""
from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .data_loader import SIZE_RANK, load_airports, load_flights
from .domain_costs import duty_after_next_leg
from .schemas import (
    AirlinePrivate, AirportRecord, AtcPrivate, BookedArrival, BusyInterval, Connection,
    GateState, GroundPrivate, NextLeg, PublicScenario, SealedOutcome,
)
from .time_utils import arrival_after_departure, hhmm_to_min

SHOWCASE = dict(MONTH=7, DAY=15, AIRLINE="OO", FLIGHT_NUMBER=6262, TAIL_NUMBER="N767SK",
                ORIGIN_AIRPORT="DAY", DESTINATION_AIRPORT="ORD")
SHOWCASE_CONNECTIONS_NOTE = ("14 passengers connect to the last flight of the day to Cleveland; "
                             "missing it means overnight hotel costs.")
SHOWCASE_DUTY_BREACH_DELAY = 35
_UNSEAL_ALLOWED = {"dn.simulate", "dn.baselines", "dn.evaluate"}


def _num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def wake_category(airline: str, distance: float) -> str:
    return "Heavy" if airline in config.HEAVY_AIRLINES and distance >= config.HEAVY_MIN_DISTANCE else "Large"


def airport_record(iata: str) -> AirportRecord:
    r = load_airports().loc[iata]
    return AirportRecord(
        iata=iata, name=r["AIRPORT"], city=r["CITY"], state=r["STATE"], size_class=r["size_class"],
        active_runways=int(r["active_runways"]), gates=int(r["gates"]),
        max_runway_ops_per_hour=int(r["max_runway_ops_per_hour"]),
        min_turnaround_min=int(r["min_turnaround_min"]),
        spare_gates_at_any_time=int(r["spare_gates_at_any_time"]),
    )


def alternate_airport(dest: str) -> str | None:
    """Same CITY, else best size_class in same STATE (ties: most delayed departures)."""
    ap = load_airports()
    if dest not in ap.index:
        return None
    d = ap.loc[dest]
    others = ap[ap.IATA_CODE != dest]
    same_city = others[(others.CITY == d["CITY"]) & (others.STATE == d["STATE"])]
    pool = same_city if len(same_city) else others[others.STATE == d["STATE"]]
    if pool.empty:
        return None
    pool = pool.assign(_rank=pool.size_class.map(SIZE_RANK).fillna(9))
    pool = pool.sort_values(["_rank", "delayed_departures_in_flights_csv"], ascending=[True, False])
    return str(pool.iloc[0].IATA_CODE)


def find_next_leg(df: pd.DataFrame, row: pd.Series, sched_arr: int) -> pd.Series | None:
    if sched_arr >= 1440:
        return None
    m = df[(df.MONTH == row.MONTH) & (df.DAY == row.DAY) & (df.TAIL_NUMBER == row.TAIL_NUMBER)
           & (df.ORIGIN_AIRPORT == row.DESTINATION_AIRPORT)]
    if m.empty:
        return None
    dep = m.SCHEDULED_DEPARTURE.map(hhmm_to_min)
    m = m[dep > sched_arr]
    if m.empty:
        return None
    return m.loc[dep[m.index].idxmin()]


@dataclass
class Scenario:
    public: PublicScenario
    atc_private: AtcPrivate
    airline_private: AirlinePrivate
    ground_private: GroundPrivate
    _sealed: SealedOutcome = field(repr=False)

    def for_agent(self, role: str) -> dict:
        private = {"ATC": self.atc_private, "AIRLINE": self.airline_private,
                   "GROUND": self.ground_private}[role]
        return {"public": self.public, "private": private}

    def for_coordinator(self) -> PublicScenario:
        return self.public


def unseal(scenario: Scenario) -> SealedOutcome:
    """Only simulate, baselines, evaluate and tests may read the real outcome."""
    caller = inspect.stack()[1].frame.f_globals.get("__name__", "")
    if caller not in _UNSEAL_ALLOWED and not caller.startswith(("tests", "test_")):
        raise PermissionError(f"{caller} may not read the sealed outcome")
    return scenario._sealed


# --------------------------------------------------------------------- builders
def _atc_private(rng, pub: PublicScenario) -> AtcPrivate:
    ap = pub.destination_airport
    start = pub.scheduled_arrival_min - config.ATC_WINDOW_BEFORE_MIN
    end = pub.scheduled_arrival_min + config.ATC_WINDOW_AFTER_MIN
    reduced = ap.max_runway_ops_per_hour * config.WEATHER_CAPACITY_FACTOR * config.ARRIVAL_SHARE
    n = int(round(reduced * config.BACKGROUND_LOAD * (end - start) / 60))
    minutes = np.sort(rng.choice(np.arange(start, end + 1), size=min(n, end - start + 1), replace=False))
    p_heavy = 0.2 if ap.size_class == "Large hub" else 0.05
    wakes = np.where(rng.random(len(minutes)) < p_heavy, "Heavy", "Large")
    taxiway = None
    if ap.size_class == "Large hub" and rng.random() < 0.3:
        taxiway = f"Taxiway {rng.choice(list('ABCHKLMNP'))}"
    return AtcPrivate(
        booked_arrivals=[BookedArrival(minute=int(m), wake=str(w)) for m, w in zip(minutes, wakes)],
        window_start_min=start, window_end_min=end,
        reduced_arrival_capacity_per_h=reduced, taxiway_closed=taxiway,
    )


def _airline_private(rng, pub: PublicScenario, showcase: bool) -> AirlinePrivate:
    n_pax = int(rng.integers(0, 31))
    connections = []
    if n_pax:
        k = int(min(n_pax, rng.integers(1, 5)))
        cuts = np.sort(rng.choice(np.arange(1, n_pax), size=k - 1, replace=False)) if k > 1 else []
        sizes = np.diff(np.concatenate([[0], cuts, [n_pax]])).astype(int)
        dests = load_airports().IATA_CODE.values
        for s in sizes:
            connections.append(Connection(
                label=f"{pub.airline}{int(rng.integers(1000, 9999))} to {rng.choice(dests)}",
                passengers=int(s),
                latest_arrival_min=pub.scheduled_arrival_min + int(rng.integers(20, 151)),
            ))
    duty_used = round(float(rng.uniform(4.0, 11.0)), 2)
    note = ""
    if showcase:
        connections.append(Connection(label=f"{pub.airline} last flight of the day to CLE",
                                      passengers=14,
                                      latest_arrival_min=pub.scheduled_arrival_min + 40))
        note = SHOWCASE_CONNECTIONS_NOTE
        # Set duty so the next leg pushes duty above 13 h when ground delay >= 35.
        arr = pub.scheduled_arrival_min + SHOWCASE_DUTY_BREACH_DELAY + config.HOLD_BUDGET_MIN
        extra = duty_after_next_leg(0.0, pub.decision_time_min, arr,
                                    pub.destination_airport.min_turnaround_min, pub.next_leg)
        duty_used = round(config.CREW_MAX_DUTY_H - extra + 1 / 60, 4)
    return AirlinePrivate(
        spare_fuel_min=config.SPARE_FUEL_MIN, final_reserve_min=config.FINAL_RESERVE_MIN,
        holding_burn_kg_per_h=config.HOLD_BURN_KG_PER_H[pub.wake_category],
        crew_duty_used_h=duty_used, connections=connections, connections_note=note,
        holding_turbulence="moderate" if rng.random() < 0.3 else "light",
    )


def _ground_private(rng, pub: PublicScenario) -> GroundPrivate:
    ap = pub.destination_airport
    arr = pub.scheduled_arrival_min
    horizon = arr + config.GROUND_DELAY_MAX_MIN + ap.min_turnaround_min + 60
    g1_free_until = arr + int(rng.integers(60, 151))
    gates = [GateState(gate="G1", busy=[BusyInterval(start=g1_free_until, end=g1_free_until + 60)])]
    for i in range(1, ap.spare_gates_at_any_time + 1):
        busy = []
        for _ in range(int(rng.integers(1, 3))):
            s = int(rng.integers(arr - 30, horizon))
            busy.append(BusyInterval(start=s, end=s + int(rng.integers(40, 91))))
        busy.sort(key=lambda b: b.start)
        gates.append(GateState(gate=f"S{i}", busy=busy))
    return GroundPrivate(
        gates=gates, min_turnaround_min=ap.min_turnaround_min,
        shift_end_min=arr + int(rng.integers(30, 151)),
        next_leg_departure_min=pub.next_leg.scheduled_departure_min if pub.next_leg else None,
    )


def build(index: int, df: pd.DataFrame | None = None) -> Scenario:
    df = load_flights() if df is None else df
    row = df.loc[index]
    dep = hhmm_to_min(row.SCHEDULED_DEPARTURE)
    sched_time = int(row.SCHEDULED_TIME)
    arr = arrival_after_departure(dep, hhmm_to_min(row.SCHEDULED_ARRIVAL), sched_time)
    mode = "pre_departure" if sched_time <= config.PREDEPARTURE_MAX_SCHEDULED_TIME_MIN else "airborne"
    nl = find_next_leg(df, row, arr)
    next_leg = None
    if nl is not None:
        next_leg = NextLeg(flight_number=f"{nl.AIRLINE}{int(nl.FLIGHT_NUMBER)}",
                           destination=nl.DESTINATION_AIRPORT,
                           scheduled_departure_min=hhmm_to_min(nl.SCHEDULED_DEPARTURE),
                           scheduled_time_min=int(nl.SCHEDULED_TIME) if _num(nl.SCHEDULED_TIME) else None)
    showcase = all(row[k] == v for k, v in SHOWCASE.items())
    pub = PublicScenario(
        scenario_id="showcase" if showcase else f"r{index}",
        date=f"{int(row.YEAR)}-{int(row.MONTH):02d}-{int(row.DAY):02d}",
        month=int(row.MONTH), day=int(row.DAY), airline=row.AIRLINE,
        flight_number=f"{row.AIRLINE}{int(row.FLIGHT_NUMBER)}", tail=str(row.TAIL_NUMBER),
        origin=row.ORIGIN_AIRPORT, destination=row.DESTINATION_AIRPORT,
        scheduled_departure_min=dep, scheduled_arrival_min=arr, scheduled_time_min=sched_time,
        distance=int(row.DISTANCE), wake_category=wake_category(row.AIRLINE, row.DISTANCE),
        decision_mode=mode,
        decision_time_min=dep - 15 if mode == "pre_departure" else arr - 30,
        disruption="weather_at_destination" if (_num(row.WEATHER_DELAY) or 0) > 15 else "late_inbound_aircraft",
        destination_airport=airport_record(row.DESTINATION_AIRPORT),
        alternate=alternate_airport(row.DESTINATION_AIRPORT), next_leg=next_leg,
    )
    rng = np.random.default_rng([config.SEED, int(index)])
    sealed = SealedOutcome(
        weather_delay=_num(row.WEATHER_DELAY) or 0.0,
        late_aircraft_delay=_num(row.LATE_AIRCRAFT_DELAY) or 0.0,
        arrival_delay=_num(row.ARRIVAL_DELAY) or 0.0,
        arrival_time=_num(row.ARRIVAL_TIME), departure_delay=_num(row.DEPARTURE_DELAY),
        next_leg_departure_delay=_num(nl.DEPARTURE_DELAY) if nl is not None else None,
        next_leg_late_aircraft_delay=_num(nl.LATE_AIRCRAFT_DELAY) if nl is not None else None,
        raw={c: _num(row[c]) if c != "CANCELLATION_REASON" else (None if pd.isna(row[c]) else str(row[c]))
             for c in config.SEALED_COLUMNS},
    )
    return Scenario(public=pub, atc_private=_atc_private(rng, pub),
                    airline_private=_airline_private(rng, pub, showcase),
                    ground_private=_ground_private(rng, pub), _sealed=sealed)


def showcase_index(df: pd.DataFrame | None = None) -> int:
    df = load_flights() if df is None else df
    m = np.ones(len(df), dtype=bool)
    for k, v in SHOWCASE.items():
        m &= (df[k] == v).to_numpy()
    idx = np.flatnonzero(m)
    assert len(idx) == 1, f"showcase row not unique: {idx}"
    return int(df.index[idx[0]])


def showcase() -> Scenario:
    return build(showcase_index())
