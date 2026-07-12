from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models.state import MatchPhase, IncidentSeverity
from app.simulator.engine import StadiumSimulator
from app.main import create_app


def test_simulator_scenario_gate_malfunction():
    sim = StadiumSimulator()
    # Before trigger
    assert sim._gates["G-S"].status == "open"
    assert sim._gates["G-S"].queue_minutes == 0.0

    incident = sim.trigger_scenario("gate_malfunction")
    assert incident is not None
    assert incident.type == "entry_bottleneck"
    assert incident.location == "Gate 2 (South Gate)"
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.description == "Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."
    assert incident.zone_id == "G-S"

    # Verify state updated
    assert sim._gates["G-S"].status == "restricted"
    assert sim._gates["G-S"].queue_minutes == 45.0
    assert sim._gates["G-S"].throughput_per_min == 0

    # Tick simulation and verify state persists
    sim.step(60)
    assert sim._gates["G-S"].status == "restricted"
    assert sim._gates["G-S"].queue_minutes == 45.0
    assert sim._gates["G-S"].throughput_per_min == 0

    # Ensure incident is active and didn't get resolved/removed
    active_incidents = [i for i in sim._incidents if i.status == "active"]
    assert incident in active_incidents


def test_simulator_scenario_medical_emergency():
    sim = StadiumSimulator()
    incident = sim.trigger_scenario("medical_emergency")
    assert incident is not None
    assert incident.type == "medical"
    assert incident.location == "Section 104 (Lower North)"
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.description == "Medical emergency reported at Section 104. Paramedics dispatched."
    assert incident.zone_id == "L-N"

    # Tick simulation and verify state persists
    sim.step(60)
    active_incidents = [i for i in sim._incidents if i.status == "active"]
    assert incident in active_incidents


def test_simulator_scenario_concession_surge():
    sim = StadiumSimulator()
    incident = sim.trigger_scenario("concession_surge")
    assert incident is not None
    assert incident.type == "congestion"
    assert incident.location == "Concourse A (Club North)"
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.description == "Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."
    assert incident.zone_id == "C-N"

    # Verify state updated
    assert sim._crowd["C-N"].occupancy == int(sim._crowd["C-N"].capacity * 0.90)
    assert sim._crowd["C-N"].density == 0.90

    # Tick simulation and verify state persists
    sim.step(60)
    assert sim._crowd["C-N"].occupancy == int(sim._crowd["C-N"].capacity * 0.90)
    assert sim._crowd["C-N"].density == 0.90
    active_incidents = [i for i in sim._incidents if i.status == "active"]
    assert incident in active_incidents


def test_simulator_scenario_reset():
    sim = StadiumSimulator()
    
    # Trigger gate malfunction
    sim.trigger_scenario("gate_malfunction")
    sim.trigger_scenario("concession_surge")
    
    # Verify scenarios active
    assert "gate_malfunction" in sim._active_scenarios
    assert "concession_surge" in sim._active_scenarios
    assert len([i for i in sim._incidents if i.status == "active"]) == 2

    # Reset
    res = sim.trigger_scenario("reset")
    assert res is None
    assert len(sim._active_scenarios) == 0
    assert len([i for i in sim._incidents if i.status == "active"]) == 0

    # Check nominal
    assert sim._gates["G-S"].status == "open"
    assert sim._gates["G-S"].queue_minutes == 0.0
    assert sim._crowd["C-N"].density == 0.0


def test_api_scenario_endpoints():
    app = create_app()
    with TestClient(app) as client:
        # Invalid scenario
        r = client.post("/simulator/scenario", json={"scenario": "invalid_name"})
        assert r.status_code == 400
        
        # Valid scenario: gate_malfunction
        r = client.post("/simulator/scenario", json={"scenario": "gate_malfunction"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["incident"]["type"] == "entry_bottleneck"
        assert data["incident"]["location"] == "Gate 2 (South Gate)"

        # Valid scenario: reset
        r = client.post("/simulator/scenario", json={"scenario": "reset"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["incident"] is None
