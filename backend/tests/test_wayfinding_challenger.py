"""Adversarial wayfinding verification tests."""
from __future__ import annotations

import pytest
from app.knowledge.store import KnowledgeStore
from app.models.roles import Role
from app.simulator.engine import StadiumSimulator
from app.simulator import fixtures
from app.tools.handlers import ToolContext, find_route
from app.models.stadium import StadiumModel, Waypoint, PathEdge, EdgeKind, LevelName


def test_dynamic_routing_restricted_gate():
    """Verify that routing from G-S to L-S when G-S is restricted:
    1. Base route with no restrictions is shorter and direct.
    2. Dynamic routing adjusts to prefer an alternative route if one is cheaper than the penalized direct route.
    """
    # 1. Load default fixtures
    venue = fixtures.load_venue()
    levels = fixtures.load_levels()
    zones = fixtures.load_zones()
    gates = fixtures.load_gates()
    amenities = fixtures.load_amenities()
    waypoints = fixtures.load_waypoints()
    edges = fixtures.load_edges()
    parking = fixtures.load_parking()
    transit = fixtures.load_transit()

    # 2. Add custom waypoint and edges to create an alternative detour
    # We add a transit node WP-T-RAIL and connect it to WP-G-S and WP-G-E
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

    custom_model = StadiumModel(
        venue=venue,
        levels=levels,
        zones=zones,
        gates=gates,
        amenities=amenities,
        waypoints=waypoints,
        edges=edges,
        parking=parking,
        transit=transit
    )

    sim = StadiumSimulator(model=custom_model)
    ctx = ToolContext(simulator=sim, model=custom_model, knowledge=KnowledgeStore())

    # Under normal circumstances:
    # Route from WP-T-RAIL to WP-Z-L-S:
    # Path: WP-T-RAIL -> WP-G-S -> WP-C-L-S -> WP-Z-L-S
    # Distances: 100m + 60m + 30m = 190.0m
    args_normal = {"from_waypoint_id": "WP-T-RAIL", "to_waypoint_id": "WP-Z-L-S"}
    res_normal = find_route(args_normal, ctx)
    
    assert "error" not in res_normal, f"Normal routing failed: {res_normal}"
    assert res_normal["distance_m"] == 190.0
    assert res_normal["steps"] == ["WP-T-RAIL", "WP-G-S", "WP-C-L-S", "WP-Z-L-S"]

    # Now restrict Gate G-S
    sim._gates["G-S"].status = "restricted"
    
    # Under restricted gate G-S:
    # Path 1 (via G-S): WP-T-RAIL -> WP-G-S -> WP-C-L-S -> WP-Z-L-S
    # Edge WP-G-S -> WP-C-L-S gets +1500m penalty.
    # Total distance Path 1: 100 + (60 + 1500) + 30 = 1690.0m
    #
    # Path 2 (via G-E detour): WP-T-RAIL -> WP-G-E -> WP-C-L-E -> WP-C-L-S -> WP-Z-L-S
    # No gate penalty since G-E is open.
    # Total distance Path 2: 200 + 60 + 100 + 30 = 390.0m
    #
    # Since 390.0m < 1690.0m, Dijkstra must dynamically choose Path 2!
    res_restricted = find_route(args_normal, ctx)
    assert "error" not in res_restricted, f"Restricted routing failed: {res_restricted}"
    assert res_restricted["distance_m"] == 390.0
    assert res_restricted["steps"] == ["WP-T-RAIL", "WP-G-E", "WP-C-L-E", "WP-C-L-S", "WP-Z-L-S"]


def test_accessibility_elevator_preference():
    """Verify that routing under accessible_only=True prefers elevator routes over stair/escalator routes."""
    sim = StadiumSimulator()
    ctx = ToolContext(simulator=sim, model=sim.model, knowledge=KnowledgeStore())

    # Case 1: accessible_only=False (default)
    # Route from WP-C-L-S (Lower South) to WP-C-CL-S (Club South)
    # Available edges:
    # 1. Escalator (40m)
    # 2. Elevator (45m)
    # Normal routing should prefer the shorter escalator route (40.0m).
    args_normal = {"from_waypoint_id": "WP-C-L-S", "to_waypoint_id": "WP-C-CL-S", "accessible": False}
    res_normal = find_route(args_normal, ctx)
    assert "error" not in res_normal
    assert res_normal["distance_m"] == 40.0

    # Case 2: accessible_only=True (accessible=True)
    # Escalator gets +20000m penalty (cost = 20040.0m).
    # Elevator gets +0 penalty (cost = 45.0m).
    # Accessible routing should prefer elevator (45.0m).
    args_accessible = {"from_waypoint_id": "WP-C-L-S", "to_waypoint_id": "WP-C-CL-S", "accessible": True}
    res_accessible = find_route(args_accessible, ctx)
    assert "error" not in res_accessible
    assert res_accessible["distance_m"] == 45.0


if __name__ == "__main__":
    import sys
    print("Running wayfinding verification tests...")
    try:
        test_dynamic_routing_restricted_gate()
        print("test_dynamic_routing_restricted_gate passed!")
        test_accessibility_elevator_preference()
        print("test_accessibility_elevator_preference passed!")
        print("All wayfinding verification tests passed successfully!")
    except AssertionError as e:
        print(f"Test failure: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)
