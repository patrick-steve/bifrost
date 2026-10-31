"""Per-organisation mandates (IMPLEMENTATION.md section 8)."""
from __future__ import annotations

from . import config
from .consensus_log import sign
from .schemas import Mandate

_DEFS = {
    "ATC": dict(organisation="Air navigation service provider", may_set=["target_arrival_min"],
                may_forbid=["HOLD", "GROUND_DELAY"], may_not=["gate", "divert_approval"]),
    "AIRLINE": dict(organisation="Airline operations control", may_set=["strategy", "ground_delay_min"],
                    may_forbid=["HOLD", "GROUND_DELAY"],
                    may_not=["gate", "target_arrival_min", "divert_approval"]),
    "GROUND": dict(organisation="Ground handling", may_set=["gate"], may_forbid=[],
                   may_not=["strategy", "target_arrival_min", "divert_approval"],
                   overtime_budget_min=config.GROUND_OVERTIME_BUDGET_MIN),
}
# Which contract types each organisation may publish.
ALLOWED_CONTRACTS = {
    "ATC": {"available_arrival_minutes", "forbid_strategy"},
    "AIRLINE": {"max_ground_delay", "latest_arrival", "forbid_strategy"},
    "GROUND": {"gate_window_free", "gate_change_notice"},
}
DIVERT_ESCALATION = "DIVERT needs airline duty manager approval"


def issue(role: str) -> Mandate:
    m = Mandate(role=role, **_DEFS[role])
    return m.model_copy(update={"signature": sign(role, m)})


def issue_all() -> dict[str, Mandate]:
    return {r: issue(r) for r in config.ROLES}


def check_commitment(mandate: Mandate, owned_fields: list[str]) -> list[str]:
    """Fields claimed outside the mandate. Empty list = OK."""
    return [f for f in owned_fields if f not in mandate.may_set]


def check_contract(mandate: Mandate, contract) -> str | None:
    """Reason string if this organisation may not publish this contract."""
    if contract.publisher != mandate.role:
        return f"{mandate.role} published a contract as {contract.publisher}"
    if contract.type not in ALLOWED_CONTRACTS[mandate.role]:
        return f"{mandate.role} may not publish {contract.type}"
    if contract.type == "forbid_strategy" and contract.strategy not in mandate.may_forbid:
        return f"{mandate.role} may not forbid {contract.strategy}"
    return None
