"""Every message and state schema (IMPLEMENTATION.md section 10). Pydantic v2."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["ATC", "AIRLINE", "GROUND"]
Strategy = Literal["GROUND_DELAY", "HOLD", "DIVERT"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- plans
class Plan(Strict):
    plan_id: str
    strategy: Strategy
    ground_delay_min: int = 0
    target_arrival_min: Optional[int] = None  # None for DIVERT
    gate: Optional[str] = None  # None for DIVERT
    hold_limit_min: int = 0


# ----------------------------------------------------------------------- contracts
class _ContractBase(Strict):
    publisher: Role
    reason: str = Field(default="", max_length=200)


class AvailableArrivalMinutes(_ContractBase):
    type: Literal["available_arrival_minutes"] = "available_arrival_minutes"
    minutes: list[int]


class MaxGroundDelay(_ContractBase):
    type: Literal["max_ground_delay"] = "max_ground_delay"
    minutes: int


class ForbidStrategy(_ContractBase):
    type: Literal["forbid_strategy"] = "forbid_strategy"
    strategy: Strategy


class GateWindow(Strict):
    gate: str
    free_from: int
    free_to: int


class GateWindowFree(_ContractBase):
    type: Literal["gate_window_free"] = "gate_window_free"
    windows: list[GateWindow]


class GateChangeNotice(_ContractBase):
    type: Literal["gate_change_notice"] = "gate_change_notice"
    minutes: int


class LatestArrival(_ContractBase):
    type: Literal["latest_arrival"] = "latest_arrival"
    minute: int


Contract = Annotated[
    Union[AvailableArrivalMinutes, MaxGroundDelay, ForbidStrategy, GateWindowFree,
          GateChangeNotice, LatestArrival],
    Field(discriminator="type"),
]


class ReasonCode(str, Enum):
    FUEL_RISK = "FUEL_RISK"
    CONNECTIONS = "CONNECTIONS"
    DUTY = "DUTY"
    OVERTIME = "OVERTIME"
    THROUGHPUT = "THROUGHPUT"
    WAKE_SEPARATION = "WAKE_SEPARATION"
    TURBULENCE = "TURBULENCE"
    GATE_CONFLICT = "GATE_CONFLICT"
    NEXT_LEG = "NEXT_LEG"
    ARRIVAL_DELAY = "ARRIVAL_DELAY"
    DIVERSION_RISK = "DIVERSION_RISK"
    OUTSIDE_CONTRACTS = "OUTSIDE_CONTRACTS"
    OUTSIDE_MANDATE = "OUTSIDE_MANDATE"


# ------------------------------------------------------------------------ messages
# stated_limits keys the coordinator understands (consistency check).
LIMIT_KEYS = {
    # key: (direction, plan field it bounds or None)
    "hold_limit_min": ("max", "hold_limit_min"),
    "reserve_min": ("min", None),
    "max_ground_delay_min": ("max", "ground_delay_min"),
}


class Turn1Contracts(Strict):
    role: Role
    turn: Literal[1] = 1
    contracts: list[Contract]
    stated_limits: dict[str, float] = Field(default_factory=dict)
    notes_for_humans: str = Field(default="", max_length=300)
    signature: str = ""


class Turn2Ranking(Strict):
    role: Role
    turn: Literal[2] = 2
    ranking: list[str] = Field(min_length=1, max_length=5)
    extra_contracts: list[Contract] = Field(default_factory=list)
    stated_limits: dict[str, float] = Field(default_factory=dict)  # optional restatement
    reasons: list[ReasonCode] = Field(default_factory=list)
    justification: str = Field(default="", max_length=400)
    signature: str = ""


class Turn3Commitment(Strict):
    role: Role
    turn: Literal[3] = 3
    plan_id: str
    accept: bool
    owned_fields: list[str] = Field(default_factory=list)
    stated_limits: dict[str, float] = Field(default_factory=dict)  # optional restatement
    reason_if_reject: Optional[ReasonCode] = None
    signature: str = ""  # HMAC added by code, never by the LLM


TurnMessage = Union[Turn1Contracts, Turn2Ranking, Turn3Commitment]


# ------------------------------------------------------------------------ mandates
class Mandate(Strict):
    role: Role
    organisation: str
    may_set: list[str]
    may_forbid: list[str] = Field(default_factory=list)
    may_not: list[str]
    overtime_budget_min: Optional[int] = None
    signature: str = ""


# ---------------------------------------------------------------------- scenario
class Synthetic(Strict):
    synthetic: Literal[True] = True


class AirportRecord(Strict):
    iata: str
    name: str
    city: str
    state: str
    size_class: str
    active_runways: int
    gates: int
    max_runway_ops_per_hour: int
    min_turnaround_min: int
    spare_gates_at_any_time: int


class NextLeg(Strict):
    flight_number: str
    destination: str
    scheduled_departure_min: int
    scheduled_time_min: Optional[int] = None


class PublicScenario(Strict):
    scenario_id: str
    date: str
    month: int
    day: int
    airline: str
    flight_number: str
    tail: str
    origin: str
    destination: str
    scheduled_departure_min: int
    scheduled_arrival_min: int
    scheduled_time_min: int
    distance: int
    wake_category: Literal["Large", "Heavy"]
    decision_mode: Literal["pre_departure", "airborne"]
    decision_time_min: int
    disruption: Literal["weather_at_destination", "late_inbound_aircraft"]
    destination_airport: AirportRecord
    alternate: Optional[str] = None
    next_leg: Optional[NextLeg] = None


class BookedArrival(Strict):
    minute: int
    wake: Literal["Large", "Heavy"]


class AtcPrivate(Synthetic):
    booked_arrivals: list[BookedArrival]
    window_start_min: int
    window_end_min: int
    reduced_arrival_capacity_per_h: float
    taxiway_closed: Optional[str] = None


class Connection(Strict):
    label: str
    passengers: int
    latest_arrival_min: int


class AirlinePrivate(Synthetic):
    spare_fuel_min: int
    final_reserve_min: int
    holding_burn_kg_per_h: int
    crew_duty_used_h: float
    connections: list[Connection]
    connections_note: str = ""
    holding_turbulence: Literal["light", "moderate"]


class BusyInterval(Strict):
    start: int
    end: int


class GateState(Strict):
    gate: str
    busy: list[BusyInterval]


class GroundPrivate(Synthetic):
    assigned_gate: str = "G1"
    gates: list[GateState]
    min_turnaround_min: int
    shift_end_min: int
    next_leg_departure_min: Optional[int] = None


class SealedOutcome(Strict):
    """Real 2015 outcome. Never shown to agents or the coordinator."""
    weather_delay: float
    late_aircraft_delay: float
    arrival_delay: float
    arrival_time: Optional[float] = None
    departure_delay: Optional[float] = None
    next_leg_departure_delay: Optional[float] = None
    next_leg_late_aircraft_delay: Optional[float] = None
    raw: dict = Field(default_factory=dict)


# ------------------------------------------------------------------------ outputs
class RecommendedPlan(Strict):
    plan: Plan
    signatures: dict[str, str]
    escalations: list[str]
    summary: str
    turns_used: int


class FallbackResult(Strict):
    plan: Plan
    branch: str
    reason: str
    escalations: list[str]
    explanation: list[str] = Field(default_factory=list)


class Event(str, Enum):
    MANDATE_ISSUED = "MANDATE_ISSUED"
    SCENARIO_PUBLIC = "SCENARIO_PUBLIC"
    FORECAST = "FORECAST"
    CONTRACTS = "CONTRACTS"
    FEASIBLE_SET = "FEASIBLE_SET"
    RANKING = "RANKING"
    SELECTED = "SELECTED"
    COMMITMENT = "COMMITMENT"
    SCHEMA_REJECT = "SCHEMA_REJECT"
    MANDATE_VIOLATION = "MANDATE_VIOLATION"
    SELF_CONTRADICTION = "SELF_CONTRADICTION"
    LOOSENING_ATTEMPT = "LOOSENING_ATTEMPT"
    FALLBACK = "FALLBACK"
    DONE = "DONE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
