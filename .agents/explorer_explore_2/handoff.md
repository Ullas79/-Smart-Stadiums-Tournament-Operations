# Handoff Report — Explorer 2

## 1. Observation
The following source code and test suite details were observed:
- **Dijkstra pathfinding & caching**: In `backend/app/tools/handlers.py`:
  - `_shortest_path` starts at line 495: `def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:`
  - Caching is managed via `_ROUTE_CACHE` at line 492.
  - The cache key includes `sim_time` at line 513: `cache_key = (model_id, src, dst, accessible_only, sim_time, gate_sig, crowd_sig, inc_sig)` where `sim_time` is cast to an integer at line 508: `sim_time = int(snap.match.sim_time)`.
  - Dynamic route penalties are updated in `_build_graph` starting at line 418: `def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:`
- **Volunteer Dispatch**: In `backend/app/simulator/engine.py`:
  - `dispatch_incident` starts at line 454: `def dispatch_incident(self, incident_id: str, assigned_staff: str) -> Incident:`
  - The method mutates the matching incident at lines 472-473:
    ```python
    i.assigned_staff = assigned_staff
    i.description = f"{i.description} [Dispatched: {assigned_staff}]"
    ```
- **FastAPI Endpoints**: In `backend/app/api/routes.py`:
  - `dispatch_incident_route` is a standard `def` endpoint at line 131: `def dispatch_incident_route(req: DispatchRequest, request: Request) -> dict[str, Any]:`
  - `trigger_scenario_route` is a standard `def` endpoint at line 26: `def trigger_scenario_route(req: ScenarioRequest, request: Request) -> dict[str, Any]:`
- **Gate Malfunction Scenario**: In `backend/app/simulator/engine.py`:
  - Scenario incident initialization starts at line 401:
    ```python
    incident = Incident(
        incident_id=f"INC-SCENARIO-GATE-{int(self.sim_time)}",
        type="entry_bottleneck",
        location="Gate 2 (South Gate)",
        zone_id="G-S",
        severity=IncidentSeverity.HIGH,
        status="active",
        created_at=self.sim_time,
        description="Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."
    )
    ```
  - However, in `backend/app/simulator/fixtures.py`, zones are loaded via `load_zones()` (lines 67-98). The zone list includes seating zones (`"L-S"`, `"C-S"`, `"U-S"`), but `"G-S"` is not a zone ID.
  - In `backend/app/tools/handlers.py` (lines 445-446):
    ```python
    from_zone = _waypoint_to_zone_id(e.from_id, ctx.model)
    to_zone = _waypoint_to_zone_id(e.to_id, ctx.model)
    ```
    And in the incident loop at lines 473-474:
    ```python
    elif incident.zone_id and incident.zone_id in (from_zone, to_zone):
        affected = True
    ```
- **Test execution**: Proposing the command `python -m pytest` inside `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend` completed successfully with `166 passed in 11.37s`.

---

## 2. Logic Chain
1. **Dijkstra pathfinding and caching**:
   - `sim_time` is cast to an integer at line 508 and is a component of the cache key at line 513.
   - If the simulation time advances by $\ge 1$ second between requests, the cache key changes.
   - Therefore, the routing cache will be bypassed for any requests occurring in different seconds, preventing effective reuse of calculated paths across time.
2. **Volunteer dispatch and tracking**:
   - The volunteer dispatch logic in the API and simulator updates the `assigned_staff` attribute and description of the `Incident` model.
   - There are no other variables or data models representing volunteer positions, status queues (e.g. idle/busy), or GPS telemetry.
   - Therefore, volunteer tracking is metadata-based rather than real-time location or activity-based.
3. **Concurrency and race conditions**:
   - Standard `def` endpoints in FastAPI are run on a concurrent thread pool.
   - The simulator ticks asynchronously on the main thread via an asyncio task, mutating state inside `self.step()`.
   - No synchronization locks (thread-level or asyncio-level) are used when accessing `self._incidents`, `self._crowd`, or `self._gates`.
   - Therefore, concurrent requests (such as scenario injections, dispatches, or chats) can run simultaneously with each other and the background simulation tick.
   - Concurrent list comprehensions on `self._incidents` (like `_update_incidents` in the tick and `trigger_scenario` in the API thread) will overwrite each other's updates, leading to lost updates.
   - Iterating over `self._incidents` in `snapshot()` while another thread is reassigning it can trigger a `RuntimeError` due to mutation during iteration.
4. **Route penalty propagation and mismatch**:
   - In `_build_graph`, the incident penalty matches `incident.zone_id` against the resolved `from_zone` and `to_zone` of edges.
   - The `gate_malfunction` scenario incident uses `zone_id = "G-S"`.
   - Seating zones associated with the South Gate resolve to `"L-S"` via `_waypoint_to_zone_id`.
   - Because `"G-S"` does not match `"L-S"`, the `5000.0` high-severity penalty is never applied to the South Gate edges. The only penalty that applies is the `1500.0` gate status penalty.

---

## 3. Caveats
- The concurrency analysis is based on code inspection. No stress tests or lock-simulation tests were executed to measure the actual occurrence rate of race conditions or thread pool starvation under high concurrent traffic.
- We assume that the simulation speed and clock rate advance sequentially as defined in configuration files.

---

## 4. Conclusion
- The pathfinding logic dynamically routes around congested areas and active incidents, but the routing cache is inefficient due to being keyed by simulation time.
- Volunteer dispatch is simple metadata modification on incidents with no spatial tracking.
- The lack of mutex/lock protection on shared simulator variables creates critical race conditions and list mutation errors under concurrent scenario injection.
- The naming mismatch between `gate_malfunction`'s `"G-S"` zone ID and the model's `"L-S"` zone ID silently disables the `5000.0` dynamic routing penalty propagation for the South Gate.

---

## 5. Verification Method
1. **Run test suite**: Run `python -m pytest` inside `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend` to verify all sequential unit and integration tests pass successfully.
2. **Inspect code references**:
   - Open `backend/app/tools/handlers.py` and inspect lines 508-518 to verify `sim_time` is cast to `int` and included in the `cache_key`.
   - Open `backend/app/simulator/engine.py` and inspect lines 401-410 to verify `gate_malfunction` scenario sets `zone_id = "G-S"`.
   - Open `backend/app/tools/handlers.py` and inspect lines 445-475 to verify how `incident.zone_id` matches against `from_zone`/`to_zone`.
