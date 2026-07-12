# Handoff Report — Concurrency and Stress Test Implementation

## 1. Observation
The following code structures and behaviors were directly observed during the investigation and implementation phases:

- **Baseline Test Verification**:
  Running `.venv\Scripts\python.exe -m pytest` from the `backend/` directory initially returned:
  ```
  ======================= 166 passed, 1 warning in 8.46s ========================
  ```

- **Missing Thread Safety**:
  In `backend/app/simulator/engine.py`, the `StadiumSimulator` class initialized lists, dicts, and metadata (such as `self._crowd`, `self._gates`, `self._incidents`, and `self._snapshot_cache`) but did not contain any synchronization locks, exposing state-modifying and state-reading methods to concurrent access.

- **Route Cache Key Invalidation**:
  In `backend/app/tools/handlers.py`'s `_shortest_path` function, the `_ROUTE_CACHE` cache lookup key was generated as:
  ```python
  cache_key = (model_id, src, dst, accessible_only, sim_time, gate_sig, crowd_sig, inc_sig)
  ```
  Since `sim_time` changed on every simulation second, this key was invalidated on every simulation second even when static and dynamic structures/weights had not changed.

- **Propagation Mismatch**:
  In `backend/app/tools/handlers.py`'s `_build_graph` function, active incidents were evaluated to apply severity penalties. The check did not directly verify matches against the gate waypoint itself when the scenario was `gate_malfunction` (which sets `zone_id = "G-S"` but the nearest waypoint matches seating zone `"L-S"`).
  ```python
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
  ```

## 2. Logic Chain
Step-by-step reasoning from observations to the implemented solution:

1. **Thread-Safety Locks**:
   To prevent race conditions (such as list mutation during iteration in `snapshot` or concurrent updates to the same simulator attributes), we introduced a `threading.RLock()` in `StadiumSimulator.__init__` as `self._lock`.
   By wrapping targeted methods `trigger_scenario`, `dispatch_incident`, `resolve_incident`, `set_gate_status`, `mitigate_bottleneck`, `step`, and `snapshot` with `with self._lock:` blocks, we guaranteed that all concurrent state-reading and state-modifying actions are mutually exclusive.

2. **Cache Key Optimization**:
   By removing `sim_time` from the `cache_key` tuple in `_shortest_path`, the cache keys only depend on signatures of actual weights/structures (`model_id`, `src`, `dst`, `accessible_only`, `gate_sig`, `crowd_sig`, `inc_sig`). This prevents unnecessary cache misses when weights have not changed, solving the cache key bypass issue.

3. **Propagation Correction**:
   To ensure that the high-severity `5000.0` penalty from the `gate_malfunction` incident (where `zone_id` is `"G-S"`) propagates to edges connected to the gate waypoint (`WP-G-S`), we added an explicit check:
   ```python
   elif incident.zone_id and (incident.zone_id in (e.from_id, e.to_id) or f"WP-{incident.zone_id}" in (e.from_id, e.to_id)):
       affected = True
   ```
   This ensures that gate incident zone IDs correctly map to the corresponding gate waypoints on the graph, applying the `5000.0` severity penalty.

4. **Concurrent Stress Testing**:
   Created `backend/tests/test_stress.py` containing:
   - `test_concurrent_scenarios_and_routing_stress`: parametrized across match phases (`pre_match`, `first_half`, `halftime`, `second_half`, `post_match`). It sets up a detour model, boosts crowd densities to 90% (guaranteeing >85% density), and launches concurrent threads invoking state-mutating functions and Dijkstra pathfinding (`find_route`). It asserts that both direct routes (when gate is open) and detour routes (when South gate has high penalty/malfunction) are dynamically chosen and computed without deadlocks or race conditions.
   - `test_concurrent_api_requests_stress`: uses `fastapi.testclient.TestClient` inside a thread pool to verify concurrency safety of the web endpoints, temporarily raising `settings.rate_limit_requests` to prevent false positive 429 errors.

## 3. Caveats
- Standard FastAPI `TestClient` is run inside a synchronous thread pool. Lifespan context must be entered using `with TestClient(app) as client:` to ensure global state attributes are properly bound.
- The `rate_limit_requests` setting was elevated to `100000` temporarily during API stress tests to avoid hitting the rate limiter middleware which defaults to 100 requests per IP.

## 4. Conclusion
All concurrency issues (lack of thread-safety locks), route caching inefficiencies, and propagation mismatches have been resolved. The simulator and web endpoints can handle heavy concurrent load without exceptions, race conditions, or deadlocks. All routing and scenario features work seamlessly.

## 5. Verification Method
To verify the implementation independently, execute the following commands from the `backend/` directory:

1. **Run Stress Tests Only**:
   ```powershell
   .venv\Scripts\python.exe -m pytest tests\test_stress.py
   ```
   Expected output: `6 passed`

2. **Run All Backend Tests**:
   ```powershell
   .venv\Scripts\python.exe -m pytest
   ```
   Expected output: `172 passed`
