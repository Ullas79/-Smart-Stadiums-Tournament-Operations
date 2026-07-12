# Handoff Report - Milestone M2: Telemetry & Simulation Verification

## 1. Observation

- **Backend code implementation**: 
  - Modified `backend/app/simulator/engine.py` to add `trigger_scenario` method, initialized `self._active_scenarios = set()`, and updated `_update_crowd`, `_update_gates`, and `_update_incidents` to enforce and persist the custom scenarios.
  - Modified `backend/app/api/routes.py` to add `POST /simulator/scenario` with input validation schema `ScenarioRequest` and 400 error handling.
- **Frontend code implementation**:
  - Modified `frontend/src/api.ts` to add `triggerScenario` POST helper.
  - Modified `frontend/vite.config.ts` to map `/simulator/scenario` to `http://localhost:8000`.
  - Modified `frontend/src/App.tsx` to include `ScenarioPanel` and update polling interval to `1500` ms.
  - Created `frontend/src/components/ScenarioPanel.tsx` and `frontend/src/components/ScenarioPanel.css`.
- **Test files**:
  - Created `backend/tests/test_scenarios.py` to test the state machines and routes.
  - Created `frontend/src/__tests__/ScenarioPanel.test.tsx` to verify component rendering and event handlers.
- **Test execution results**:
  - Run backend pytest:
    ```
    tests\test_agent_loop.py .......                                         [ 13%]
    tests\test_api.py ......                                                 [ 25%]
    tests\test_integration.py ...                                            [ 31%]
    tests\test_scenarios.py .....                                            [ 41%]
    tests\test_simulator.py .............                                    [ 66%]
    tests\test_tools.py .................                                    [100%]
    ======================== 51 passed, 1 warning in 2.60s ========================
    ```
  - Run frontend vitest:
    ```
    ✓ src/__tests__/RoleSwitcher.test.tsx (2 tests) 99ms
    ✓ src/__tests__/ScenarioPanel.test.tsx (3 tests) 191ms
    ✓ src/__tests__/ChatPanel.test.tsx (2 tests) 230ms

    Test Files  3 passed (3)
         Tests  7 passed (7)
    ```
  - Run frontend build:
    ```
    vite v5.4.21 building for production...
    transforming...
    ✓ 40 modules transformed.
    rendering chunks...
    computing gzip size...
    dist/index.html                   0.43 kB │ gzip:  0.30 kB
    dist/assets/index-ClzgVctc.css    6.44 kB │ gzip:  1.81 kB
    dist/assets/index-8wIJwSoy.js   150.93 kB │ gzip: 48.75 kB
    ✓ built in 1.64s
    ```

## 2. Logic Chain

1. **Gate Malfunction Scenario Logic**: Set status to `"restricted"`, queue minutes to `45.0`, and throughput to `0` at gate `G-S` (South Gate) and spawn high-severity `entry_bottleneck` incident with location `"Gate 2 (South Gate)"` and description `"Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."`.
2. **Medical Emergency Scenario Logic**: Spawn high-severity `medical` incident with location `"Section 104 (Lower North)"` and description `"Medical emergency reported at Section 104. Paramedics dispatched."`.
3. **Concession Surge Scenario Logic**: Set crowd density at `C-N` to `0.90` (occupancy = capacity * 0.90) and spawn high-severity `congestion` incident at `"Concourse A (Club North)"` with description `"Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."`.
4. **Reset Scenario Logic**: Clear all active scenario incidents (identifiable by `INC-SCENARIO-` prefix), clear the active scenarios tracking set, and reset the gate status and crowd densities to nominal values (handling `PRE_OPEN` phase as 0.0 occupancy).
5. **Persistence Logic**: The standard simulator tick loops update crowd and gate values. To avoid overwriting the simulated scenarios on ticks, we check `self._active_scenarios` at the end of the simulator tick update steps (`_update_crowd` and `_update_gates`) and enforce the scenario values. We also skip `INC-SCENARIO-` incidents during the normal `_update_incidents` aging step to prevent them from auto-resolving before the user clicks reset.
6. **API and Frontend integration**: The routing, API proxy, state polling (accelerated to 1.5s), and visual ScenarioPanel components cleanly link the frontend controls to the simulator backend.

## 3. Caveats

- We assumed that manual staff-reported incidents created via `/chat` or `report_incident` with prefix `INC-MAN-` should NOT be cleared by `reset` unless requested. Currently, `reset` explicitly clears only the simulator scenario incidents (prefix `INC-SCENARIO-`).
- If custom gates or zones are added to the model configuration, the hardcoded IDs like `G-S`, `C-N`, and `L-N` must exist in the models for scenario triggers to map correctly.

## 4. Conclusion

The dynamic operational simulation scenarios are fully implemented, verified, and integrated from the simulator engine core up to the responsive dashboard interface. Both backend unit tests and frontend vitest suites run and pass successfully. Zero compilation/build errors exist in the codebase.

## 5. Verification Method

- **To run backend unit tests**:
  - Run the following command in the `backend` directory:
    ```powershell
    .venv\Scripts\pytest
    ```
- **To run frontend unit tests**:
  - Run the following command in the `frontend` directory:
    ```bash
    npm run test
    ```
- **To verify compilation/build**:
  - Run the following command in the `frontend` directory:
    ```bash
    npm run build
    ```
