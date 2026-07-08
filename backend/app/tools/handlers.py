"""Tool handler implementations.

Each handler is a pure function `(args: dict, ctx: ToolContext) -> dict` that
operates on the simulator snapshot, the static stadium model, or the knowledge
store. Handlers are role-agnostic; the registry enforces role access before
calling them.
"""
from __future__ import annotations

import heapq
from collections import defaultdict

from ..knowledge.store import KnowledgeStore
from ..models.stadium import StadiumModel
from ..models.state import StadiumSnapshot
from ..simulator.engine import StadiumSimulator


class ToolContext:
    """Shared dependencies injected into every tool handler."""

    def __init__(self, simulator: StadiumSimulator, model: StadiumModel, knowledge: KnowledgeStore) -> None:
        self.simulator = simulator
        self.model = model
        self.knowledge = knowledge

    def snapshot(self) -> StadiumSnapshot:
        return self.simulator.snapshot()


# ---- handlers ---------------------------------------------------------------

def get_crowd_density(args: dict, ctx: ToolContext) -> dict:
    zone_id = args.get("zone_id", "")
    snap = ctx.snapshot()
    cd = snap.crowd_by_zone(zone_id)
    if cd is None:
        available = [c.zone_id for c in snap.crowd]
        return {"error": f"Unknown zone_id '{zone_id}'.", "available_zone_ids": available}
    zone = ctx.model.zone_by_id(zone_id)
    return {
        "zone_id": cd.zone_id,
        "zone_name": zone.name if zone else zone_id,
        "level": zone.level.value if zone else "",
        "occupancy": cd.occupancy,
        "capacity": cd.capacity,
        "density": round(cd.density, 3),
        "level_label": cd.level(),
    }


def get_all_zones_status(args: dict, ctx: ToolContext) -> dict:
    snap = ctx.snapshot()
    zones = []
    for cd in snap.crowd:
        zone = ctx.model.zone_by_id(cd.zone_id)
        zones.append({
            "zone_id": cd.zone_id,
            "zone_name": zone.name if zone else cd.zone_id,
            "level": zone.level.value if zone else "",
            "occupancy": cd.occupancy,
            "capacity": cd.capacity,
            "density": round(cd.density, 3),
            "level_label": cd.level(),
        })
    return {"phase": snap.match.phase.value, "zones": zones}


def get_gate_status(args: dict, ctx: ToolContext) -> dict:
    snap = ctx.snapshot()
    gate_id = args.get("gate_id")
    if gate_id:
        gs = next((g for g in snap.gates if g.gate_id == gate_id), None)
        if gs is None:
            return {"error": f"Unknown gate_id '{gate_id}'.", "available_gate_ids": [g.gate_id for g in snap.gates]}
        return _gate_dict(gs)
    return {"gates": [_gate_dict(g) for g in snap.gates]}


def lookup_schedule(args: dict, ctx: ToolContext) -> dict:
    snap = ctx.snapshot()
    m = snap.match
    return {
        "match_id": m.match_id,
        "name": m.name,
        "venue": snap.venue_name,
        "phase": m.phase.value,
        "kickoff_at": m.kickoff_at,
        "halftime_at": m.halftime_at,
        "full_time_at": m.full_time_at,
        "sim_time": m.sim_time,
        "next_event": _next_event(m.sim_time, m.kickoff_at, m.halftime_at, m.full_time_at),
    }


def find_route(args: dict, ctx: ToolContext) -> dict:
    from_id = args.get("from_waypoint_id", "")
    to_id = args.get("to_waypoint_id", "")
    accessible_only = bool(args.get("accessible", False))
    # resolve zone/concourse shorthand to waypoint ids
    from_id = _resolve_waypoint(from_id, ctx)
    to_id = _resolve_waypoint(to_id, ctx)
    if from_id not in {w.waypoint_id for w in ctx.model.waypoints}:
        return {"error": f"Unknown from '{from_id}'.", "waypoint_ids": [w.waypoint_id for w in ctx.model.waypoints]}
    if to_id not in {w.waypoint_id for w in ctx.model.waypoints}:
        return {"error": f"Unknown to '{to_id}'.", "waypoint_ids": [w.waypoint_id for w in ctx.model.waypoints]}
    path, dist = _shortest_path(ctx, from_id, to_id, accessible_only)
    if path is None:
        return {"error": "No route found between the given waypoints.", "accessible_only": accessible_only}
    return {
        "from": from_id,
        "to": to_id,
        "accessible": accessible_only,
        "distance_m": round(dist, 1),
        "steps": path,
        "step_count": len(path),
    }


def report_incident(args: dict, ctx: ToolContext) -> dict:
    type_ = args.get("type", "congestion")
    location = args.get("location", "")
    severity = args.get("severity", "low")
    description = args.get("description", "")
    inc = ctx.simulator.report_incident(type_, location, severity, description)
    return {"incident_id": inc.incident_id, "status": inc.status, "type": inc.type,
            "location": inc.location, "severity": inc.severity.value}


def get_incidents(args: dict, ctx: ToolContext) -> dict:
    snap = ctx.snapshot()
    return {"incidents": [i.model_dump() for i in snap.incidents]}


def recommend_action(args: dict, ctx: ToolContext) -> dict:
    """Deterministic decision-support heuristic for organizers."""
    snap = ctx.snapshot()
    recommendations: list[str] = []
    high_zones = [c for c in snap.crowd if c.level() == "high"]
    restricted_gates = [g for g in snap.gates if g.status == "restricted"]

    if high_zones:
        names = [ctx.model.zone_by_id(c.zone_id).name for c in high_zones if ctx.model.zone_by_id(c.zone_id)]
        recommendations.append(
            f"High crowd density at {', '.join(names)}. Open secondary gates and reroute arriving fans "
            f"away from these zones; deploy volunteers to manage flow."
        )
    if restricted_gates:
        rg = [g.label for g in restricted_gates]
        recommendations.append(
            f"Restricted gates due to queueing: {', '.join(rg)}. Broadcast rerouting to the nearest open "
            f"gate and consider staffing additional entry lanes."
        )
    high_severity = [i for i in snap.incidents if i.severity.value == "high"]
    if high_severity:
        for i in high_severity:
            recommendations.append(
                f"High-severity incident at {i.location} ({i.type}): dispatch first aid and clear "
                f"the immediate area. Notify control room."
            )
    if snap.match.phase.value == "halftime":
        recommendations.append(
            "Halftime concourse spike: encourage fans to use upper-level amenities and water stations; "
            "stage concessions staff on main concourses."
        )
    if not recommendations:
        recommendations.append("Operations are nominal. No immediate action required; maintain monitoring.")

    return {
        "phase": snap.match.phase.value,
        "high_density_zones": [c.zone_id for c in high_zones],
        "restricted_gates": [g.gate_id for g in restricted_gates],
        "active_incidents": len(snap.incidents),
        "recommendations": recommendations,
    }


def translate_response(args: dict, ctx: ToolContext) -> dict:
    """Marks text for translation into the target language. The model performs
    the actual translation in its final answer (Gemini is natively multilingual)."""
    text = args.get("text", "")
    target = args.get("target_language", "en")
    return {
        "text": text,
        "target_language": target,
        "instruction": f"Translate the following into {target} and reply to the user in {target}.",
    }


def search_knowledge(args: dict, ctx: ToolContext) -> dict:
    query = args.get("query", "")
    k = int(args.get("k", 3))
    results = ctx.knowledge.search_sync(query, k)
    return {"query": query, "results": [{"id": d["id"], "title": d["title"], "text": d["text"]} for d in results]}


# ---- helpers ----------------------------------------------------------------

def _gate_dict(gs) -> dict:
    return {
        "gate_id": gs.gate_id,
        "label": gs.label,
        "status": gs.status,
        "throughput_per_min": gs.throughput_per_min,
        "queue_minutes": round(gs.queue_minutes, 1),
    }


def _next_event(sim_time: float, kickoff: float, halftime: float, full_time: float) -> str:
    if sim_time < kickoff:
        return f"Kickoff in {int((kickoff - sim_time) / 60)} min."
    if sim_time < halftime:
        return f"Halftime in {int((halftime - sim_time) / 60)} min."
    if sim_time < full_time:
        return f"Full time in {int((full_time - sim_time) / 60)} min."
    return "Match concluded; managing exit flow."


def _resolve_waypoint(token: str, ctx: ToolContext) -> str:
    """Allow callers to pass a zone_id (e.g. 'L-N'), gate_id, or full waypoint id."""
    if not token:
        return token
    if token.startswith("WP-"):
        return token
    # zone id -> seats waypoint
    zone = ctx.model.zone_by_id(token)
    if zone:
        return f"WP-Z-{token}"
    gate = ctx.model.gate_by_id(token)
    if gate:
        return f"WP-{token}"
    # concourse shorthand e.g. C-L-N -> WP-C-L-N
    if token.startswith("C-"):
        return f"WP-{token}"
    return token


def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:
    g: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for e in ctx.model.edges:
        if accessible_only and not e.accessible:
            continue
        g[e.from_id].append((e.to_id, e.distance_m))
    return g


def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool):
    g = _build_graph(ctx, accessible_only)
    heap: list[tuple[float, str, list[str]]] = [(0.0, src, [src])]
    seen: set[str] = set()
    while heap:
        dist, node, path = heapq.heappop(heap)
        if node == dst:
            return path, dist
        if node in seen:
            continue
        seen.add(node)
        for nbr, w in g.get(node, []):
            if nbr not in seen:
                heapq.heappush(heap, (dist + w, nbr, path + [nbr]))
    return None, 0.0
