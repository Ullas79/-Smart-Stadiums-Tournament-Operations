## 2026-07-11T23:10:47+05:30
You are the Concurrency and Stress Test Implementer.
Your working directory is: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_stress
Your identity is: teamwork_preview_worker
Your task is to implement the thread-safety locks, fix routing cache key invalidation, resolve the gate_malfunction scenario zone ID mismatch, and write concurrent pytest stress tests.

Specifically:
1. Thread-safety: In `backend/app/simulator/engine.py`, introduce a `threading.RLock` inside `StadiumSimulator.__init__` (e.g. `self._lock = threading.RLock()`). Ensure that all state-modifying and state-reading methods are thread-safe by wrapping their logic inside `with self._lock:` blocks. Target these methods:
   - `trigger_scenario`
   - `dispatch_incident`
   - `resolve_incident`
   - `set_gate_status`
   - `mitigate_bottleneck`
   - `step` (or operations in it mutating state)
   - `snapshot` (wrap the list copy and reading logic in the lock to avoid RuntimeError: list iterator mutated during iteration)
   Ensure you import `threading` at the top of the file.

2. Caching optimization: In `backend/app/tools/handlers.py`, modify `_ROUTE_CACHE` lookup key. Remove `int(sim_time)` or `sim_time` from the cache key inside `_shortest_path`. Caching should only depend on static structures and state signatures (such as `model_id`, `src`, `dst`, `accessible_only`, `gate_sig`, `crowd_sig`, `inc_sig`) so that it doesn't get bypassed/invalidated on every single simulation second when the graph's weight parameters have not changed.

3. Propagation mismatch: In `backend/app/tools/handlers.py`'s `_build_graph` function, check for active incident matches. Currently, `gate_malfunction` sets `zone_id = "G-S"` but the waypoint maps to seating zone `"L-S"`, resulting in a mismatch and preventing the high-severity `5000.0` penalty from propagating to edges connected to the gate. Add a check to verify if the incident's `zone_id` directly matches the gate waypoint itself (e.g. check if `incident.zone_id == e.from_id or incident.zone_id == e.to_id` or `f"WP-{incident.zone_id}" in (e.from_id, e.to_id)`), ensuring the `5000.0` penalty is properly propagated to the gate's edges.

4. Concurrent Stress Test: Create a new pytest file `backend/tests/test_stress.py`. Write automated stress tests checking for:
   - Concurrent scenario injections under high crowd densities (>85%) across match phases (pre_match, first_half, halftime, second_half, post_match).
   - Simulate concurrent method calls or HTTP requests (e.g. using `concurrent.futures.ThreadPoolExecutor` or `threading.Thread`) against the `StadiumSimulator` and API to ensure the backend executes without deadlock, race conditions, or unhandled exceptions, and that all route penalties and volunteer dispatch updates take effect instantly and accurately.
   - Verify that Dijkstra pathfinding (`find_route`) correctly dynamically re-routes paths under these concurrent updates.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Confirm all 166+ backend pytest tests pass cleanly by running `.venv\Scripts\python.exe -m pytest` from the `backend` directory. Write a detailed report of what code was modified, run the tests, and report the outputs in your handoff report to `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_stress\handoff.md`.
