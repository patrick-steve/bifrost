"""Dashboard API smoke tests (scripted agents, no API key)."""
from fastapi.testclient import TestClient

from app.server import app

c = TestClient(app)


def test_meta_and_scenario():
    m = c.get("/api/meta").json()
    assert any(s["scenario_id"] == "showcase" for s in m["scenarios"])
    d = c.get("/api/scenario/showcase").json()
    assert d["public"]["scheduled_arrival"] == "06:08" and len(d["plans"]) == 101
    assert set(d["private"]) == {"ATC", "AIRLINE", "GROUND"}


def test_run_approve_reveal_and_pressure():
    r = c.post("/api/run", json={"scenario_id": "showcase"}).json()
    assert r["verify"]["ok"] and r["meta"]["status"] == "DONE"
    a = c.post(f"/api/run/{r['run_id']}/approve", json={"role": "ramp_lead", "scenario_id": "showcase"})
    assert a.status_code == 200 and a.json()["verify"]["ok"]
    assert c.post(f"/api/run/{r['run_id']}/approve", json={"role": "ramp_lead", "scenario_id": "showcase"}).status_code == 409
    rv = c.get(f"/api/reveal/{r['run_id']}?scenario_id=showcase").json()
    assert rv["actual"]["arrival_delay_min"] == 43
    p = c.post("/api/run", json={"scenario_id": "showcase", "pressure": True}).json()
    assert p["meta"]["status"] == "FALLBACK" and p["run_id"] != r["run_id"]
    assert any(e["event"] == "LOOSENING_ATTEMPT" for e in p["entries"])


def test_claude_without_key_is_refused(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert c.post("/api/run", json={"scenario_id": "showcase", "agents": "claude"}).status_code == 400


def test_bad_run_id_rejected():
    assert c.get("/api/run/..%2F..?scenario_id=showcase").status_code in (400, 404)


def test_page_served():
    assert c.get("/").status_code == 200 and c.get("/app.js").status_code == 200
    assert "meeting" in c.get("/").text.lower() or "storm" in c.get("/").text.lower()
    assert c.get("/dashboard").status_code == 200
