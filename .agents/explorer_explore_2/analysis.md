# Backend Routing, Pathfinding, and Volunteer Dispatch Analysis Report

## Executive Summary
This report analyzes the backend routing, pathfinding, and volunteer dispatch logic of the Smart Stadiums Tournament Operations system. The investigation covers the Dijkstra pathfinding implementation, routing cache behavior, volunteer dispatch mechanism, potential concurrency hazards under high crowd density/scenarios, and the propagation of route penalties when dynamic incidents are injected.

Key findings include:
1. **Routing Cache Bypass**: The route cache is effectively invalidated on every simulation second because `sim_time` is cast to an integer and included in the cache key.
2. **Missing Concurrency Protection**: The simulator has a background asyncio tick loop running in the main event loop thread while API endpoints run concurrently in the thread pool. Because there is no synchronization (locks/mutexes) protecting the shared state (`self._incidents`, `self._crowd`, `self._gates`), the system is highly vulnerable to race conditions, lost updates, and `RuntimeError` due to concurrent list mutations.
3. **Gate Incident Penalty Mismatch (Bug)**: The `gate_malfunction` scenario incident uses a non-existent zone ID (`G-S`). Consequently, the `5000.0` high-severity routing penalty is never propagated to edges around the South Gate; only the `1500.0` gate status penalty applies.
4. **Metadata-only Volunteer Dispatch**: Volunteer dispatch is a simple metadata assignment on the `Incident` object; there is no real-time GPS or waypoint-based volunteer tracking.

---

## 1. Dijkstra Pathfinding and Caching Mechanisms

### 1.1 Pathfinding Logic
The pathfinding logic is initiated via the `find_route` tool handler in `backend/app/tools/handlers.py` (lines 145-176) and executed via `_shortest_path` (lines 495-539). The algorithm runs a standard Dijkstra search over a dynamically weighted waypoint graph.

The graph is constructed on-demand on every cache miss using `_build_graph` (lines 418-489):
```python
def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:
    g: dict[str, list[tuple[str, float]]] = defaultdict(list)
    snap = ctx.snapshot()

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
```

### 1.2 Caching Mechanism
The routing cache is declared at the module level in `backend/app/tools/handlers.py` as:
```python
_ROUTE_CACHE: dict[Any, tuple[list[str] | None, float]] = {}
```
Inside `_shortest_path`, the cache key is constructed using:
- `model_id` (memory ID of `ctx.model`)
- `src` (source waypoint ID)
- `dst` (destination waypoint ID)
- `accessible_only` (accessibility filter toggle)
- `sim_time` (simulation clock time cast to `int`)
- `gate_sig` (tuple of gate IDs and their current statuses)
- `crowd_sig` (tuple of zone IDs and their densities rounded to 2 decimal places)
- `inc_sig` (tuple of active incident attributes: ID, location, zone ID, severity, status)

#### Cache Eviction Strategy
When the cache size reaches or exceeds `2048` entries, the entire cache is cleared:
```python
if len(_ROUTE_CACHE) >= 2048:
    _ROUTE_CACHE.clear()
```

#### Cache Limitations & Shortcomings
- **High Invalidation Frequency**: Because `sim_time` is cast to `int` and included in the `cache_key`, the cache is completely bypassed on every simulation second (provided `sim_time` advances by $\ge 1.0$ unit per tick). This makes the cache ineffective across seconds.
- **Defensive Copying**: The cache returns a copy of the path list (`list(path_found)`) on lookup. This is a positive design decision as it prevents callers from mutating the cached list in place.

---

## 2. Volunteer Dispatch and Tracking Logic

### 2.1 Dispatch Logic
The dispatch process consists of three layers:
1. **API Router**: The endpoint `POST /api/incidents/dispatch` (in `backend/app/api/routes.py`, lines 127-145) receives a `DispatchRequest` body containing `incident_id`, `volunteer_id`, and `assigned_staff`. It resolves the dispatcher name via `staff = req.assigned_staff or req.volunteer_id` and invokes the simulator.
2. **Simulator Engine**: `dispatch_incident` (in `backend/app/simulator/engine.py`, lines 454-477) updates the matching active incident:
   ```python
   def dispatch_incident(self, incident_id: str, assigned_staff: str) -> Incident:
       for i in self._incidents:
           if i.incident_id == incident_id:
               if i.status == "resolved":
                   raise ValueError("Incident is already resolved")
               i.assigned_staff = assigned_staff
               i.description = f"{i.description} [Dispatched: {assigned_staff}]"
               self._snapshot_cache = None
               return i
       raise KeyError(f"Incident {incident_id} not found")
   ```
3. **Agent Tool Handler**: The `dispatch_staff` function (in `backend/app/tools/handlers.py`, lines 565-587) wraps the simulator call for agent use and enforces Role-Based Access Control (RBAC). Only the `STAFF` role is authorized to call `dispatch_staff`.

### 2.2 Tracking Logic Details
- **No Geographical Tracking**: There is no GPS telemetry, grid location tracking, or waypoint position tracking for volunteers.
- **State Preservation**: Volunteers are only "tracked" as a metadata string (`assigned_staff` field) on the `Incident` object itself.
- **In-Place Modification**: Dispatching appends `[Dispatched: {assigned_staff}]` to the incident's description and clears `self._snapshot_cache`. It does not transition volunteers between status queues (e.g. "idle" vs "busy").

---

## 3. Concurrency, Race Conditions, and Deadlocks Assessment

The current architecture lacks synchronization mechanisms, exposing the system to multiple race conditions under high concurrent workloads:

### 3.1 FastAPI Threading vs. Asyncio Tick Loop
FastAPI routes that are declared with standard `def` instead of `async def` (e.g., `trigger_scenario_route`, `dispatch_incident_route`, `chat`, etc.) are run in a threadpool (via AnyIO) to avoid blocking the main event loop. The simulator's tick task `_run` runs on the main asyncio event loop.
Consequently, multiple threads are executing API requests that read/write the simulator's state concurrently with the simulator background thread mutating the state in `self.step()`.

### 3.2 Key Concurrency Hazards

#### A. Concurrent Mutation and List Comprehension Overwrite on `self._incidents`
Python list comprehensions are not thread-safe. Multiple threads performing list comprehensions concurrently on `self._incidents` can overwrite each other's updates:
1. **Background Tick**: `_update_incidents` executes:
   `self._incidents = [i for i in self._incidents if i.status == "active" or ...]`
2. **Scenario Injector Thread**: `trigger_scenario` executes:
   `self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]`
3. **Race Condition**: If both run concurrently, one will overwrite `self._incidents` with its resulting list, erasing the updates of the other. For instance, a newly injected scenario incident or a resolved incident record could be completely lost.

#### B. Iterator Mutated During Iteration (`RuntimeError`)
In `snapshot()` (lines 572-589):
```python
incidents=[i.model_copy() for i in self._incidents if i.status == "active"]
```
If `snapshot()` iterates over `self._incidents` to build the list copy while another thread is executing `trigger_scenario` or `_update_incidents` (which appends to or filters the list), Python can raise a `RuntimeError: list iterator mutated during iteration`. This would cause `/state` or `/chat` API requests to fail with a 500 error.

#### C. Overwritten Crowd Density Mitigations
In `mitigate_bottleneck` (lines 539-570), the crowd density is updated via:
```python
cd.occupancy = int(cd.occupancy * 0.75)
cd.density = cd.occupancy / cd.capacity
```
Concurrently, the background tick loop runs `_update_crowd` (lines 175-200), which mutates `cd.occupancy` towards the phase target. Without synchronization, these concurrent writes can lead to race conditions where the mitigation is either immediately overwritten by the tick loop or vice-versa, neutralizing the mitigation effect.

### 3.3 Deadlocks
Because there are **no locks** (no `threading.Lock`, no `asyncio.Lock`) used in the simulator or tool handlers, classic deadlock scenarios (mutual exclusion wait locks) are impossible.
However, "soft deadlocks" due to CPU starvation could occur if multiple concurrent wayfinding requests are received under high crowd density, causing the thread pool to saturate due to heavy Dijkstra path calculations on a dynamically calculated graph.

---

## 4. Route Penalty Propagation and Scenario Mismatch (Bug)

### 4.1 Propagation Flow
1. An incident is reported or triggered (active status).
2. The snapshot cache is cleared, and subsequent pathfinding queries compute a new `inc_sig` for the routing cache key, forcing a cache bypass.
3. `_build_graph` iterates over every edge `e` in the stadium model and checks if the active incident affects it based on:
   - Endpoint match: `incident.location in (e.from_id, e.to_id)`
   - Zone match 1: `incident.zone_id and incident.zone_id in (from_zone, to_zone)`
   - Zone match 2: `incident.location and incident.location in (from_zone, to_zone)`
4. If affected, an incident penalty is added to the edge weight:
   - `low` severity: `+500.0`
   - `medium` severity: `+1500.0`
   - `high` severity: `+5000.0`
5. Dijkstra's algorithm computes the shortest path on the dynamically penalized graph, routing traffic away from these high-cost edges.

### 4.2 Gate Malfunction Penalty Mismatch (Bug)
In `backend/app/simulator/engine.py` (lines 401-410), the `gate_malfunction` scenario is injected with:
- `zone_id = "G-S"`
- `location = "Gate 2 (South Gate)"`

However, `"G-S"` is not a valid seating zone ID (the stadium zones are `"L-S"`, `"C-S"`, and `"U-S"`).
When `_waypoint_to_zone_id` resolves waypoint `"WP-G-S"` (South Gate Plaza), it maps it to nearest seating zone `"L-S"`.
In `_build_graph`'s propagation check:
- `incident.zone_id` is `"G-S"`.
- `from_zone` and `to_zone` for the South Gate edge resolve to `"L-S"`.
- `incident.zone_id in (from_zone, to_zone)` evaluates to `"G-S" in ("L-S", "L-S")` $\rightarrow$ `False`.
- `incident.location` (`"Gate 2 (South Gate)"`) does not match the zone `"L-S"`, nor the waypoint `"WP-G-S"`.

Because of this mismatch, **the high-severity incident penalty (+5000.0) is never applied to the South Gate edges**.
The only penalty that applies to the South Gate edges is the gate status penalty of `1500.0` (applied because `self._gates["G-S"].status` is set to `"restricted"`). The additional `5000.0` penalty from the high-severity incident is silently lost.

For comparison:
- `medical_emergency` (`zone_id = "L-N"`) correctly maps and applies the `5000.0` penalty because `"L-N"` is a valid zone.
- `concession_surge` (`zone_id = "C-N"`) correctly maps and applies the `5000.0` penalty because `"C-N"` is a valid zone.

---

## 5. Verification and Test Execution Results
All backend logic was verified against the project test suite using `pytest`.
- **Test Command**: `python -m pytest` inside `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend`
- **Result**: `166 passed in 11.37s`
- **Integrity Status**: Verified that all API contracts are functionally correct under sequential/synchronous execution.
