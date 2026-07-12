# Handoff Report — Milestone M2: Telemetry & Simulation Verification

This report provides the results of the empirical verification of the Telemetry & Simulation components for Milestone M2.

---

## 1. Observation

### Verification Test Suite execution
We created `backend/tests/test_challenger_m2.py` and ran it using:
`.venv\Scripts\python -m pytest tests/test_challenger_m2.py -vv`
All 7 tests passed successfully:
```
tests/test_challenger_m2.py::test_polling_interval_in_frontend PASSED    [ 14%]
tests/test_challenger_m2.py::test_telemetry_simulator_updates_correctly PASSED [ 28%]
tests/test_challenger_m2.py::test_scenario_injection_gate_malfunction PASSED [ 42%]
tests/test_challenger_m2.py::test_scenario_injection_medical_emergency PASSED [ 57%]
tests/test_challenger_m2.py::test_scenario_injection_concession_surge PASSED [ 71%]
tests/test_challenger_m2.py::test_reset_recovers_stadium_state PASSED    [ 85%]
tests/test_challenger_m2.py::test_system_adapts_instantly PASSED         [100%]
```

### Polling interval
In `frontend/src/App.tsx`, the polling interval is defined at line 28:
```typescript
const id = setInterval(poll, 1500);
```

### Scenario triggers
In `backend/app/simulator/engine.py`, the three custom scenario injection mappings and reset are implemented as follows:
- **Gate Malfunction** (lines 286-305):
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
  ```
- **Medical Emergency** (lines 307-322):
  ```python
  elif scenario == "medical_emergency":
      self._active_scenarios.add("medical_emergency")
      incident = Incident(
          incident_id=f"INC-SCENARIO-MEDICAL-{int(self.sim_time)}",
          type="medical",
          location="Section 104 (Lower North)",
          zone_id="L-N",
          severity=IncidentSeverity.HIGH,
          status="active",
          created_at=self.sim_time,
          description="Medical emergency reported at Section 104. Paramedics dispatched."
      )
  ```
- **Concession Surge** (lines 324-342):
  ```python
  elif scenario == "concession_surge":
      self._active_scenarios.add("concession_surge")
      if "C-N" in self._crowd:
          self._crowd["C-N"].occupancy = int(self._crowd["C-N"].capacity * 0.90)
          self._crowd["C-N"].density = 0.90
      incident = Incident(
          incident_id=f"INC-SCENARIO-CONCESSION-{int(self.sim_time)}",
          type="congestion",
          location="Concourse A (Club North)",
          zone_id="C-N",
          severity=IncidentSeverity.HIGH,
          status="active",
          created_at=self.sim_time,
          description="Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."
      )
  ```
- **Reset State** (lines 267-284):
  ```python
  if scenario == "reset":
      self._active_scenarios.clear()
      self._incidents = [i for i in self._incidents if not i.incident_id.startswith("INC-SCENARIO-")]
      # Restore gates and crowds to nominal phase-specific targets
  ```

### E2E Test Suite Bug
Running `.venv\Scripts\python -m pytest` yielded 46 failures out of 140 tests. All 46 failures occurred in `backend/tests/test_e2e_suite.py` with:
```
E           AttributeError: 'State' object has no attribute 'simulator'
```
because tests accessed `app.state.simulator` directly outside of `with TestClient(app) as client:` contexts.

---

## 2. Logic Chain

1. **Telemetry updates correctness**:
   - The test `test_telemetry_simulator_updates_correctly` verifies that the simulator transitions MatchPhases and updates crowd occupancy and transit congestion upon steps.
   - Therefore, the telemetry simulator updates correctly.

2. **Polling Interval**:
   - Reading `frontend/src/App.tsx` shows `setInterval(poll, 1500)`.
   - 1500ms is exactly 1.5 seconds, which satisfies the condition `<= 2s`.
   - Therefore, the polling interval requirement is met.

3. **Scenario triggers and reset**:
   - The tests `test_scenario_injection_*` assert that triggering each scenario spawns the corresponding incident with correct properties and immediately updates the simulator state (Gate status/queue, Section 104 incident, and Concourse A density).
   - The test `test_reset_recovers_stadium_state` verifies that `reset` clears all scenarios and recovers nominal states.
   - Therefore, scenario triggering and reset behaviors are correct.

4. **Instant Adaptation**:
   - The test `test_system_adapts_instantly` queries the FastAPI test client.
   - It asserts that hitting `POST /simulator/scenario` immediately propagates the changes to `GET /state` snapshots without requiring another simulator tick.
   - Therefore, the system adapts instantly.

---

## 3. Caveats

- **No live Gemini calls**: All tests run in offline/mock mode to avoid triggering external service dependencies.
- **FastAPI Thread Safety**: If multiple requests read/write state concurrently, there could be race conditions since `/state` is synchronous (`def`) but modifies and reads data also accessed/mutated by the simulator async tick. This was not tested with high concurrent load.

---

## 4. Conclusion

The implementation of Milestone M2 meets the functional requirements (telemetry simulation, 1.5s polling, scenario injection, and instant state adaptation/recovery).
However, the test suite `tests/test_e2e_suite.py` is currently broken due to a lifespan lifecycle initialization issue in the tests themselves. Also, thread safety concerns exist in the routes definitions which should be mitigated by changing synchronous route handlers to `async def` or adding locking mechanisms.

---

## 5. Verification Method

To independently verify the implementation, run:

1. **Backend Verification tests**:
   ```bash
   cd backend
   .venv\Scripts\python -m pytest tests/test_challenger_m2.py -vv
   ```
2. **Frontend Unit tests**:
   ```bash
   cd frontend
   npm test
   ```
