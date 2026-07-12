# M2: Telemetry & Simulation Verification — Detailed Analysis Report

## Executive Summary
This analysis report evaluates the implementation of the live stadium telemetry and scenario simulation engine against the **R3: Live Stadium Telemetry & Incident Simulation Engine** requirements. The investigation identified critical gaps between the project specifications/contracts and the actual codebase. While the dynamic crowd simulator is functional and runs correctly in the background, the UI polling interval is too slow, the scenario injection endpoint is completely missing from the backend, and the interactive scenario injection panel is absent from the frontend UI.

---

## 1. Telemetry Simulator Implementation
The simulation engine is built as an in-process, asynchronous task within the FastAPI backend:
- **FastAPI Lifespan Integration (`backend/app/main.py`)**:
  - During application startup (`lifespan`), the stadium model is loaded via `fixtures.load_stadium_model()`.
  - The `StadiumSimulator` is instantiated with `tick_seconds=settings.sim_tick_seconds` (default: 5) and `speed=settings.sim_speed` (default: 60).
  - The simulator starts its asynchronous task by calling `await sim.start()`.
  - During application shutdown, the simulator task is cleanly canceled with `await sim.stop()`.
- **Simulator Engine (`backend/app/simulator/engine.py`)**:
  - Runs an infinite loop `_run()` that calls `await asyncio.sleep(self.tick_seconds)` and invokes `self.step(self.tick_seconds * self.speed)`.
  - Each simulation step advances `sim_time` by 300 simulation seconds (5s tick * 60x speed multiplier = 5 minutes).
  - Updates crowd density across 12 zones based on target percentages matching the current match phase (Pre-Open, Arrival, Pre-Kickoff, Live, Halftime, Full-Time, Post-Event).
  - Updates gate status (`open` or `restricted`) based on throughput spikes and queue times.
  - Ticks transit wait times and congestion based on match phase.
  - Spawns incidents probabilistically (medical, congestion, lost child, entry bottleneck) depending on the match phase density.
  - Manually logs incidents via `report_incident()`, which appends new `Incident` objects to `self._incidents`.
- **Fixtures (`backend/app/simulator/fixtures.py`)**:
  - Houses the static MetLife Stadium venue structure, including a capacity of 82,500, levels, quadrants (North, South, East, West), gates (G-N, G-S, G-E, G-W), amenities, and waypoints with accessible paths (elevators/escalators).

---

## 2. UI Telemetry Polling & Lag Analysis
- **Polling Loop (`frontend/src/App.tsx`)**:
  - The React frontend establishes a state polling loop via `setInterval(poll, 5000)` inside a `useEffect` hook.
  - It fetches the full stadium snapshot from the `/state` endpoint.
- **Lag Analysis & UI Responsiveness**:
  - The frontend React rendering performs cleanly without thread-blocking calculations (it performs a simple loop map over 12 zones and 4 gates).
  - However, the 5-second polling interval violates the **R3 requirement** of `<= 2s` fast polling intervals. It is too slow to provide the feel of "real-time telemetry" needed for judges/reviewers.

---

## 3. Scenario Injection & Operational Spikes
R3 explicitly requires that judges/reviewers can trigger custom operational spikes on demand (specifically **Gate 2 Malfunction**, **Medical Emergency**, and **Half-Time Surge**).
- **Backend Gaps**:
  - The FastAPI backend router in `backend/app/api/routes.py` contains **no endpoint** to handle scenario injections (e.g., `POST /api/simulator/scenario` defined in `PROJECT.md` is missing).
  - The `StadiumSimulator` in `backend/app/simulator/engine.py` does not have any predefined fixtures or methods to trigger the specific scenarios.
  - MetLife gates are defined as `G-N`, `G-S`, `G-E`, and `G-W` (North, South, East, West Gates). There is no gate named "Gate 2" in the fixtures, meaning the malfunction must be mapped to one of the existing gates (e.g., G-N / North Gate).
- **Frontend Gaps**:
  - `frontend/src/api.ts` does not contain any API client method to make a POST request to a scenario endpoint.
  - The Scenario Injection panel is **entirely missing** from the frontend component tree and `App.tsx` layout. There are no UI controls to trigger custom spikes.

---

## 4. Reconcile with R3 Requirements (Gaps Table)

| R3 Requirement | Current Codebase Implementation Status | Gaps / Issues Found | Severity |
| :--- | :--- | :--- | :--- |
| **Real-time telemetry updates (polling <= 2s)** | Polling implemented, but set to **5 seconds** in `App.tsx` | Fails R3 <= 2s polling requirement. | **Medium** |
| **Scenario Injection Panel** | **Not implemented** (No UI components exist) | Judges cannot trigger scenarios. | **High** |
| **Gate 2 Turnstile Malfunction** | **Not implemented** in backend or simulator | No API endpoint, no simulator hook, Gate 2 is not mapped. | **High** |
| **Medical Emergency at Section 104** | **Not implemented** in backend or simulator | No API endpoint, no simulator hook. | **High** |
| **Half-Time Concession Surge** | **Not implemented** in backend or simulator | No API endpoint, no simulator hook. | **High** |

---

## 5. Detailed Recommendations & Proposed Fixes

To achieve full compliance with R3, the following modifications are recommended for the implementation team:

### A. Simulator Engine Expansion (`backend/app/simulator/engine.py`)
Add a new method `trigger_scenario` to `StadiumSimulator` to manipulate crowd and gate state programmatically:
```python
    def trigger_scenario(self, scenario: str) -> Incident:
        self._snapshot_cache = None
        if scenario == "gate_malfunction":
            # Map Gate 2 to Gate G-N (North Gate)
            gate = self._gates.get("G-N")
            if gate:
                gate.status = "restricted"
                gate.queue_minutes = 22.5
                gate.throughput_per_min = 15
            return self.report_incident(
                type="entry_bottleneck",
                location="Gate 2 (North Gate)",
                severity="high",
                description="Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."
            )
        elif scenario == "medical_emergency":
            # Section 104 is in lower bowl, nearest Lower East
            return self.report_incident(
                type="medical",
                location="Section 104 (Lower East)",
                severity="high",
                description="Medical emergency reported at Section 104. Paramedics dispatched."
            )
        elif scenario == "concession_surge":
            # Halftime concession spike: raise concourse zone density to 90% (exceeds 85% limit)
            cd = self._crowd.get("L-N")
            if cd:
                cd.occupancy = int(cd.capacity * 0.90)
                cd.density = 0.90
            return self.report_incident(
                type="congestion",
                location="Concourse A (C-L-N)",
                severity="high",
                description="Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."
            )
        else:
            raise ValueError(f"Unknown scenario type: {scenario}")
```

### B. Backend Route Additions (`backend/app/api/routes.py`)
Add the route handler for triggering scenarios:
```python
from fastapi import HTTPException

@router.post("/simulator/scenario")
def trigger_scenario(req: dict, request: Request):
    sim = request.app.state.simulator
    scenario = req.get("scenario")
    if not scenario:
        raise HTTPException(status_code=400, detail="Missing 'scenario' field in payload")
    try:
        inc = sim.trigger_scenario(scenario)
        return {"status": "success", "incident": inc.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### C. Frontend API Client Addition (`frontend/src/api.ts`)
Expose the scenario trigger method:
```typescript
export function triggerScenario(scenario: string): Promise<{ status: string; incident: any }> {
  return jsonFetch("/simulator/scenario", {
    method: "POST",
    body: JSON.stringify({ scenario }),
  });
}
```

### D. Polling Interval Adjustment (`frontend/src/App.tsx`)
Reduce the polling interval from `5000` to `1500` ms (1.5 seconds) to comply with R3:
```typescript
    poll();
    const id = setInterval(poll, 1500); // Changed from 5000 to 1500 for <= 2s real-time feed
```

### E. Scenario Panel Component Creation
Create `frontend/src/components/ScenarioPanel.tsx`:
```typescript
import { useState } from "react";
import { triggerScenario } from "../api";
import "./ScenarioPanel.css";

interface Props {
  onTriggered: () => void;
}

export function ScenarioPanel({ onTriggered }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTrigger = async (scenario: string) => {
    setStatus("Triggering...");
    setError(null);
    try {
      const res = await triggerScenario(scenario);
      setStatus(`Triggered: ${res.incident.type} at ${res.incident.location}`);
      onTriggered();
    } catch (e) {
      setError((e as Error).message);
      setStatus(null);
    }
  };

  return (
    <div className="panel scenario-panel">
      <h3>Scenario Injection</h3>
      <div className="scenario-buttons">
        <button className="btn-scenario" onClick={() => handleTrigger("gate_malfunction")}>
          🛃 Gate 2 Malfunction
        </button>
        <button className="btn-scenario" onClick={() => handleTrigger("medical_emergency")}>
          🚑 Medical (Sec 104)
        </button>
        <button className="btn-scenario" onClick={() => handleTrigger("concession_surge")}>
          🍔 Halftime Surge
        </button>
      </div>
      {status && <p className="success-text">{status}</p>}
      {error && <p className="error-text">⚠️ {error}</p>}
    </div>
  );
}
```
*Note: This panel must be imported and rendered in `App.tsx` next to the `OpsDashboard` component.*

---

## 6. Verification Strategy

### Step 1: Unit & Route Integration Tests
The implementation team should add tests in `backend/tests/test_simulator.py` and `backend/tests/test_api.py` to assert correct behavior:
- Verify calling `sim.trigger_scenario("gate_malfunction")` correctly sets Gate G-N to "restricted", updates queue minutes, and registers a high severity incident.
- Verify `POST /api/simulator/scenario` returns `200 OK` and a structured JSON payload for valid inputs, and `400 Bad Request` for unknown scenarios.

### Step 2: E2E Telemetry Frequency Check
- Spin up the backend and frontend locally.
- Open the browser console and inspect the network tab.
- Confirm `/state` requests are dispatched every **1.5 seconds** (1500ms) without causing UI lag or stuttering.

### Step 3: Interactive Verification
- Switch to the Organizer role in the UI.
- Click the "Gate 2 Malfunction" button.
- Verify that the active incident count increases immediately, "Gate 2 (North Gate) turnstile malfunction" is displayed under incidents, and North Gate's status changes to "restricted" with an increased queue duration.
- Ask the organizer assistant: *"Give me operational recommendations."*
- Verify that the Gemini assistant outputs specific recommendations to mitigate the Gate 2 bottleneck (such as redirecting fans to the East/West gates).
