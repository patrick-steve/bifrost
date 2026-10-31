"""All constants from PLAN.md section 10 and IMPLEMENTATION.md section 4.1."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DN_DATA_DIR", ROOT / "data"))
# Vercel's filesystem is read-only except /tmp.
RUNS_DIR = Path(os.environ.get("DN_RUNS_DIR", "/tmp/bifrost-runs" if os.environ.get("VERCEL") else ROOT / "runs"))
RESULTS_DIR = ROOT / "results"  # committed evaluation summaries, read when runs/ has none
FLIGHTS_CSV = DATA_DIR / "flights.csv"
FLIGHTS_PARQUET = DATA_DIR / "flights.parquet"  # committed compact copy of flights.csv
WORKBOOK = DATA_DIR / "challenge2_operational_constraints.xlsx"

try:  # optional .env support
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

SEED = 42
SPARE_FUEL_MIN = 45
FINAL_RESERVE_MIN = 30
HOLD_BUDGET_MIN = SPARE_FUEL_MIN - FINAL_RESERVE_MIN  # 15
HOLD_BURN_KG_PER_H = {"Large": 2400, "Heavy": 6500}
HEAVY_AIRLINES = {"AA", "UA", "DL", "HA"}
HEAVY_MIN_DISTANCE = 2500
APPROACH_SPEED_KT = 150
WEATHER_CAPACITY_FACTOR = 0.5
ARRIVAL_SHARE = 0.5
BACKGROUND_LOAD = 0.8
CREW_MAX_DUTY_H = 13
GROUND_SHIFT_H = 8
OVERTIME_MULT = 1.5
GATE_CHANGE_NOTICE_MIN = 20
GROUND_DELAY_STEP_MIN = 5
GROUND_DELAY_MAX_MIN = 120
PREDEPARTURE_MAX_SCHEDULED_TIME_MIN = 120
DIVERT_RISK_TARGET = 0.10
MAX_TURNS = 3

# Derived / protocol constants
GROUND_OVERTIME_BUDGET_MIN = 60
AGENT_TIMEOUT_S = 30
BROADCAST_MAX_PLANS = 15
DEFAULT_NEXT_LEG_BLOCK_MIN = 60
ATC_WINDOW_BEFORE_MIN = 30
ATC_WINDOW_AFTER_MIN = 180

AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
ORG_KEYS = {
    "ATC": os.environ.get("ORG_KEY_ATC", "demo-only-atc-key"),
    "AIRLINE": os.environ.get("ORG_KEY_AIRLINE", "demo-only-airline-key"),
    "GROUND": os.environ.get("ORG_KEY_GROUND", "demo-only-ground-key"),
}
ROLES = ("ATC", "AIRLINE", "GROUND")

# Columns agents must never see (PLAN.md decision 4).
SEALED_COLUMNS = (
    "WEATHER_DELAY", "ARRIVAL_DELAY", "ARRIVAL_TIME", "WHEELS_ON", "TAXI_IN",
    "ELAPSED_TIME", "AIR_TIME", "DEPARTURE_TIME", "DEPARTURE_DELAY", "TAXI_OUT",
    "WHEELS_OFF", "AIR_SYSTEM_DELAY", "SECURITY_DELAY", "AIRLINE_DELAY",
    "LATE_AIRCRAFT_DELAY", "DIVERTED", "CANCELLED", "CANCELLATION_REASON",
)
