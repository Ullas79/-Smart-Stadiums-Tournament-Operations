"""Verification tests for Milestone M2.

Verifies:
1. Telemetry simulator updates correctly (time advances, phases change).
2. Polling interval is <= 2s (checked against frontend source code).
3. Scenario injection triggers 3 custom events ("Gate 2 Turnstile Malfunction",
   "Medical Emergency at Section 104", "Half-Time Concession Surge").
4. Reset recovers stadium state.
5. System adapts instantly.
"""
from __future__ import annotations

import re
from pathlib import Path
from fastapi.testclient import TestClient

from app.models.state import MatchPhase, IncidentSeverity
from app.simulator.engine import StadiumSimulator
from app.main import create_app


def test_polling_interval_in_frontend():
    """Verify that the frontend polling interval is <= 2s (e.g. 1.5s)."""
    # Project root is backend/.. -> root.
    root_dir = Path(__file__).resolve().parents[2]
    app_tsx_path = root_dir / "frontend" / "src" / "App.tsx"
    
    assert app_tsx_path.exists(), f"Frontend App.tsx not found at {app_tsx_path}"
    
    content = app_tsx_path.read_text(encoding="utf-8")
    
    # Search for setInterval(poll, <number>)
    match = re.search(r"setInterval\(\s*poll\s*,\s*(\d+)\s*\)", content)
    assert match is not None, "Could not find setInterval(poll, ...) in App.tsx"
    
    interval_ms = int(match.group(1))
    interval_seconds = interval_ms / 1000.0
    
    print(f"Detected polling interval: {interval_ms}ms ({interval_seconds}s)")
    assert interval_seconds <= 2.0, f"Polling interval of {interval_seconds}s exceeds 2.0s limit!"


def test_telemetry_simulator_updates_correctly():
    """Verify that simulator updates correctly and advances phases/time."""
    sim = StadiumSimulator()
    
    # 1. Initial State Check
    snap = sim.snapshot()
    assert snap.match.phase == MatchPhase.PRE_OPEN
    assert sim.sim_time == -10 * 60  # -10 minutes before kickoff
    
    # 2. Step simulator forward
    # 15 minutes in real time * sim_speed 60 = 900 seconds or 15 sim minutes
    sim.step(15 * 60)
    snap2 = sim.snapshot()
    assert snap2.match.phase == MatchPhase.ARRIVAL
    assert sim.sim_time == 5 * 60
    
    # Crowd occupancy should start filling
    occupancies = [c.occupancy for c in snap2.crowd]
    assert any(o > 0 for o in occupancies), "Expected crowd occupancy to grow"
    
    # Step into kickoff
    sim.step(60 * 60) # 1 hour further
    snap3 = sim.snapshot()
    assert snap3.match.phase == MatchPhase.LIVE
    
    # Check that transit load/congestion updates
    assert any(t.congestion in ("low", "moderate", "high") for t in snap3.transit)


def test_scenario_injection_gate_malfunction():
    """Verify Gate 2 Turnstile Malfunction scenario triggers correctly."""
    sim = StadiumSimulator()
    incident = sim.trigger_scenario("gate_malfunction")
    
    assert incident is not None
    assert incident.type == "entry_bottleneck"
    assert incident.location == "Gate 2 (South Gate)"
    assert incident.severity == IncidentSeverity.HIGH
    assert "malfunction" in incident.description
    
    # Verify state updates immediately
    assert sim._gates["G-S"].status == "restricted"
    assert sim._gates["G-S"].queue_minutes == 45.0
    assert sim._gates["G-S"].throughput_per_min == 0


def test_scenario_injection_medical_emergency():
    """Verify Medical Emergency at Section 104 scenario triggers correctly."""
    sim = StadiumSimulator()
    incident = sim.trigger_scenario("medical_emergency")
    
    assert incident is not None
    assert incident.type == "medical"
    assert incident.location == "Section 104 (Lower North)"
    assert incident.severity == IncidentSeverity.HIGH
    assert "Section 104" in incident.description


def test_scenario_injection_concession_surge():
    """Verify Half-Time Concession Surge scenario triggers correctly."""
    sim = StadiumSimulator()
    incident = sim.trigger_scenario("concession_surge")
    
    assert incident is not None
    assert incident.type == "congestion"
    assert incident.location == "Concourse A (Club North)"
    assert incident.severity == IncidentSeverity.HIGH
    
    # Verify crowd state updates immediately
    assert sim._crowd["C-N"].occupancy == int(sim._crowd["C-N"].capacity * 0.90)
    assert sim._crowd["C-N"].density == 0.90


def test_reset_recovers_stadium_state():
    """Verify that reset clears scenarios and recovers state to nominal."""
    sim = StadiumSimulator()
    
    # Inject scenarios
    sim.trigger_scenario("gate_malfunction")
    sim.trigger_scenario("medical_emergency")
    sim.trigger_scenario("concession_surge")
    
    # Verify scenarios active
    assert len(sim._active_scenarios) == 3
    assert len(sim.snapshot().incidents) == 3
    
    # Trigger Reset
    sim.trigger_scenario("reset")
    
    # Verify clean state
    assert len(sim._active_scenarios) == 0
    assert len(sim.snapshot().incidents) == 0
    
    # Verify nominal values restored
    assert sim._gates["G-S"].status == "open"
    assert sim._gates["G-S"].queue_minutes == 0.0
    assert sim._crowd["C-N"].density == 0.0


def test_system_adapts_instantly():
    """Verify that triggering a scenario via API updates state instantly."""
    app = create_app()
    with TestClient(app) as client:
        # Check initial incidents
        r = client.get("/state")
        assert r.status_code == 200
        initial_state = r.json()
        assert len(initial_state["incidents"]) == 0
        
        # Inject Gate Malfunction
        r = client.post("/simulator/scenario", json={"scenario": "gate_malfunction"})
        assert r.status_code == 200
        
        # Immediately call GET /state and verify incident is present
        r = client.get("/state")
        assert r.status_code == 200
        updated_state = r.json()
        assert len(updated_state["incidents"]) == 1
        assert updated_state["incidents"][0]["location"] == "Gate 2 (South Gate)"
        
        # Inject Concession Surge
        r = client.post("/simulator/scenario", json={"scenario": "concession_surge"})
        assert r.status_code == 200
        
        # Verify instantly available in state
        r = client.get("/state")
        state_after_surge = r.json()
        assert len(state_after_surge["incidents"]) == 2
        # verify concession density instantly changed to 90%
        cn_zone = next(z for z in state_after_surge["crowd"] if z["zone_id"] == "C-N")
        assert cn_zone["density"] == 0.90
        
        # Reset State via API
        r = client.post("/simulator/scenario", json={"scenario": "reset"})
        assert r.status_code == 200
        
        # Verify instantly cleared
        r = client.get("/state")
        final_state = r.json()
        assert len(final_state["incidents"]) == 0
        cn_zone_reset = next(z for z in final_state["crowd"] if z["zone_id"] == "C-N")
        assert cn_zone_reset["density"] == 0.0
