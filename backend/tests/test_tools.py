"""Tool registry + handler tests (no Gemini calls)."""
from __future__ import annotations

import pytest

from app.knowledge.store import KnowledgeStore
from app.models.roles import Role
from app.simulator.engine import StadiumSimulator
from app.simulator import fixtures
from app.tools.handlers import ToolContext
from app.tools.registry import ToolRegistry


@pytest.fixture()
def ctx():
    sim = StadiumSimulator()
    model = fixtures.load_stadium_model()
    knowledge = KnowledgeStore()
    return ToolContext(simulator=sim, model=model, knowledge=knowledge), sim


@pytest.fixture()
def registry():
    return ToolRegistry()


# ---- role guards --------------------------------------------------------

def test_fan_cannot_report_incident(registry, ctx):
    c, _ = ctx
    res = registry.execute("report_incident", {"type": "medical", "location": "x", "severity": "high"}, Role.FAN, c)
    assert "not authorized" in res["error"]


def test_volunteer_cannot_recommend_action(registry, ctx):
    c, _ = ctx
    res = registry.execute("recommend_action", {}, Role.VOLUNTEER, c)
    assert "not authorized" in res["error"]


def test_organizer_can_recommend_action(registry, ctx):
    c, _ = ctx
    res = registry.execute("recommend_action", {}, Role.ORGANIZER, c)
    assert "recommendations" in res


def test_unknown_tool_returns_error(registry, ctx):
    c, _ = ctx
    res = registry.execute("does_not_exist", {}, Role.ORGANIZER, c)
    assert "error" in res


def test_declarations_for_role_subset(registry):
    fan_decls = registry.declarations_for_role(Role.FAN)
    org_decls = registry.declarations_for_role(Role.ORGANIZER)
    fan_names = {d.name for d in fan_decls}
    org_names = {d.name for d in org_decls}
    assert "recommend_action" not in fan_names
    assert "recommend_action" in org_names
    assert "report_incident" not in fan_names
    assert "report_incident" in org_names


# ---- handlers -----------------------------------------------------------

def test_get_crowd_density_unknown_zone(registry, ctx):
    c, _ = ctx
    res = registry.execute("get_crowd_density", {"zone_id": "ZZZ"}, Role.FAN, c)
    assert "error" in res and "available_zone_ids" in res


def test_get_all_zones_status_returns_all(registry, ctx):
    c, _ = ctx
    res = registry.execute("get_all_zones_status", {}, Role.FAN, c)
    assert len(res["zones"]) == 12
    assert "phase" in res


def test_get_gate_status_single_and_all(registry, ctx):
    c, _ = ctx
    allg = registry.execute("get_gate_status", {}, Role.FAN, c)
    assert len(allg["gates"]) == 4
    one = registry.execute("get_gate_status", {"gate_id": "G-N"}, Role.FAN, c)
    assert one["gate_id"] == "G-N"


def test_lookup_schedule(registry, ctx):
    c, _ = ctx
    res = registry.execute("lookup_schedule", {}, Role.FAN, c)
    assert res["name"] == "FIFA World Cup 2026 Final"
    assert "next_event" in res


def test_find_route_gate_to_zone(registry, ctx):
    c, _ = ctx
    res = registry.execute(
        "find_route", {"from_waypoint_id": "G-N", "to_waypoint_id": "L-N"}, Role.FAN, c
    )
    assert "steps" in res
    assert res["from"].startswith("WP-")
    assert res["step_count"] >= 2


def test_find_route_accessible_only(registry, ctx):
    c, _ = ctx
    # upper-concourse route requires a vertical connector; accessible path uses elevator
    res = registry.execute(
        "find_route", {"from_waypoint_id": "G-N", "to_waypoint_id": "C-U-N", "accessible": True}, Role.FAN, c
    )
    assert "steps" in res
    assert res["accessible"] is True
    assert res["step_count"] >= 3


def test_report_incident_organizer(registry, ctx):
    c, _ = ctx
    res = registry.execute(
        "report_incident", {"type": "medical", "location": "Lower North", "severity": "high"}, Role.ORGANIZER, c
    )
    assert res["status"] == "active"
    assert res["severity"] == "high"


def test_get_incidents(registry, ctx):
    c, _ = ctx
    registry.execute(
        "report_incident", {"type": "congestion", "location": "x", "severity": "low"}, Role.VOLUNTEER, c
    )
    res = registry.execute("get_incidents", {}, Role.VOLUNTEER, c)
    assert len(res["incidents"]) >= 1


def test_recommend_action_includes_recommendations(registry, ctx):
    c, sim = ctx
    # force a high-density state
    sim.sim_time = fixtures.KICKOFF_AT
    for _ in range(30):
        sim.step(60)
    res = registry.execute("recommend_action", {}, Role.ORGANIZER, c)
    assert isinstance(res["recommendations"], list)
    assert len(res["recommendations"]) >= 1


def test_translate_response(registry, ctx):
    c, _ = ctx
    res = registry.execute("translate_response", {"text": "hello", "target_language": "Spanish"}, Role.FAN, c)
    assert res["target_language"] == "Spanish"
    assert "instruction" in res


def test_search_knowledge_returns_relevant(registry, ctx):
    c, _ = ctx
    res = registry.execute("search_knowledge", {"query": "bag policy"}, Role.FAN, c)
    assert res["results"]
    assert any("bag" in r["text"].lower() for r in res["results"])


def test_tool_error_surfaces_structured(registry, ctx):
    c, _ = ctx
    # missing required arg -> handler should still return a dict (no raise escapes)
    res = registry.execute("get_crowd_density", {}, Role.FAN, c)
    assert "error" in res
