from __future__ import annotations

import concurrent.futures
import random
import time
import pytest
from fastapi.testclient import TestClient

from app.knowledge.store import KnowledgeStore
from app.models.roles import Role
from app.simulator.engine import StadiumSimulator
from app.simulator import fixtures
from app.tools.handlers import ToolContext, find_route
from app.models.stadium import StadiumModel, Waypoint, PathEdge, EdgeKind, LevelName
from app.main import create_app


def build_custom_detour_model() -> StadiumModel:
    """Builds a stadium model with a detour from WP-T-RAIL via WP-G-S or WP-G-E."""
    venue = fixtures.load_venue()
    levels = fixtures.load_levels()
    zones = fixtures.load_zones()
    gates = fixtures.load_gates()
    amenities = fixtures.load_amenities()
    waypoints = fixtures.load_waypoints()
    edges = fixtures.load_edges()
    parking = fixtures.load_parking()
    transit = fixtures.load_transit()

    # Add custom waypoint and edges to create an alternative detour
    new_waypoint = Waypoint(waypoint_id="WP-T-RAIL", name="Transit Rail Station", level=LevelName.LOWER_BOWL)
    waypoints.append(new_waypoint)

    # Flat edge from WP-T-RAIL to WP-G-S: 100.0m
    edges.append(PathEdge.make("WP-T-RAIL", "WP-G-S", EdgeKind.FLAT, 100.0))
    edges.append(PathEdge.make("WP-G-S", "WP-T-RAIL", EdgeKind.FLAT, 100.0))

    # Flat edge from WP-T-RAIL to WP-G-E: 200.0m
    edges.append(PathEdge.make("WP-T-RAIL", "WP-G-E", EdgeKind.FLAT, 200.0))
    edges.append(PathEdge.make("WP-G-E", "WP-T-RAIL", EdgeKind.FLAT, 200.0))

    # Flat edge connecting East and South concourses: 100.0m
    edges.append(PathEdge.make("WP-C-L-E", "WP-C-L-S", EdgeKind.FLAT, 100.0))
    edges.append(PathEdge.make("WP-C-L-S", "WP-C-L-E", EdgeKind.FLAT, 100.0))

    return StadiumModel(
        venue=venue,
        levels=levels,
        zones=zones,
        gates=gates,
        amenities=amenities,
        waypoints=waypoints,
        edges=edges,
        parking=parking,
        transit=transit,
    )


@pytest.mark.parametrize(
    "phase_name,sim_time",
    [
        ("pre_match", 3000.0),      # MatchPhase.PRE_KICKOFF
        ("first_half", 4200.0),     # MatchPhase.LIVE
        ("halftime", 6600.0),       # MatchPhase.HALFTIME
        ("second_half", 7500.0),    # MatchPhase.LIVE
        ("post_match", 9600.0),     # MatchPhase.FULL_TIME
    ]
)
def test_concurrent_scenarios_and_routing_stress(phase_name, sim_time):
    """Verifies that simulator executes concurrent operations without race conditions,
    deadlocks, or exceptions, and routes adapt dynamically.
    """
    model = build_custom_detour_model()
    sim = StadiumSimulator(model=model)
    sim.sim_time = sim_time
    
    # Run a step to initialize time-dependent state
    sim.step(0.0)

    # Force crowd density >85% for all zones
    with sim._lock:
        for cd in sim._crowd.values():
            cd.density = 0.90
            cd.occupancy = int(cd.capacity * 0.90)

    ctx = ToolContext(simulator=sim, model=model, knowledge=KnowledgeStore())

    # Shared flags/variables
    stop_event = False
    routing_results = []
    errors = []

    def scenario_injector():
        nonlocal stop_event
        rng = random.Random(1)
        while not stop_event:
            try:
                scenario = rng.choice(["gate_malfunction", "medical_emergency", "concession_surge", "reset"])
                sim.trigger_scenario(scenario)
                time.sleep(0.01)
            except Exception as e:
                errors.append(f"ScenarioInjector error: {e}")

    def incident_handler():
        nonlocal stop_event
        rng = random.Random(2)
        while not stop_event:
            try:
                # Randomly report, dispatch, or resolve incidents
                action = rng.choice(["report", "dispatch", "resolve"])
                if action == "report":
                    sim.report_incident("medical", "Lower South", "medium")
                elif action == "dispatch":
                    active = [i for i in sim._incidents if i.status == "active"]
                    if active:
                        inc = rng.choice(active)
                        sim.dispatch_incident(inc.incident_id, "Staff-Stress")
                else:
                    active = [i for i in sim._incidents if i.status == "active"]
                    if active:
                        inc = rng.choice(active)
                        sim.resolve_incident(inc.incident_id)
                time.sleep(0.01)
            except Exception as e:
                # Dispatches/resolves might throw expected errors if other thread resolved them first
                if "already resolved" not in str(e) and "not found" not in str(e):
                    errors.append(f"IncidentHandler error: {e}")

    def routing_client():
        nonlocal stop_event
        while not stop_event:
            try:
                # Route from WP-T-RAIL to WP-Z-L-S
                res = find_route({"from_waypoint_id": "WP-T-RAIL", "to_waypoint_id": "WP-Z-L-S"}, ctx)
                if "error" not in res:
                    routing_results.append(res)
                else:
                    errors.append(f"Routing client returned error: {res}")
                time.sleep(0.005)
            except Exception as e:
                errors.append(f"Routing client exception: {e}")

    # Launch threads
    threads = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        futures.append(executor.submit(scenario_injector))
        futures.append(executor.submit(incident_handler))
        futures.append(executor.submit(incident_handler))
        futures.append(executor.submit(routing_client))
        futures.append(executor.submit(routing_client))
        futures.append(executor.submit(routing_client))
        futures.append(executor.submit(routing_client))

        # Let them run concurrently for 1.5 seconds
        time.sleep(1.5)
        stop_event = True

        # Wait for all futures to complete
        concurrent.futures.wait(futures)

    # Check for errors
    assert len(errors) == 0, f"Encountered concurrent errors: {errors}"
    assert len(routing_results) > 0, "No routes were calculated"

    # Verify that Dijkstra correctly dynamically re-routed paths
    # 1. Check routing options observed during the run
    steps_seen = set()
    for r in routing_results:
        steps_seen.add(tuple(r["steps"]))

    # Verify that we observe both the direct route (when gate is open)
    # and the east gate detour (when South gate has high penalty / malfunction)
    direct_route = ("WP-T-RAIL", "WP-G-S", "WP-C-L-S", "WP-Z-L-S")
    detour_route = ("WP-T-RAIL", "WP-G-E", "WP-C-L-E", "WP-C-L-S", "WP-Z-L-S")

    # Assert that we actually observed dynamic rerouting in action
    assert direct_route in steps_seen, "Direct route was never chosen"
    assert detour_route in steps_seen, "Detour route was never chosen when gate was restricted"


def test_concurrent_api_requests_stress():
    """Simulates concurrent HTTP requests against the FastAPI server endpoints to ensure thread-safety."""
    from app.core.config import settings
    original_requests = settings.rate_limit_requests
    settings.rate_limit_requests = 100000

    try:
        app = create_app()
        with TestClient(app) as client:
            stop_event = False
            errors = []

            def state_poller():
                nonlocal stop_event
                while not stop_event:
                    try:
                        r = client.get("/state")
                        assert r.status_code == 200
                        time.sleep(0.01)
                    except Exception as e:
                        errors.append(f"state_poller error: {e}")

            def scenario_triggerer():
                nonlocal stop_event
                rng = random.Random(42)
                while not stop_event:
                    try:
                        scenario = rng.choice(["gate_malfunction", "medical_emergency", "concession_surge", "reset"])
                        r = client.post("/simulator/scenario", json={"scenario": scenario})
                        assert r.status_code == 200
                        time.sleep(0.02)
                    except Exception as e:
                        errors.append(f"scenario_triggerer error: {e}")

            def chat_client():
                nonlocal stop_event
                while not stop_event:
                    try:
                        r = client.post("/chat", json={"role": "fan", "message": "What is the status of Gate G-S?", "language": "en"})
                        assert r.status_code == 200
                        time.sleep(0.02)
                    except Exception as e:
                        errors.append(f"chat_client error: {e}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                futures.append(executor.submit(state_poller))
                futures.append(executor.submit(state_poller))
                futures.append(executor.submit(scenario_triggerer))
                futures.append(executor.submit(scenario_triggerer))
                futures.append(executor.submit(chat_client))
                futures.append(executor.submit(chat_client))

                time.sleep(1.5)
                stop_event = True
                concurrent.futures.wait(futures)

            assert len(errors) == 0, f"Encountered API concurrent errors: {errors}"
    finally:
        settings.rate_limit_requests = original_requests
