from dn import mandates as md
from dn.consensus_log import verify_signature
from dn.schemas import ForbidStrategy, GateChangeNotice


def test_signed():
    ms = md.issue_all()
    assert all(verify_signature(r, m) for r, m in ms.items())


def test_commitment_claims():
    ms = md.issue_all()
    assert md.check_commitment(ms["ATC"], ["gate"]) == ["gate"]
    assert md.check_commitment(ms["GROUND"], ["gate"]) == []
    assert md.check_commitment(ms["AIRLINE"], ["strategy", "ground_delay_min"]) == []


def test_contract_permissions():
    ms = md.issue_all()
    assert md.check_contract(ms["ATC"], GateChangeNotice(publisher="ATC", minutes=5))
    assert md.check_contract(ms["ATC"], ForbidStrategy(publisher="ATC", strategy="DIVERT"))
    assert md.check_contract(ms["ATC"], ForbidStrategy(publisher="ATC", strategy="HOLD")) is None
