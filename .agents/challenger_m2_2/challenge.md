## Challenge Summary

**Overall risk assessment**: MEDIUM

While the core simulation logic, scenario injection, and instant adaptation are functional and verified by our test suite, there are significant architectural and testing flaws that introduce operational and stability risks:
1. **E2E Test Suite Bug**: The e2e test suite (`tests/test_e2e_suite.py`) fails 46 tests out of 140 because it attempts to access the FastAPI app state `app.state.simulator` directly without entering the lifespan context.
2. **FastAPI Thread Safety Violations**: API routes (like `/state`) are declared as synchronous `def` functions rather than `async def`, causing FastAPI to run them on background threadpools. Since `StadiumSimulator` is thread-unsafe and runs mutating ticks on the main asyncio event loop, this is a race condition risk that can cause concurrent modification errors (`RuntimeError: dictionary changed size during iteration`) and intermittent production crashes.
3. **In-Memory State Volatility**: The stadium simulator state resides completely in-memory, resetting to pre-kickoff (`-10 min`) on process restarts (such as Render deployments or inactive scale-downs), which invalidates real-time assistance.

---

## Challenges

### [Medium] Challenge 1: E2E Test Suite Failures due to Missing Lifespan context

- **Assumption challenged**: The test suite assumed that `app.state.simulator` is instantiated and populated immediately after calling `create_app()`.
- **Attack scenario**: Running pytest on the full backend test suite collects 140 tests and fails 46 of them with `AttributeError: 'State' object has no attribute 'simulator'`.
- **Blast radius**: Developers cannot run the full test suite out-of-the-box to verify changes, hindering CI/CD pipelines.
- **Mitigation**: Update all test cases in `tests/test_e2e_suite.py` that access `app.state.simulator` to execute inside a `with TestClient(app) as client:` block, ensuring that the ASGI lifespan event handler is triggered and populates the app state properly.

### [High] Challenge 2: Thread-Unsafe Simulator Mutated Concurrently

- **Assumption challenged**: Simulator state reads and updates are synchronized or thread-safe.
- **Attack scenario**: The simulator updates its state in a background task on the main event loop (`asyncio.create_task`). Concurrently, the FastAPI route `@router.get("/state") def get_state(...)` is synchronous (`def` instead of `async def`), so FastAPI executes it in an external thread pool. If a client reads the state while the simulator is mutating it, Python will raise thread-safety race exceptions, resulting in `500 Internal Server Errors`.
- **Blast radius**: Intermittent API failure and state corruption under load.
- **Mitigation**: Define all FastAPI routes reading/writing simulator state as `async def` so they execute on the main thread's event loop, or implement thread-safe locks/deep-copy snapshots.

### [Medium] Challenge 3: Simulator Reset and Match Clock Drift on Process Restart

- **Assumption challenged**: In-memory state and counters are durable.
- **Attack scenario**: In environments like Render or local container deployments, processes may restart or scale down. When restarted, the simulator clock resets back to `-10 * 60` sim-seconds, losing current match phase and incident history.
- **Blast radius**: Operational users and fans receive incorrect pre-match guidance during live games.
- **Mitigation**: Persist active incidents, current simulation phase, and time offset to a database or cache (e.g. Redis, SQLite), and sync the simulation clock with real-world epoch time offsets.

---

## Stress Test Results

- **Frontend Polling Interval** → Interval must be <= 2.0s → Detected `setInterval(poll, 1500)` in `frontend/src/App.tsx` (1.5 seconds) → **PASS**
- **Gate Malfunction Scenario** → Triggers Gate 2 turnstile incident at G-S, restricts gate, sets queue minutes to 45.0, throughput to 0 → State updated correctly immediately → **PASS**
- **Medical Emergency Scenario** → Triggers high-severity medical incident at Section 104 (L-N) → Active incident registered successfully → **PASS**
- **Concession Surge Scenario** → Triggers high-severity congestion incident at Concourse A (C-N), sets occupancy to 90% and density to 0.90 → Density updated to 0.90 immediately → **PASS**
- **Reset State** → Clears all active scenarios and incident list, recovers Gate 2 and Concourse A to nominal targets → Nominal state restored cleanly → **PASS**
- **Instant Adaptation** → Simulator state updates immediately upon POST request, returned on next GET `/state` → State updates instantly without waiting for next simulation tick → **PASS**

---

## Unchallenged Areas

- **Gemini Live Function Calling** — out of scope for Milestone M2 (which focuses on simulator correctness and telemetry updates).
- **Physical stadium deployment infrastructure** — out of scope.
