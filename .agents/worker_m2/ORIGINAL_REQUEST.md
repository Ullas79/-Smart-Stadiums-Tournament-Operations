## 2026-07-10T12:05:03Z

<USER_REQUEST>
You are the worker for Milestone M2: Telemetry & Simulation Verification.
Your working directory is C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m2\.

Perform the following implementation and verification tasks:
1. Backend Changes:
   - In `backend/app/simulator/engine.py`: Implement a `trigger_scenario(self, scenario: str) -> Incident` method on `StadiumSimulator` to dynamically inject the required operational scenarios:
     * `gate_malfunction` -> Maps to South Gate (`G-S`). Change status to `"restricted"`, queue_minutes to `45.0`, throughput to `0`, and spawn a high-severity `entry_bottleneck` incident with location `"Gate 2 (South Gate)"` and description `"Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."`.
     * `medical_emergency` -> Maps to Lower North Seating (`L-N`). Spawn a high-severity `medical` incident with location `"Section 104 (Lower North)"` and description `"Medical emergency reported at Section 104. Paramedics dispatched."`.
     * `concession_surge` -> Maps to Club North Concourse (`C-N`). Set the occupancy of `C-N` to 90% of its capacity (density = 0.90) and spawn a high-severity `congestion` incident at `"Concourse A (Club North)"` with description `"Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."`.
     * Provide a way to reset/clear active scenarios (e.g. `reset` scenario that clears manually injected incidents and resets gate and crowd densities to nominal).
   - In `backend/app/api/routes.py`: Add the `POST /simulator/scenario` route handler. It must expect a JSON body with `{"scenario": "scenario_name"}`, validate that the scenario is one of the supported types, invoke `sim.trigger_scenario(scenario)`, and return `{"status": "success", "incident": incident.model_dump()}`. Handle invalid scenario names with a 400 HTTP error.
2. Frontend Changes:
   - In `frontend/src/api.ts`: Add `triggerScenario(scenario: string)` function which posts to `/simulator/scenario`.
   - In `frontend/vite.config.ts`: Add `/simulator/scenario` proxy target pointing to `http://localhost:8000`.
   - In `frontend/src/App.tsx`:
     * Accelerate the state polling loop by changing the interval from `5000` to `1500` ms.
     * Import and place a new `ScenarioPanel` component in the UI layout so that users can interact with it.
   - Create `frontend/src/components/ScenarioPanel.tsx` (and companion CSS if needed): Render a panel containing three buttons to trigger the scenarios, plus a reset button. Make it responsive, visually clean, and accessible.
3. Verification and Testing:
   - Write comprehensive unit tests in backend (e.g., in a new `backend/tests/test_scenarios.py` or existing tests) to verify simulator state changes on scenario trigger and API endpoint responses.
   - Ensure the backend tests run and pass using the pytest command.
   - Ensure frontend tests run and pass.
   - Compile both frontend and backend to verify zero build errors.

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.
</USER_REQUEST>
