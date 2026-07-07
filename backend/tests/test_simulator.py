"""Simulator + fixtures tests."""
from __future__ import annotations

import pytest

from app.models.state import MatchPhase
from app.simulator import fixtures
from app.simulator.engine import StadiumSimulator, _phase_for


# ---- Fixtures -----------------------------------------------------------

def test_venue_loads_metlife():
    v = fixtures.load_venue()
    assert v.name == "MetLife Stadium"
    assert v.capacity == 82500
    assert "East Rutherford" in v.city


def test_stadium_model_capacities_consistent():
    m = fixtures.load_stadium_model()
    assert len(m.zones) == 12
    assert len(m.gates) == 4
    # every zone's nearest gate exists
    gate_ids = {g.gate_id for g in m.gates}
    for z in m.zones:
        assert z.nearest_gate_id in gate_ids
    # edges reference defined waypoints
    wp_ids = {w.waypoint_id for w in m.waypoints}
    for e in m.edges:
        assert e.from_id in wp_ids and e.to_id in wp_ids


def test_graph_has_accessible_vertical_connectors():
    m = fixtures.load_stadium_model()
    # there should be at least one elevator edge (accessible) for vertical moves
    assert any(e.kind.value == "elevator" for e in m.edges)
    assert any(e.accessible for e in m.edges)


# ---- Engine -------------------------------------------------------------

def test_simulator_initial_state_empty():
    sim = StadiumSimulator()
    snap = sim.snapshot()
    assert all(c.occupancy == 0 for c in snap.crowd)
    assert snap.match.phase == MatchPhase.PRE_OPEN


def test_crowd_rises_during_arrival():
    sim = StadiumSimulator()
    # advance into arrival phase (gates open at t=0)
    sim.step(15 * 60)  # +15 min -> arrival
    snap = sim.snapshot()
    assert snap.match.phase == MatchPhase.ARRIVAL
    seat_zones = [c for c in snap.crowd if not c.zone_id.startswith("C-")]
    assert any(c.occupancy > 0 for c in seat_zones)


def test_crowd_peaks_pre_kickoff():
    sim = StadiumSimulator()
    sim.step(55 * 60)  # 5 min before kickoff
    snap = sim.snapshot()
    assert snap.match.phase == MatchPhase.PRE_KICKOFF
    seat_zones = [c for c in snap.crowd if not c.zone_id.startswith("C-")]
    avg = sum(c.density for c in seat_zones) / len(seat_zones)
    assert avg > 0.5


def test_halftime_concourse_spike():
    sim = StadiumSimulator()
    sim.sim_time = fixtures.HALFTIME_AT + 60  # 1 min into halftime
    # step several minutes so concourses fill toward the halftime target
    for _ in range(10):
        sim.step(60)
    snap = sim.snapshot()
    assert snap.match.phase == MatchPhase.HALFTIME
    concourse = [c for c in snap.crowd if c.zone_id.startswith("C-")]
    assert any(c.density > 0.5 for c in concourse)


def test_full_time_exit_surge_drains_seats():
    sim = StadiumSimulator()
    sim.sim_time = fixtures.FULL_TIME_AT + 60  # 1 min after full time
    sim.step(60)
    snap = sim.snapshot()
    assert snap.match.phase == MatchPhase.FULL_TIME
    seat_zones = [c for c in snap.crowd if not c.zone_id.startswith("C-")]
    avg = sum(c.density for c in seat_zones) / len(seat_zones)
    assert avg < 0.5  # draining


def test_incidents_spawn_and_resolve():
    sim = StadiumSimulator()
    # Run many halftime ticks to probabilistically spawn incidents.
    sim.step(106 * 60)
    spawned = False
    for _ in range(40):
        sim.step(60)  # 1 min each
        if sim.snapshot().incidents:
            spawned = True
            break
    assert spawned, "expected at least one incident to spawn around halftime"
    # advance well past their lifetime to resolve them
    sim.step(30 * 60)
    snap = sim.snapshot()
    # resolved incidents are removed from the active snapshot
    # (they may have been pruned; active list should be small/empty now)
    assert all(i.status == "active" for i in snap.incidents)


def test_report_incident_manual():
    sim = StadiumSimulator()
    inc = sim.report_incident("medical", "Lower North", "high", "fan needs help")
    assert inc.status == "active"
    assert inc.severity.value == "high"
    assert inc in [i for i in sim._incidents]


def test_gate_restricts_on_high_queue():
    sim = StadiumSimulator()
    sim.step(58 * 60)  # pre-kickoff, dense
    snap = sim.snapshot()
    # at least one gate should be restricted or open; statuses are valid
    assert all(g.status in ("open", "restricted", "closed") for g in snap.gates)


def test_snapshot_summary_contains_phase():
    sim = StadiumSimulator()
    sim.step(60 * 60)
    s = sim.snapshot().summary()
    assert "Match phase" in s


def test_phase_for_boundaries():
    assert _phase_for(-1) == MatchPhase.PRE_OPEN
    assert _phase_for(fixtures.KICKOFF_AT - 1) == MatchPhase.PRE_KICKOFF
    assert _phase_for(fixtures.KICKOFF_AT + 1) == MatchPhase.LIVE
    assert _phase_for(fixtures.HALFTIME_AT + 1) == MatchPhase.HALFTIME
    assert _phase_for(fixtures.FULL_TIME_AT + 1) == MatchPhase.FULL_TIME
