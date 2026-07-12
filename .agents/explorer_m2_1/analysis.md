# M2: Telemetry & Simulation Verification — Detailed Analysis Report

This report presents findings from a read-only investigation of the live stadium telemetry simulation engine and its integration with the front-end control room dashboard.

---

## 1. Executive Summary

While the backend telemetry simulator (`engine.py`) and UI dashboard (`OpsDashboard.tsx`) have a solid architectural foundation with passing tests, there are several **critical compliance gaps** with the **R3: Live Stadium Telemetry & Incident Simulation Engine** requirements:

*   **UI Polling Interval**: The UI polls the backend state every 5 seconds (`setInterval(poll, 5000)` in `App.tsx`), violating the requirement of `<= 2s` polling intervals.
*   **Missing Scenario Injection Panel**: There is no Scenario Injection Panel on the UI dashboard.
*   **Missing Custom Spikes**: The backend does not support triggering the specific scenarios: "Gate 2 Turnstile Malfunction", "Medical Emergency at Section 104", or "Half-Time Concession Surge".
*   **Fidelity Discrepancy**: The static stadium model uses direction-based names (e.g., gates `G-N`, `G-S`, `G-E`, `G-W` and zones `L-N`, `L-S`, `L-E`, `L-W`), meaning "Gate 2" and "Section 104" do not exist in the current fixtures.
*   **Concession Queue Modeling**: Concession wait-times/queues are not simulated or modified in the simulator's dynamic state.

---

## 2. Detailed Findings

### A. Telemetry Simulator Engine (`backend/app/simulator/`)
*   **State & Capacity**: The system uses `fixtures.py` to define MetLife Stadium with 12 zones. The total capacity is `82,500` fans. The simulator engine (`engine.py`) uses a `step` function to scale occupancy up to 92% in the seating bowl during the LIVE phase, meaning it simulates 80,000+ fans.
*   **Gate Throughput**: Gates (`G-N`, `G-S`, `G-E`, `G-W`) have dynamic throughput rates based on the match phase. Queue wait times are modeled in minutes (`queue_minutes`). Gates change to `"restricted"` when queue times exceed 12 minutes.
*   **Incidents**: Incidents are spawned randomly via `_maybe_spawn_incident` with types `medical`, `congestion`, `lost_child`, and `entry_bottleneck`. Organizers can manually report incidents using the `report_incident` tool.
*   **Concession Queues Gap**: While concessions are loaded as static amenities (in `fixtures.py`), their queues or wait times are **not** modeled or updated in the simulator state.
*   **No Scenario Triggering API**: The simulator lacks methods to inject specific structured scenarios that simulate gate failures, localized medical crises, or concession rushes.

### B. UI Polling & Telemetry Feed (`frontend/src/`)
*   **Telemetry Polling**: `frontend/src/App.tsx` retrieves telemetry from `/state` via a `setInterval(poll, 5000)` polling mechanism. This is a 5-second interval, violating the R3 requirement of `<= 2s`.
*   **UI Lag**: Polling is asynchronous. However, a 5-second update cycle causes the dashboard to appear static, failing to provide the fast real-time feedback loop required by judges.
*   **No WebSockets**: WebSockets are not used.

### C. Scenario Injection Panel & Custom Spikes
*   **No Panel**: The frontend lacks any scenario injection controls or a panel.
*   **Unresolved Names**:
    *   **Gate 2 Malfunction**: No gate matches "Gate 2" (only North, South, East, West gates exist).
    *   **Medical Emergency at Section 104**: No zone matches "Section 104" (zones use lower/club/upper tiers with North/South/East/West directions, e.g., `L-N`).
    *   **Half-Time Concession Surge**: Halftime concourse occupancy spikes are modeled overall, but individual concessions do not have wait times or queue indicators.

---

## 3. Reconciliation with R3 Requirements

| Requirement | Code Location | Status | Details / Gaps |
| :--- | :--- | :--- | :--- |
| **80,000+ simulated fan movements** | `backend/app/simulator/engine.py` | **Fully Met** | Simulates 82,500 total capacity with phase-based occupancy rates up to 92%. |
| **Gate throughput spikes** | `backend/app/simulator/engine.py` | **Fully Met** | Throughput spikes up to 320/min during arrival/exit phases; queue wait times adjust dynamically. |
| **Concession queues** | `backend/app/simulator/fixtures.py` | **Not Met** | Concessions are static; wait times or queues are not simulated in the state snapshot. |
| **Security alerts** | `backend/app/simulator/engine.py` | **Partially Met** | Spawns generic active incidents, but lacks dedicated security-specific alert types. |
| **Simulation start via toggle** | `backend/app/main.py` | **Not Met** | Simulator runs automatically on backend startup; no on-demand start/stop toggle exists. |
| **WebSockets or fast polling <= 2s** | `frontend/src/App.tsx` | **Not Met** | Polling is set to 5000ms. |
| **Scenario Injection panel** | `frontend/src/` | **Not Met** | No panel exists on the frontend dashboard. |
| **"Gate 2 Turnstile Malfunction"** | `backend/app/simulator/` | **Not Met** | Gate 2 is not in fixtures; no turnstile failure trigger exists. |
| **"Medical Emergency at Section 104"** | `backend/app/simulator/` | **Not Met** | Section 104 is not in fixtures; no specific incident trigger exists. |
| **"Half-Time Concession Surge"** | `backend/app/simulator/` | **Not Met** | No concession queue surge trigger or concession-specific metrics exist. |
| **Verify instant system adaptation** | `backend/app/tools/handlers.py` | **Not Met** | Decision-support `recommend_action` handles generic high-density or gate restrictions but cannot adapt to custom untriggerable scenarios. |

---

## 4. Proposed Fix & Verification Strategy

### A. Backend Changes

#### 1. Map Scenario Names to Fixtures
Map the judge-facing scenario descriptions to the existing structural model:
*   **Gate 2 Malfunction** $\rightarrow$ Map to **South Gate** (`G-S`).
*   **Medical Emergency at Section 104** $\rightarrow$ Map to **Lower North Seating** (`L-N`, near Waypoint `WP-Z-L-N`).
*   **Half-Time Concession Surge** $\rightarrow$ Map to **Club North Concourse** (`C-N` or concourse `C-CL-N`).

#### 2. Extend Simulator State for Scenario Spikes
Introduce active scenario states inside `StadiumSimulator`:
```python
# In backend/app/simulator/engine.py
class StadiumSimulator:
    def __init__(self, ...):
        ...
        self.active_scenarios: set[str] = set()
```
Create a new API endpoint `/api/scenario` to trigger/reset scenarios:
*   `POST /api/scenario/trigger` with body `{"scenario": "gate_malfunction" | "medical_emergency" | "concession_surge"}`.
*   `POST /api/scenario/reset` to restore nominal state.

Modify `step()` in `engine.py` to apply scenario-specific modifiers:
*   **Gate Malfunction**: Set the gate status of `G-S` to `"closed"`, set throughput to `0`, and spike queue time to `45.0` minutes.
*   **Medical Emergency**: Spawn a high-severity incident at `Lower North` (`L-N`) named `"INC-MED-104"` with type `"medical"`, description `"Medical emergency reported at Section 104."`.
*   **Concession Surge**: Model wait-times for concession amenities. Add a `concession_queues` field in `StadiumSnapshot` or mutate specific concourse density (e.g., `C-CL-N` and `C-CL-S`) to `1.2` (exceeding capacity) and inject a custom congestion incident at the North main concourse.

#### 3. Update Decision-Support Heuristics (`recommend_action`)
Ensure `recommend_action` provides targeted mitigation advice when these scenarios are active:
*   If Gate Malfunction is active: Recommend redirecting arriving fans from `G-S` (South Gate) to `G-N` (North Gate).
*   If Medical Emergency is active: Recommend dispatching first aid to Lower North and creating an accessible emergency path.
*   If Concession Surge is active: Recommend advising fans to use upper-tier concession stands to relieve main level pressure.

### B. Frontend Changes

#### 1. Accelerate Polling Interval
In `frontend/src/App.tsx`, reduce the polling interval to 1.5 seconds:
```typescript
const id = setInterval(poll, 1500);
```

#### 2. Implement the Scenario Injection Panel
Create a new component `ScenarioPanel.tsx` and place it in the Control Room view:
*   **Layout**: A side panel or header control group containing three action buttons:
    1. **Trigger Gate Malfunction** (Gate 2 / South Gate)
    2. **Trigger Medical Emergency** (Section 104 / Lower North)
    3. **Trigger Half-Time Concession Surge** (North Concourse)
    4. **Reset Simulator** (restores nominal phase-based state)
*   **API Connection**: Calls `POST /api/scenario/trigger` and `POST /api/scenario/reset`.

### C. Verification Plan
1.  **Unit & Integration Tests**:
    *   Write a unit test in `test_simulator.py` to trigger each scenario and assert that the simulated states (gate throughput, active incidents, concourse density) modify correctly.
    *   Write an integration test in `test_api.py` targeting `/api/scenario/trigger` to ensure the endpoint modifies the simulator instance on `app.state.simulator`.
2.  **Visual Verification**:
    *   Open the dashboard and trigger "Gate 2 Malfunction". Verify that South Gate turns red ("closed") and the queue spikes.
    *   Trigger "Medical Emergency". Verify a new active high-severity incident appears on the incident list.
    *   Verify the unified AI assistant updates its recommendations when `recommend_action` is queried.
