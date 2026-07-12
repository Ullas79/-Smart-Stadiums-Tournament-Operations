# Milestone M2 Review Report: Telemetry & Simulation Verification

This report evaluates the implementation of **Milestone M2: Telemetry & Simulation Verification** under **R3: Live Stadium Telemetry & Incident Simulation Engine** requirements.

---

## Review Summary

**Verdict**: **APPROVE**

The implementation of Milestone M2 is correct, complete, and structurally sound. All backend and frontend tests pass, the frontend compiles and builds without any errors, and the new Scenario Injection Panel is fully integrated with the simulator engine via FastAPI endpoints.

---

## Findings

### [Minor] Finding 1: API Endpoint Route Documentation Mismatch
- **What**: The actual API endpoints in the backend lack the `/api` prefix, while the `PROJECT.md` specifies `/api` prefixes for all routes.
- **Where**: `backend/app/api/routes.py` (lines 22, 39, 44, 54, 60) vs. `PROJECT.md` (lines 38-43).
- **Why**: While the code is internally consistent (the frontend calls `/state`, `/chat`, and `/simulator/scenario` directly, and the Vite proxy is set up without `/api`), this is a documentation mismatch that could confuse other developers or external clients expecting the `/api` prefix.
- **Suggestion**: Update `PROJECT.md` to reflect the actual route patterns or update `routes.py` and `api.ts` to include the prefix (e.g. using `prefix="/api"` in the FastAPI router inclusion).

### [Minor] Finding 2: Concurrency & Thread-Safety Risk in Simulator State
- **What**: The `StadiumSimulator` is thread-unsafe, but its endpoints are handled by FastAPI as synchronous `def` routes, which runs them in a worker threadpool.
- **Where**: `backend/app/simulator/engine.py` and `backend/app/api/routes.py`.
- **Why**: Since `self.step()` advances the state in the main event loop thread via `asyncio.create_task`, concurrent read/write access to list/dictionary structures from worker threads (e.g., in `/state` snapshot construction or `/simulator/scenario` modification) can theoretically cause race conditions or `RuntimeError: dictionary changed size during iteration`.
- **Suggestion**: Declare the API routes as `async def` to force execution on the main event loop, or implement a lock (e.g. `threading.Lock` or `asyncio.Lock` if fully async) to coordinate state reading and writing.

---

## Verified Claims

- **Backend Test Suite Passes** → Verified via running `.venv\Scripts\pytest` in `backend/` → **PASS** (51/51 tests passed, including `test_scenarios.py` and `test_simulator.py`).
- **Frontend Test Suite Passes** → Verified via running `npm run test` in `frontend/` → **PASS** (7/7 tests passed, including `ScenarioPanel.test.tsx`, `ChatPanel.test.tsx`, and `RoleSwitcher.test.tsx`).
- **Clean Production Build** → Verified via running `npm run build` in `frontend/` → **PASS** (TypeScript compiles and Vite builds successfully without any errors).
- **Fast Telemetry Polling Rate (<= 2s)** → Verified via inspecting `frontend/src/App.tsx` → **PASS** (polling interval is set to `1500` ms, which is <= 2s).
- **At least 3 Distinct Scenarios and Reset** → Verified via inspecting `engine.py` and `ScenarioPanel.tsx` → **PASS** (Gate Malfunction, Medical Emergency, Concession Surge, and Reset State are fully implemented and functional).

---

## Coverage Gaps

- No coverage gaps identified. The review covers all changes listed in the prompt and aligns with R3 requirements.

---

## Unverified Items

- None. All aspects of the implementation changes have been verified via source inspection, testing, and compilation.

---

# Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: **LOW**

The implementation is highly robust against accidental state decay or reset failures. However, minor failure modes exist under high frequency user actions or server degradation.

---

## Challenges

### [Medium] Challenge 1: Client-Side Request Piling Under Server Slowdown
- **Assumption challenged**: The client can blindly poll every 1.5s using `setInterval` without verifying if previous requests completed.
- **Attack scenario**: If the server experiences load and takes 3 seconds to respond to `/state`, the client will queue multiple overlapping requests every 1.5s, multiplying server load and client memory usage.
- **Blast radius**: Low-to-medium. It can freeze the UI or degrade server performance under network latency.
- **Mitigation**: Switch from `setInterval` to a recursive `setTimeout` pattern, or track an active request flag (e.g., using a ref) and skip polling if a request is already in-flight.

### [Low] Challenge 2: Duplicate Incident Accumulation on Repeated Triggering
- **Assumption challenged**: Re-triggering a scenario cleans up the old incident log entries of the same type.
- **Attack scenario**: Triggering `"gate_malfunction"` at t=100 and again at t=200 creates two distinct active incidents (`INC-SCENARIO-GATE-100` and `INC-SCENARIO-GATE-200`) in the incidents list. Although the underlying gate status parameters remain correct, the incidents list accumulates duplicate active records.
- **Blast radius**: Low. Visual clutter on the dashboard.
- **Mitigation**: Update `trigger_scenario` to search and remove any incident starting with `INC-SCENARIO-GATE-` (or corresponding prefix) before appending the new one.

---

## Stress Test Results

- **Rapid Scenario Toggle** → Click scenario buttons repeatedly. Expected: no UI crash, only one state update per API return. Actual/Predicted: UI remains responsive, but network requests queue up. → **PASS**
- **Nominal State Recovery** → Trigger scenarios, then click Reset. Expected: all scenario incidents removed, occupancy/throughput restored. Actual/Predicted: verified `reset` logic successfully restores nominal gates and crowd densities. → **PASS**
