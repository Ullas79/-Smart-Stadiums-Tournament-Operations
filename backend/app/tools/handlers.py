"""Tool handler implementations.

Each handler is a pure function `(args: dict, ctx: ToolContext) -> dict` that
operates on the simulator snapshot, the static stadium model, or the knowledge
store. Handlers are role-agnostic; the registry enforces role access before
calling them.
"""
from __future__ import annotations

from collections import defaultdict
from collections import OrderedDict
import heapq
from typing import Any

from ..knowledge.store import KnowledgeStore
from ..models.stadium import Gate, StadiumModel, Zone
from ..models.state import GateStatus, StadiumSnapshot
from ..simulator.engine import StadiumSimulator


class ToolContext:
    """Shared dependencies injected into every tool handler."""

    def __init__(self, simulator: StadiumSimulator, model: StadiumModel, knowledge: KnowledgeStore) -> None:
        """Initializes the ToolContext.

        Args:
            simulator: The stadium simulator instance.
            model: The static stadium venue model.
            knowledge: The knowledge store instance.
        """
        self.simulator = simulator
        self.model = model
        self.knowledge = knowledge

    def snapshot(self) -> StadiumSnapshot:
        """Retrieves the current simulator snapshot.

        Returns:
            The current StadiumSnapshot.
        """
        return self.simulator.snapshot()


# ---- handlers ---------------------------------------------------------------

def get_crowd_density(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Retrieves the live crowd density for a specific stadium zone.

    Args:
        args: Dictionary containing "zone_id" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing density metrics or error.
    """
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


def get_all_zones_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Retrieves live crowd density for all zones in the stadium.

    Args:
        args: Dictionary (unused).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary listing the match phase and metrics for all zones.
    """
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


def get_gate_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Retrieves the throughput, queue length, and status of entry gates.

    Args:
        args: Dictionary optionally containing "gate_id" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing status for one or all gates, or an error.
    """
    snap = ctx.snapshot()
    gate_id = args.get("gate_id")
    if gate_id:
        gs = snap.gate_by_id(gate_id)
        if gs is None:
            return {"error": f"Unknown gate_id '{gate_id}'.", "available_gate_ids": [g.gate_id for g in snap.gates]}
        return _gate_dict(gs)
    return {"gates": [_gate_dict(g) for g in snap.gates]}


def lookup_schedule(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Retrieves the match schedule and current match timing info.

    Args:
        args: Dictionary (unused).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing match phase and timing information.
    """
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


def find_route(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Finds an indoor walking route between two waypoint/zone/gate locations.

    Args:
        args: Dictionary containing "from_waypoint_id" (str), "to_waypoint_id" (str),
              and optionally "accessible" (bool).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing route steps and total distance, or an error.
    """
    from_id = args.get("from_waypoint_id", "")
    to_id = args.get("to_waypoint_id", "")
    accessible_only = bool(args.get("accessible", False) or args.get("accessible_only", False))
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


def report_incident(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Manually reports a new on-ground incident.

    Args:
        args: Dictionary containing "type" (str), "location" (str),
              "severity" (str), and optionally "description" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing details of the newly created incident.
    """
    type_ = args.get("type", "congestion")
    location = args.get("location", "")
    severity = args.get("severity", "low")
    description = args.get("description", "")
    inc = ctx.simulator.report_incident(type_, location, severity, description)
    return {"incident_id": inc.incident_id, "status": inc.status, "type": inc.type,
            "location": inc.location, "severity": inc.severity.value}


def get_incidents(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Lists all currently active incidents.

    Args:
        args: Dictionary (unused).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing a list of active incidents.
    """
    snap = ctx.snapshot()
    return {"incidents": [i.model_dump() for i in snap.incidents]}


def recommend_action(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Deterministic decision-support heuristic for organizers.

    Args:
        args: Dictionary (unused).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary detailing operational alerts and recommended steps.
    """
    snap = ctx.snapshot()
    recommendations: list[str] = []
    high_zones = [c for c in snap.crowd if c.density >= 0.85]
    restricted_gates = [g for g in snap.gates if g.status == "restricted"]

    if high_zones:
        names = []
        for c in high_zones:
            zone = ctx.model.zone_by_id(c.zone_id)
            if zone:
                names.append(zone.name)
        recommendations.append(
            f"High crowd density at {', '.join(names)} (>85% capacity). Operational mitigation plan:\n"
            f"Step 1: Open secondary turnstiles and gates to maximize outflow/entry capacity.\n"
            f"Step 2: Deploy volunteers and facility staff to redirect incoming flow to lower-density adjacent zones.\n"
            f"Step 3: Update mobile app routing navigation and public signage displays to route fans away from {', '.join(names)}."
        )
    if restricted_gates:
        rg = [g.label for g in restricted_gates]
        recommendations.append(
            f"Gate bottleneck detected at: {', '.join(rg)}. Operational mitigation plan:\n"
            f"Step 1: Transition adjacent gates to open status to share queue burden.\n"
            f"Step 2: Direct volunteers to walk along queue lines to verify tickets/security checks beforehand, accelerating throughput.\n"
            f"Step 3: Broadcast a dynamic push notification advising fans to utilize alternative entry gates."
        )
    
    # Check all incidents (both manual and scenario incidents)
    active_incidents = [i for i in snap.incidents if i.status == "active"]
    if active_incidents:
        for i in active_incidents:
            recommendations.append(
                f"Active incident at {i.location} ({i.type}, severity: {i.severity.value}). Operational mitigation plan:\n"
                f"Step 1: Dispatch medical/safety personnel directly to {i.location}.\n"
                f"Step 2: Instruct nearest volunteers to cordon off the area and maintain clear access paths for emergency responders.\n"
                f"Step 3: Report status back to command center and update incident logs."
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
        "active_incidents": len(active_incidents),
        "recommendations": recommendations,
    }


def translate_response(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Marks text to be translated into the fan's preferred language.

    Args:
        args: Dictionary containing "text" (str) and "target_language" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary with translation instructions.
    """
    text = args.get("text", "")
    target = args.get("target_language", "en")
    return {
        "text": text,
        "target_language": target,
        "instruction": f"Translate the following into {target} and reply to the user in {target}.",
    }


def search_knowledge(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Searches the knowledge store for relevant policies, FAQs, or amenities.

    Args:
        args: Dictionary containing "query" (str) and optionally "k" (int).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary containing query and list of relevant document results.
    """
    query = args.get("query", "")
    k = int(args.get("k", 3))
    results = ctx.knowledge.search_sync(query, k)
    return {"query": query, "results": [{"id": d["id"], "title": d["title"], "text": d["text"]} for d in results]}


# ---- helpers ----------------------------------------------------------------

def _gate_dict(gs: GateStatus) -> dict[str, Any]:
    """Converts a GateStatus model into a dictionary.

    Args:
        gs: The GateStatus model.

    Returns:
        A dictionary representation of the gate status.
    """
    return {
        "gate_id": gs.gate_id,
        "label": gs.label,
        "status": gs.status,
        "throughput_per_min": gs.throughput_per_min,
        "queue_minutes": round(gs.queue_minutes, 1),
    }


def _next_event(sim_time: float, kickoff: float, halftime: float, full_time: float) -> str:
    """Calculates the time left until the next match phase event.

    Args:
        sim_time: The current simulator time in seconds.
        kickoff: Kickoff time in seconds.
        halftime: Halftime start time in seconds.
        full_time: Full time start time in seconds.

    Returns:
        A string describing the next event and time remaining.
    """
    if sim_time < kickoff:
        return f"Kickoff in {int((kickoff - sim_time) / 60)} min."
    if sim_time < halftime:
        return f"Halftime in {int((halftime - sim_time) / 60)} min."
    if sim_time < full_time:
        return f"Full time in {int((full_time - sim_time) / 60)} min."
    return "Match concluded; managing exit flow."


def _resolve_waypoint(token: str, ctx: ToolContext) -> str:
    """Resolves short-hand tokens (zones, gates) to full waypoint IDs.

    Args:
        token: The token to resolve.
        ctx: The ToolContext dependency container.

    Returns:
        The resolved waypoint ID.
    """
    if not token:
        return token
    token_upper = token.upper()
    if token_upper.startswith("WP-"):
        return token_upper
    # zone id -> seats waypoint
    zone = ctx.model.zone_by_id(token_upper)
    if zone:
        return f"WP-Z-{zone.zone_id}"
    gate = ctx.model.gate_by_id(token_upper)
    if gate:
        return f"WP-{gate.gate_id}"
    # concourse shorthand e.g. C-L-N -> WP-C-L-N
    if token_upper.startswith("C-"):
        return f"WP-{token_upper}"
    return token_upper


def _waypoint_to_zone_id(waypoint_id: str, model: StadiumModel) -> str | None:
    """Maps a waypoint ID to a zone ID if possible, using model zones, concourses, and gates.

    Args:
        waypoint_id: The waypoint ID to resolve.
        model: The static stadium venue model.

    Returns:
        The zone ID if mapped, otherwise None.
    """
    if not waypoint_id:
        return None
    # 1. Direct seats mapping
    if waypoint_id.startswith("WP-Z-"):
        zone_id = waypoint_id[5:]
        if any(z.zone_id == zone_id for z in model.zones):
            return zone_id

    # 2. Concourse mapping (WP-C-...)
    if waypoint_id.startswith("WP-"):
        potential_conc = waypoint_id[3:]
        # Find zone with this concourse_id
        for zone in model.zones:
            if zone.concourse_id == potential_conc:
                return zone.zone_id

    # 3. Gate mapping (WP-G-...)
    if waypoint_id.startswith("WP-"):
        potential_gate = waypoint_id[3:]
        # Find zone with this nearest_gate_id
        for zone in model.zones:
            if zone.nearest_gate_id == potential_gate:
                return zone.zone_id

    return None


def _build_graph(ctx: ToolContext, accessible_only: bool, snap: StadiumSnapshot) -> dict[str, list[tuple[str, float]]]:
    """Adjacency list representation of the stadium waypoint graph with dynamic weights.

    Args:
        ctx: The ToolContext dependency container.
        accessible_only: If True, penalizes non-accessible edges instead of filtering.
        snap: The StadiumSnapshot of the stadium state.

    Returns:
        A dictionary mapping waypoint IDs to lists of (neighbor_id, distance) tuples.
    """
    g: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for e in ctx.model.edges:
        cost = e.distance_m

        # Accessibility penalties
        if accessible_only and not e.accessible:
            if e.kind == "stairs":
                cost += 10000.0
            elif e.kind == "escalator":
                cost += 20000.0

        # Telemetry penalties
        penalty = 0.0

        # Zone density penalty
        from_zone = _waypoint_to_zone_id(e.from_id, ctx.model)
        to_zone = _waypoint_to_zone_id(e.to_id, ctx.model)
        for zid in {from_zone, to_zone}:
            if zid:
                cd = snap.crowd_by_zone(zid)
                if cd:
                    if cd.density >= 0.85:
                        penalty += 1500.0
                    elif cd.density >= 0.50:
                        penalty += 300.0

        # Gate status penalty
        for gate in ctx.model.gates:
            gate_wp = f"WP-{gate.gate_id}"
            if e.from_id == gate_wp or e.to_id == gate_wp or e.from_id == gate.gate_id or e.to_id == gate.gate_id:
                gs = snap.gate_by_id(gate.gate_id)
                if gs:
                    if gs.status == "restricted":
                        penalty += 1500.0
                    elif gs.status == "closed":
                        penalty += 99999.0

        # Active incident severity penalty
        for incident in snap.incidents:
            if incident.status == "active":
                affected = False
                if incident.location in (e.from_id, e.to_id):
                    affected = True
                elif incident.zone_id and incident.zone_id in (from_zone, to_zone):
                    affected = True
                elif incident.location and incident.location in (from_zone, to_zone):
                    affected = True
                elif incident.zone_id and (incident.zone_id in (e.from_id, e.to_id) or f"WP-{incident.zone_id}" in (e.from_id, e.to_id)):
                    affected = True

                if affected:
                    if incident.severity == "low":
                        penalty += 500.0
                    elif incident.severity == "medium":
                        penalty += 1500.0
                    elif incident.severity == "high":
                        penalty += 5000.0

        cost += penalty
        g[e.from_id].append((e.to_id, cost))

    return g


_ROUTE_CACHE: OrderedDict[Any, tuple[list[str] | None, float]] = OrderedDict()


def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
    """Computes the shortest path between two waypoints using Dijkstra's algorithm.

    Args:
        ctx: The ToolContext dependency container.
        src: The source waypoint ID.
        dst: The destination waypoint ID.
        accessible_only: If True, only uses wheelchair-accessible paths.

    Returns:
        A tuple of (path_list, distance) where path_list is a list of waypoint IDs or None.
    """
    snap = ctx.snapshot()
    model_id = id(ctx.model)
    gate_sig = tuple((g.gate_id, g.status) for g in snap.gates)
    crowd_sig = tuple((c.zone_id, round(c.density, 2)) for c in snap.crowd)
    inc_sig = tuple((i.incident_id, i.location, i.zone_id, i.severity.value if hasattr(i.severity, "value") else str(i.severity), i.status) for i in snap.incidents if i.status == "active")
    cache_key = (model_id, src, dst, accessible_only, gate_sig, crowd_sig, inc_sig)
    if cache_key in _ROUTE_CACHE:
        _ROUTE_CACHE.move_to_end(cache_key)
        path, dist = _ROUTE_CACHE[cache_key]
        # Return a copy of the path list to prevent callers from mutating the cached list
        return list(path) if path is not None else None, dist

    g = _build_graph(ctx, accessible_only, snap)
    heap: list[tuple[float, str, list[str]]] = [(0.0, src, [src])]
    seen: set[str] = set()

    path_found, dist_found = None, 0.0
    while heap:
        dist, node, path = heapq.heappop(heap)
        if node == dst:
            path_found, dist_found = path, dist
            break
        if node in seen:
            continue
        seen.add(node)
        for nbr, w in g.get(node, []):
            if nbr not in seen:
                heapq.heappush(heap, (dist + w, nbr, path + [nbr]))

    if len(_ROUTE_CACHE) >= 2048:
        _ROUTE_CACHE.popitem(last=False)
    _ROUTE_CACHE[cache_key] = (path_found, dist_found)
    return list(path_found) if path_found is not None else None, dist_found


def set_gate_status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Updates the status of a stadium entry/exit gate.

    Args:
        args: Dictionary containing "gate_id" (str) and "status" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary representation of the updated GateStatus, or an error.
    """
    gate_id = args.get("gate_id")
    status = args.get("status")
    if not gate_id or not status:
        return {"error": "Both 'gate_id' and 'status' are required parameters."}
    try:
        updated = ctx.simulator.set_gate_status(gate_id, status)
        return _gate_dict(updated)
    except KeyError:
        return {"error": f"Gate '{gate_id}' not found.", "available_gate_ids": ctx.simulator.get_gate_ids()}
    except ValueError as e:
        return {"error": str(e)}


def dispatch_staff(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Records that a staff member or volunteer is dispatched to an incident.

    Args:
        args: Dictionary containing "incident_id" (str) and "assigned_staff" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary representation of the updated Incident, or an error.
    """
    incident_id = args.get("incident_id")
    assigned_staff = args.get("assigned_staff")
    if not incident_id or not assigned_staff:
        return {"error": "Both 'incident_id' and 'assigned_staff' are required parameters."}
    try:
        updated = ctx.simulator.dispatch_incident(incident_id, assigned_staff)
        return updated.model_dump()
    except KeyError:
        return {"error": f"Incident '{incident_id}' not found."}
    except ValueError as e:
        return {"error": str(e)}


def mitigate_bottleneck(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Mitigates crowd bottlenecks in a zone by reducing occupancy/density.

    Args:
        args: Dictionary containing "zone_id" (str) and optionally "strategy" (str).
        ctx: The ToolContext dependency container.

    Returns:
        A dictionary detailing the mitigation action.
    """
    zone_id = args.get("zone_id")
    strategy = args.get("strategy")
    if not zone_id:
        return {"error": "Parameter 'zone_id' is required."}
    try:
        return ctx.simulator.mitigate_bottleneck(zone_id, strategy)
    except KeyError:
        return {"error": f"Zone '{zone_id}' not found.", "available_zone_ids": ctx.simulator.get_zone_ids()}

