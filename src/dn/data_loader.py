"""Load flights.csv and the challenge workbook."""
import logging
import re
from functools import lru_cache

import pandas as pd

from . import config

log = logging.getLogger(__name__)
EXPECTED_ROWS = 358_774
SIZE_RANK = {"Large hub": 0, "Medium hub": 1, "Small hub": 2, "Non-hub": 3}


@lru_cache(maxsize=1)
def load_flights() -> pd.DataFrame:
    cache = config.RUNS_DIR / "cache" / "flights.parquet"
    if cache.exists() and cache.stat().st_mtime >= config.FLIGHTS_CSV.stat().st_mtime:
        return pd.read_parquet(cache)
    df = pd.read_csv(
        config.FLIGHTS_CSV,
        low_memory=False,
        dtype={"ORIGIN_AIRPORT": str, "DESTINATION_AIRPORT": str, "TAIL_NUMBER": str,
               "AIRLINE": str, "CANCELLATION_REASON": str},
    )
    n_raw = len(df)
    ok = df.ORIGIN_AIRPORT.str.fullmatch(r"[A-Z]{3}") & df.DESTINATION_AIRPORT.str.fullmatch(r"[A-Z]{3}")
    df = df[ok.fillna(False)].reset_index(drop=True)
    log.info("flights.csv: %d rows raw, %d after airport-code filter", n_raw, len(df))
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def _leading_number(text) -> float:
    m = re.search(r"[\d,]+(?:\.\d+)?", str(text))
    if not m:
        raise ValueError(f"no number in {text!r}")
    return float(m.group(0).replace(",", ""))


@lru_cache(maxsize=1)
def load_airports() -> pd.DataFrame:
    df = pd.read_excel(config.WORKBOOK, sheet_name="airport_capacity", header=2)
    return df.set_index("IATA_CODE", drop=False)


def _wake_class(label) -> str:
    return str(label).split("(")[0].strip()


@lru_cache(maxsize=1)
def load_wake_table() -> dict:
    """{(leader, follower): nm}; key ('*','*') holds the default for unlisted pairs."""
    df = pd.read_excel(config.WORKBOOK, sheet_name="wake_separation", header=2)
    table = {}
    for _, r in df.iterrows():
        if str(r["leader"]).startswith("Any other"):
            table[("*", "*")] = float(r["min_separation_nm"])
        else:
            table[(_wake_class(r["leader"]), _wake_class(r["follower"]))] = float(r["min_separation_nm"])
    return table


def wake_nm(leader: str, follower: str) -> float:
    t = load_wake_table()
    return t.get((leader, follower), t[("*", "*")])


def wake_minutes(leader: str, follower: str) -> float:
    """Arrival wake spacing converted at the approach speed (PLAN section 10)."""
    return wake_nm(leader, follower) / config.APPROACH_SPEED_KT * 60


@lru_cache(maxsize=1)
def load_fuel_and_crew() -> dict:
    df = pd.read_excel(config.WORKBOOK, sheet_name="fuel_and_crew", header=0)
    return {r["rule"]: {"value": r["value"], "number": _leading_number(r["value"]),
                        "applies_to": r["applies_to"]} for _, r in df.iterrows()}


def check_constants() -> None:
    """Assert config.py matches the fuel_and_crew sheet."""
    fc = load_fuel_and_crew()
    assert fc["Final fuel reserve"]["number"] == config.FINAL_RESERVE_MIN
    assert fc["Holding fuel burn (narrowbody)"]["number"] == config.HOLD_BURN_KG_PER_H["Large"]
    assert fc["Holding fuel burn (widebody)"]["number"] == config.HOLD_BURN_KG_PER_H["Heavy"]
    assert fc["Assumed spare fuel on arrival"]["number"] == config.SPARE_FUEL_MIN
    assert fc["Flight crew max duty"]["number"] == config.CREW_MAX_DUTY_H
    assert fc["Ground crew shift"]["number"] == config.GROUND_SHIFT_H
    assert _leading_number(fc["Ground crew shift"]["value"].split("costs")[1]) == config.OVERTIME_MULT
    assert fc["Gate change notice"]["number"] == config.GATE_CHANGE_NOTICE_MIN


@lru_cache(maxsize=1)
def load_rules_of_play() -> pd.DataFrame:
    return pd.read_excel(config.WORKBOOK, sheet_name="rules_of_play", header=0)


def warm() -> None:
    """Load every cached table up front (call before starting worker threads)."""
    from . import forecast

    load_flights(); load_airports(); load_wake_table(); load_fuel_and_crew(); load_rules_of_play()
    forecast._population("WEATHER_DELAY", "DESTINATION_AIRPORT", "SCHEDULED_ARRIVAL")
    forecast._population("LATE_AIRCRAFT_DELAY", "ORIGIN_AIRPORT", "SCHEDULED_DEPARTURE")
