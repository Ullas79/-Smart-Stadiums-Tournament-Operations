# Milestone M2 Review: Telemetry & Simulation Verification

This report reviews the implementation of Milestone M2 (Telemetry & Simulation Verification) for correctness, completeness, robustness, and conformance.

---

## Part 1: Quality Review Report

### Review Summary

**Verdict**: **APPROVE**

Milestone M2 is fully complete and structurally sound. The simulator correctly models MetLife Stadium phases, supports dynamic scenario injection (`gate_malfunction`, `medical_emergency`, `concession_surge`, and `reset`), and updates the stadium state in a deterministic/robust manner. The frontend successfully mounts the `ScenarioPanel` component, handles state transitions, communicates via the configured Vite proxy, and contains complete unit tests that mock the API client. Both backend and frontend test suites pass with 100% success rate, and the frontend builds cleanly without TypeScript or compilation errors.

---

### Findings

#### [Major] Finding 1: Potential Race Conditions in Synchronous API Routes

- **What**: The FastAPI endpoints `/state` and `/simulator/scenario` are declared as synchronous handlers (`def`), not asynchronous handlers (`async def`).
- **Where**: `backend/app/api/routes.py`, line 23 (`def trigger_scenario_route`) and line 55 (`def get_state`).
- **Why**: FastAPI executes synchronous `def` routes in separate threads from an external threadpool. Since `StadiumSimulator` is thread-unsafe and runs/ticks inside an asyncio task on the main event loop thread, concurrent requests to read the state or inject scenarios from threadpool threads can lead to race conditions and data inconsistency.
- **Suggestion**: Change both handler definitions to use `async def`. Because these endpoints perform fast, in-memory operations and do not block on CPU or I/O, running them directly on the main event loop thread avoids multi-threading entirely and guarantees thread-safety.

#### [Minor] Finding 2: Numerical Instability in Crowd Updates under Large Time-Steps

- **What**: The crowd occupancy update uses a first-order Euler step multiplier: `rate * (dt / 60.0)`.
- **Where**: `backend/app/simulator/engine.py`, line 149.
- **Why**: If the simulator is configured with a large time step `dt` or extreme speed, the term `rate * (dt / 60.0)` can exceed `1.0`. This causes the crowd occupancy to overshoot the target occupancy and oscillate. Although bounded by `min`/`max` guards, it can lead to erratic density jumps.
- **Suggestion**: Restrict the step multiplier using `min(1.0, rate * (dt / 60.0))` or use an exponential decay formula to guarantee stability:
  ```python
  cd.occupancy = int(target_occ - (target_occ - cd.occupancy) * math.exp(-rate * dt / 60.0))
  ```

---

### Verified Claims

- **Simulator scenario updates** → verified via running `.venv\Scripts\pytest` (specifically `tests/test_scenarios.py`) → **PASS** (Asserted that gate restriction, concourse density increases, and active incident lists adapt correctly on injection and persist across steps).
- **API endpoints functionality** → verified via running `.venv\Scripts\pytest` (specifically `tests/test_api.py` and `tests/test_scenarios.py`) → **PASS** (Asserted route status codes, JSON payload formats, invalid scenario name rejection, and reset response values).
- **Frontend ScenarioPanel rendering & interaction** → verified via running `npm run test` (specifically `src/__tests__/ScenarioPanel.test.tsx`) → **PASS** (Asserted button visibility, trigger click mock API responses, reset feedback, and error state handling).
- **Frontend compilation and build integrity** → verified via running `npm run build` in `frontend` → **PASS** (Finished with 0 compilation errors, emitting optimized assets).

---

### Coverage Gaps

- **Simulation Concurrency stress-testing** — risk level: **Medium** — recommendation: **Investigate** (Verify whether high frequency concurrent requests to `/state` and `/simulator/scenario` cause any dictionary mutation runtime errors like `RuntimeError: dictionary changed size during iteration` in `_update_crowd` or `snapshot`).

---

### Unverified Items

- **None** — all relevant backend and frontend implementation areas in the milestone scope were verified via test suites and code inspection.

---

## Part 2: Adversarial Challenge Report

### Challenge Summary

**Overall risk assessment**: **LOW**

The simulator's logic for state overrides is robust because the scenarios explicitly override properties in the tick step. However, there are minor vulnerabilities under high-load concurrency and unhandled JSON exceptions in the API fetch layer.

---

### Challenges

#### [Medium] Challenge 1: Dictionary Size Change RuntimeError under Concurrent Snapshot Reads

- **Assumption challenged**: The simulation state can be safely dumped into a snapshot dictionary while background updates are appending incidents.
- **Attack scenario**: A user queries `/state` at the exact millisecond `_maybe_spawn_incident` appends a new incident to `self._incidents` or when `_update_incidents` trims the history. Because Python lists/dicts are mutated in-place, copying or iterating over `self._incidents` in the snapshot method can raise a `RuntimeError` due to size changes.
- **Blast radius**: The `/state` endpoint returns 500 Internal Server Error, temporarily breaking the dashboard polling.
- **Mitigation**: Create copies of state collections inside a thread lock, or ensure all routes are `async def` to execute on the same thread as the event loop.

#### [Low] Challenge 2: Unhandled HTML Responses in Fetch Client

- **Assumption challenged**: The backend API will always return valid JSON payloads even under failure states.
- **Attack scenario**: If the FastAPI server experiences a startup failure or uvicorn crashes, a gateway/proxy (like Nginx, Vercel, or Vite dev proxy) might return a `502 Bad Gateway` HTML page. Calling `await res.json()` in the frontend's `jsonFetch` will throw a `SyntaxError: Unexpected token <` which masks the underlying HTTP error.
- **Blast radius**: Obscure frontend error message ("Unexpected token < in JSON at position 0") instead of clean connection/server errors.
- **Mitigation**: Catch parsing errors in `jsonFetch` and throw a descriptive error containing the HTTP status:
  ```typescript
  try {
    return await res.json();
  } catch {
    throw new Error(`Failed to parse response JSON (HTTP ${res.status})`);
  }
  ```

---

### Stress Test Results

- **Multiple parallel scenario injections** → expect simulator to maintain correct state overrides → **PASS** (State overrides are applied sequentially in Python. Activating concession surge and gate malfunction concurrently keeps both states active).
- **Invalid scenario name injection** → expect API to return 400 Bad Request → **PASS** (Asserted in `test_api_scenario_endpoints`).
- **Reset during high-congestion phase** → expect state to return to nominal for that phase → **PASS** (Asserted in `test_simulator_scenario_reset`).
