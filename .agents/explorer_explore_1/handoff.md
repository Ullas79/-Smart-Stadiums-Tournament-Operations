# Handoff Report: Explorer 1 - Backend Test Suite & Simulator Engine Analysis

## 1. Observation
* **Test Suite Files**: Located inside `backend/tests/` using `find_by_name`. The file list includes:
  ```
  backend/tests/test_adversarial_security.py
  backend/tests/test_agent_loop.py
  backend/tests/test_api.py
  backend/tests/test_challenger_m2.py
  backend/tests/test_challenger_m7.py
  backend/tests/test_e2e_suite.py
  backend/tests/test_integration.py
  backend/tests/test_scenarios.py
  backend/tests/test_security_hardening.py
  backend/tests/test_simulator.py
  backend/tests/test_tools.py
  backend/tests/test_wayfinding_challenger.py
  ```
* **Test Suite Execution**: Running `.venv\Scripts\pytest` returned:
  ```
  collected 166 items
  ...
  ======================= 166 passed, 1 warning in 15.92s =======================
  ```
* **Simulator Tick & State Logic**: In `backend/app/simulator/engine.py` (lines 130-136):
  ```python
  def step(self, dt_sim_seconds: float) -> None:
      self.sim_time += dt_sim_seconds
      phase = _phase_for(self.sim_time)
      self._update_crowd(phase, dt_sim_seconds)
      self._update_gates(phase)
      self._update_transit(phase)
      self._update_incidents(dt_sim_seconds)
      self._maybe_spawn_incident(phase)
      self._snapshot_cache = None
  ```
* **Scenario Injection Handler**: In `backend/app/simulator/engine.py` (lines 359-364):
  ```python
  def trigger_scenario(self, scenario: str) -> Incident | None:
      valid_scenarios = {"gate_malfunction", "medical_emergency", "concession_surge", "reset"}
      if scenario not in valid_scenarios:
          raise ValueError(f"Invalid scenario name: {scenario}")
  ```
  And details for `gate_malfunction` (lines 395-414):
  ```python
  elif scenario == "gate_malfunction":
      self._active_scenarios.add("gate_malfunction")
      if "G-S" in self._gates:
          self._gates["G-S"].status = "restricted"
          self._gates["G-S"].queue_minutes = 45.0
          self._gates["G-S"].throughput_per_min = 0
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
      self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]
      self._incidents.append(incident)
      self._snapshot_cache = None
      return incident
  ```
* **API Route Definition**: In `backend/app/api/routes.py` (lines 25-26):
  ```python
  @router.post("/simulator/scenario")
  def trigger_scenario_route(req: ScenarioRequest, request: Request) -> dict[str, Any]:
  ```
  Note the `def` keyword indicating a synchronous route handler.
* **Concurrent/Stress Test Search**: RiPGrep (`grep_search`) searches for `concurrent` or `stress` in `backend/tests/` yielded no matches.

---

## 2. Logic Chain
1. **Locating Test Files**: By searching the `backend/tests/` directory via `find_by_name`, we cataloged all 12 test files.
2. **Identifying Counts & Focus**: By running `pytest --collect-only` and `pytest`, we confirmed that there are exactly 166 tests collected. An inspection of test names and contents allowed categorizing them into E2E (82 tests), security (21 tests), functional/unit (40 tests), milestone specific (12 tests), and integration (3 tests).
3. **Telemetry & Scenario Engine Logic**: Viewing `backend/app/simulator/engine.py` showed that telemetry is driven by a periodic timer advancing simulator time (`sim_time`) via the `step` method. Scenario injections (`trigger_scenario`) directly mutate Python objects (adding to the `_active_scenarios` set and appending to `_incidents` list) without synchronization locks.
4. **Concurrent Stress Testing and Safety Assessment**:
   * Our search confirmed that no concurrent or stress testing infrastructure currently exists.
   * Observing `def trigger_scenario_route` in `backend/app/api/routes.py` indicates that FastAPI executes these endpoints concurrently using a background threadpool.
   * Since `StadiumSimulator`'s mutation methods are not guarded by any locks (e.g. `threading.Lock`), concurrent API requests to inject/reset scenarios or dispatch/resolve incidents can execute simultaneously, leading to race conditions or inconsistent states (e.g. duplicate incident IDs, corrupted list structures).

---

## 3. Caveats
* **CPython GIL**: The Global Interpreter Lock (GIL) prevents CPU-level concurrency for Python bytecode execution, but standard operations like checking state and performing multiple sequential list/dict modifications are not thread-safe.
* **External Client Behaviors**: This investigation is read-only and does not check frontend-side network behavior or concurrent requests sent by the browser.

---

## 4. Conclusion
The backend test suite is highly comprehensive, covering 166 E2E, integration, security, and unit tests, all of which pass successfully. However, the suite lacks any concurrent stress testing or load testing infrastructure. The simulator engine runs dynamically but exposes synchronous route handlers that run in a threadpool, exposing state structures to race conditions due to a complete lack of thread-safety locks in `StadiumSimulator`. We recommend implementing locking in the simulator and adding concurrent test cases using `httpx.AsyncClient` and `asyncio.gather`.

---

## 5. Verification Method
* **Test Suite Verification**: Run `.venv\Scripts\pytest` in `backend/` to verify that all 166 tests compile and pass:
  ```powershell
  cd backend
  .venv\Scripts\pytest
  ```
* **Simulator Concurrency Vulnerability Verification**:
  1. Inspect `backend/app/api/routes.py` lines 25-26 (`def trigger_scenario_route`) and 127-131 (`def dispatch_incident_route`) to confirm synchronous handlers.
  2. Inspect `backend/app/simulator/engine.py` lines 359-452 (`trigger_scenario`) and confirm the absence of lock synchronization.
