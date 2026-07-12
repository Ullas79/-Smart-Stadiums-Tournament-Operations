# Backend Test Suite & Simulator Engine Analysis Report

## Executive Summary
This report analyzes the backend testing suite, simulator engine logic, scenario injection mechanism, and concurrency aspects of the SmartStadium AI application. We identified a total of **166 tests** across 12 test files, covering everything from granular unit checks to complete End-to-End (E2E) workflow scenarios. We also conducted a code-level review of the simulator engine (`backend/app/simulator/engine.py`) and identified that the simulator state updates and scenario injections are not thread-safe. Furthermore, there is currently **no existing concurrent stress test suite or infrastructure** in the codebase.

---

## 1. Backend Test Files
All 12 test files are located in `backend/tests/`. Below is a catalog of the located test files:

| File Name | Location | Primary Focus |
|---|---|---|
| `test_adversarial_security.py` | `backend/tests/` | Adversarial prompt injections, role-based access control, security guards. |
| `test_agent_loop.py` | `backend/tests/` | Agent reasoning loop execution, prompt assembly, and fallback mechanisms. |
| `test_api.py` | `backend/tests/` | HTTP endpoints validation using FastAPI TestClient (status codes, JSON schemas). |
| `test_challenger_m2.py` | `backend/tests/` | Verification tests for Milestone M2 (polling intervals, basic simulator updates). |
| `test_challenger_m7.py` | `backend/tests/` | Security bypass/adversarial tests (escaping input checks, rate limits, size limit bypass). |
| `test_e2e_suite.py` | `backend/tests/` | Comprehensive feature coverage (Tiers 1-4, feature interactions, and realistic scenarios). |
| `test_integration.py` | `backend/tests/` | Integration between the agent, tool registry, and simulator over conversation turns. |
| `test_scenarios.py` | `backend/tests/` | Simulator scenario injection unit tests and API scenario endpoints. |
| `test_security_hardening.py` | `backend/tests/` | Security headers, payload size limits, rate limiting, and RBAC guards. |
| `test_simulator.py` | `backend/tests/` | Core simulator logic (crowd metrics, gate queues, phase-based transitions, fixtures). |
| `test_tools.py` | `backend/tests/` | Tool handlers execution, role permissions, routing, schedule lookup. |
| `test_wayfinding_challenger.py` | `backend/tests/` | Wayfinding-specific edge cases (dynamic routing, accessibility preferences). |

---

## 2. Test Count and Categorization
A total of **166 tests** were collected and verified as passing (running `.venv\Scripts\pytest` took ~15.9s). 

### Count by Test File
* **`test_e2e_suite.py`**: **82 tests** (Opaque-box E2E testing partitioned into Tier 1 (F1-F7), Tier 2 (boundaries), Tier 3 (interactions), and Tier 4 (real-world scenarios)).
* **`test_tools.py`**: **18 tests** (Unit/Integration focus on tool handlers, volunteer/fan/organizer permissions, Dijkstra wayfinding routing, and translation helpers).
* **`test_simulator.py`**: **13 tests** (Unit/Integration testing of venue loading, graph configuration, crowd dynamics per match phase, and manual incidents).
* **`test_api.py`**: **8 tests** (Integration testing of general FastAPI endpoints).
* **`test_security_hardening.py`**: **8 tests** (Security testing verifying headers, rate limits, payload size constraints, and prompt injection filters).
* **`test_adversarial_security.py`**: **7 tests** (Security testing of model prompt protections and RBAC tool execution guards).
* **`test_agent_loop.py`**: **7 tests** (Unit/Integration testing of the GenAI agent's reasoning loop and tool call extraction).
* **`test_challenger_m2.py`**: **7 tests** (Milestone-specific integration tests verifying simulator ticking and frontend polling intervals).
* **`test_challenger_m7.py`**: **6 tests** (Security testing of potential bypass methods: environment variables, newlines, and PII filters).
* **`test_scenarios.py`**: **5 tests** (Unit/Integration testing of simulator scenario triggers).
* **`test_integration.py`**: **3 tests** (Integration tests verifying multi-turn assistant conversations).
* **`test_wayfinding_challenger.py`**: **2 tests** (Unit testing of elevator preferences and routing around restricted gates).

### Categorization by Focus
1. **End-to-End (E2E) & Integration (93 tests / 56.0%)**: Included in `test_e2e_suite.py`, `test_integration.py`, and `test_api.py`. These tests verify full request/response lifecycles, user workflows, and multi-component coordination.
2. **Unit & Functional (40 tests / 24.1%)**: Found in `test_tools.py`, `test_simulator.py`, `test_scenarios.py`, and `test_wayfinding_challenger.py`. These target specific functions, helper classes, routing algorithms, and static data structures.
3. **Security (21 tests / 12.7%)**: Located in `test_security_hardening.py`, `test_adversarial_security.py`, and `test_challenger_m7.py`. These verify input sanitation, rate-limiting middleware, payload size checks, prompt injection fallbacks, and role-based access control.
4. **Milestone Specific (12 tests / 7.2%)**: Found in `test_challenger_m2.py` and `test_agent_loop.py` (which contain helper checks, polling intervals, and setup regressions).
5. **Stress & Performance (0 tests / 0.0%)**: There are no tests checking system performance under load, concurrent request handling, or resource starvation.

---

## 3. Simulator Engine Investigation
The simulator engine is implemented in `backend/app/simulator/engine.py`.

### Telemetry Updates & Tick Loop
* **Tick Schedule**: The simulator ticks asynchronously. `StadiumSimulator.start()` starts an async loop task `_run()` that runs forever, sleeping for `tick_seconds` (defined in settings, e.g., 5 seconds) and calling `step(dt_sim_seconds)` where `dt_sim_seconds = tick_seconds * speed` (advancing simulation time rapidly).
* **Phase Determinations**: The simulator computes the active phase from the cumulative simulation clock `self.sim_time` (starts at `-10 * 60` seconds, i.e., 10 minutes before gate opening). Phases evolve through:
  `PRE_OPEN` $\rightarrow$ `ARRIVAL` $\rightarrow$ `PRE_KICKOFF` $\rightarrow$ `LIVE` $\rightarrow$ `HALFTIME` $\rightarrow$ `LIVE` (second half) $\rightarrow$ `FULL_TIME` $\rightarrow$ `POST_EVENT`.
* **Telemetry Progression**: During each tick `step()`:
  1. `_update_crowd(phase, dt)`: Gradually moves zone occupancies toward targets. For seats, targets vary by phase (e.g., peak at 0.92 during `LIVE`, dropping to 0.45 at `HALFTIME`). For concourses, a boost is added during halftime (`+0.7` fraction).
  2. `_update_gates(phase)`: Re-calculates queue times. If a gate status is set to closed, queue time becomes 99.0 minutes. Otherwise, queue time is computed as a function of gate throughput and the density of served zones.
  3. `_update_transit(phase)`: Updates waiting times and congestion levels of bus and rail endpoints.
  4. `_maybe_spawn_incident(phase)`: Uses a random number generator to spawn random incidents based on a phase-specific probability.

### Scenario Injections
Scenario injections are triggered by calling `StadiumSimulator.trigger_scenario(scenario: str)`. It modifies the simulator's internal state structures:
1. **`gate_malfunction`**:
   * Adds `"gate_malfunction"` to the `self._active_scenarios` set.
   * Modifies Gate `G-S` (South Gate) directly, setting status to `"restricted"`, queue wait time to `45.0` minutes, and throughput to `0`.
   * Appends an `Incident` to `self._incidents` with ID `INC-SCENARIO-GATE-{timestamp}`, type `"entry_bottleneck"`, location `"Gate 2 (South Gate)"`, and severity `HIGH`.
2. **`medical_emergency`**:
   * Adds `"medical_emergency"` to `self._active_scenarios`.
   * Appends an `Incident` with ID `INC-SCENARIO-MEDICAL-{timestamp}`, type `"medical"`, location `"Section 104 (Lower North)"`, and severity `HIGH`.
3. **`concession_surge`**:
   * Adds `"concession_surge"` to `self._active_scenarios`.
   * Immediately sets the occupancy of concourse North (`C-N`) to 90% of capacity and density to `0.90`.
   * Appends an `Incident` with ID `INC-SCENARIO-CONCESSION-{timestamp}`, type `"congestion"`, location `"Concourse A (Club North)"`, and severity `HIGH`.
4. **`reset`**:
   * Clears the `self._active_scenarios` set.
   * Removes all incidents starting with `INC-SCENARIO-` from `self._incidents`.
   * Recalculates nominal gate wait times and sets zone occupancies back to target fractions matching the current phase (e.g. restoring concourse density back to 0.0).

---

## 4. Concurrent Stress & Scenario Test Infrastructure Analysis
An investigation was performed to identify any existing concurrent stress tests or infrastructure.

### Analysis of Existing Test Suite
* We searched the entire test suite for asynchronous execution groups, stress-test scripts, or multi-threaded/concurrent request loops. **No stress testing scripts or concurrent tests exist.**
* The test client used is `fastapi.testclient.TestClient`, which is synchronous and runs requests sequentially.

### Concurrency Architecture & Thread-Safety Risks
Although the simulator runs a single background loop as an asyncio task, HTTP request handlers can run concurrently. A detailed check of `backend/app/api/routes.py` reveals:

1. **Synchronous Endpoint Handlers**:
   The FastAPI routes for scenarios, dispatch, and resolving incidents are declared as synchronous functions (`def` instead of `async def`):
   ```python
   @router.post("/simulator/scenario")
   def trigger_scenario_route(req: ScenarioRequest, request: Request): ...

   @router.post("/api/incidents/dispatch")
   def dispatch_incident_route(req: DispatchRequest, request: Request): ...
   ```
2. **FastAPI Threading Model**:
   FastAPI executes synchronous `def` routes in an external threadpool (using `anyio.to_thread.run_sync`) to prevent blocking the main asyncio event loop.
3. **Lack of Mutex / Locks**:
   The `StadiumSimulator` state (such as `self._incidents`, `self._active_scenarios`, and `self._gates`) is modified directly in these endpoints via:
   * `self._active_scenarios.add(...)`
   * `self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]`
   * `self._incidents.append(...)`
   There are no thread locks (`threading.Lock` or `threading.RLock`) protecting these states.
4. **Potential Race Conditions**:
   If multiple clients send concurrent POST requests (e.g., injecting scenarios or dispatching staff to the same incident simultaneously):
   * Python's list comprehensions and append operations are executed across multiple operations. Two threads executing `self._incidents = [i for ...]` concurrently may overwrite each other's updates, leading to lost updates or duplicate scenario incident entries.
   * The cache variable `self._snapshot_cache = None` is set without synchronization. A thread generating a snapshot might read a partially modified or inconsistent state from another thread.

### Recommendation
To verify and protect the backend against concurrent scenario injections:
1. Introduce a thread-safe lock (`threading.Lock`) inside `StadiumSimulator` to synchronize state mutations in `trigger_scenario`, `dispatch_incident`, `resolve_incident`, `set_gate_status`, and `mitigate_bottleneck`.
2. Add a concurrent pytest stress test (using `anyio` or `asyncio.gather` with `httpx.AsyncClient`) that triggers multiple scenario injections concurrently to verify the backend resolves requests safely without state corruption.
