import json

from dn.consensus_log import ConsensusLog, read, verify, verify_entries


def test_chain_and_tamper(tmp_path):
    log = ConsensusLog(tmp_path / "log.jsonl")
    for i in range(5):
        log.append("X", 1, "CONTRACTS", {"i": i})
    assert verify(log.path)[0]
    entries = read(log.path)
    assert entries[0]["prev_hash"] == "0" * 64
    entries[2]["payload"]["i"] = 99
    ok, seq, _ = verify_entries(entries)
    assert not ok and seq == 2


def test_signature_tamper(tmp_path, showcase):
    from dn.run import backends_for, run_scenario

    _, log, _ = run_scenario(showcase, backends_for("scripted"), run_dir=tmp_path / "r")
    entries = read(log.path)
    i = next(i for i, e in enumerate(entries) if e["event"] == "CONTRACTS")
    entries[i]["payload"]["message"]["notes_for_humans"] = "forged"
    # recompute hashes so only the HMAC can catch it
    import hashlib
    from dn.consensus_log import GENESIS, canonical_json
    prev = GENESIS
    for e in entries:
        e["prev_hash"] = prev
        body = {k: v for k, v in e.items() if k != "hash"}
        e["hash"] = hashlib.sha256((prev + canonical_json(body)).encode()).hexdigest()
        prev = e["hash"]
    ok, seq, msg = verify_entries(entries)
    assert not ok and seq == i and "signature" in msg
