# Detailed Codebase Analysis: M2 Telemetry & Simulation Verification

This report analyzes the MetLife Stadium telemetry simulator and frontend UI to verify alignment with the **R3. Live Stadium Telemetry & Incident Simulation Engine** requirements.

---

## 1. Executive Summary

A comprehensive inspection of the backend and frontend code reveals **critical gaps** between the current implementation and the R3 requirements specified in the project specs:
1. **Telemetry Update Intervals**:
   - The frontend currently polls every **5 seconds** (exceeding the required limit of **<= 2 seconds**).
   - The backend simulator ticks on a **5-second real-world interval**, meaning any faster frontend polling will only fetch duplicate, cached snapshots.
2. **Scenario Injection Panel**:
   - The Scenario Injection panel is **entirely missing** from the React frontend.
   - The backend contains no endpoints or services to inject specific scenarios or operational spikes.
   - There are mismatches between the required scenario details (e.g., "Gate 2", "Section 104") and the simulator's static model labels ("North Gate", "Lower North seats", etc.).

---

## 2. Direct Code Observations

### A. Polling and Simulator Tick Intervals
In the frontend, `frontend/src/App.tsx` contains the following polling logic (lines 16-32):
```typescript
16:   useEffect(() => {
17:     let active = true;
18:     async function poll() {
19:       try {
20:         const s = await fetchState();
21:         if (active) setSnapshot(s);
22:       } catch {
23:         /* backend not up yet */
24:       }
25:     }
26:     poll();
27:     const id = setInterval(poll, 5000);
28:     return () => {
29:       active = false;
30:       clearInterval(id);
31:     };
32:   }, []);
```
* **Observation**: Line 27 shows `setInterval(poll, 5000)`. The UI fetches telemetry state once every 5000 milliseconds (5 seconds).

In the backend, `backend/app/core/config.py` defines the default settings (lines 31-33):
```python
31:     # Simulator
32:     sim_tick_seconds: int = 5
33:     sim_speed: int = 60
```
* **Observation**: Line 32 sets the real-time tick interval to 5 seconds.
* **Observation**: Line 33 sets the simulation speed to `60` (1 real second advances 60 simulation seconds, so 5 real seconds advance 5 minutes).

In the backend engine `backend/app/simulator/engine.py` (lines 112-119):
```python
112:     async def _run(self) -> None:
113:         try:
114:             while True:
115:                 await asyncio.sleep(self.tick_seconds)
116:                 self.step(self.tick_seconds * self.speed)
117:         except asyncio.CancelledError:
118:             pass
```
* **Observation**: Line 115 sleeps for `self.tick_seconds` (5 seconds by default) before advancing the simulation.

---

### B. Scenario Injection & Operational Spikes
1. **Frontend UI**:
   - `frontend/src/App.tsx` renders `<ChatPanel>` and `<OpsDashboard>` inside `<main className="app-main">`. No other interactive control panels or components exist.
   - `frontend/src/components/OpsDashboard.tsx` is read-only; it displays crowd density, gates, active incidents, and transit load from the snapshot, but includes no buttons, switches, or forms to trigger/inject scenarios.
2. **Backend Routes (`backend/app/api/routes.py`)**:
   - The file defines only four routes: `/health` (GET), `/role` (GET), `/state` (GET), and `/chat` (POST). There are no POST endpoints to receive scenario triggers (e.g. `/api/scenario`).
3. **Data Model Mismatch**:
   - In `backend/app/simulator/fixtures.py`, the gates are loaded as (lines 86-92):
     - `G-N` ("North Gate")
     - `G-S` ("South Gate")
     - `G-E` ("East Gate")
     - `G-W` ("West Gate")
     - There is no gate named **"Gate 2"** (which is specified in R3 requirements: "Gate 2 Turnstile Malfunction").
   - Similarly, the zones are loaded as (lines 57-73):
     - quadrants like `L-N` ("Lower North"), `L-S` ("Lower South"), etc.
     - There is no zone named **"Section 104"** (which is specified in R3 requirements: "Medical Emergency at Section 104").

---

## 3. Reconciliation with R3 Requirements

Below is the verification checklist mapping current code against the **R3. Live Stadium Telemetry & Incident Simulation Engine** requirements.

| Requirement Description | Code Implementation | Status | Gaps Found |
|---|---|---|---|
| **Single toggle/command starts simulation** | Lifespan context manager starts the simulator automatically on FastAPI backend startup (`backend/app/main.py:45`). | **PASSED** | None. Starts automatically with server. |
| **Telemetry updates emitted under <= 2s intervals** | Frontend polls every 5s (`App.tsx:27`). Backend simulator ticks every 5s (`config.py:32`). | **FAILED** | Both frontend polling and backend tick rates are set to 5s instead of <= 2s. |
| **No UI lag during continuous polling** | Fetch queries `/state` which returns a lightweight JSON snapshot (~1.5 KB). Minimal overhead. | **PASSED** | Polling itself does not cause lag, but the interval is too slow. |
| **Scenario Injection panel allows triggering 3+ events** | No injection panel exists in the UI. No endpoints exist on the backend. | **FAILED** | Scenario panel and trigger mechanism are completely missing. |
| **Handles "Gate 2 Turnstile Malfunction"** | Neither the model nor the engine supports custom gate failure injection. "Gate 2" does not exist in the gates fixture list. | **FAILED** | Need to map "Gate 2" to a simulator gate (e.g., North Gate G-N / Gate 2) and implement logic to fail/restrict the gate. |
| **Handles "Medical Emergency at Section 104"** | No manual incident injection via UI exists. "Section 104" does not exist in the zones fixture list. | **FAILED** | Need to map "Section 104" to a simulator zone (e.g., Lower North L-N / Section 104) and trigger a high-severity medical incident there. |
| **Handles "Half-Time Concession Surge"** | No surge injection API exists. While the simulator naturally moves to halftime phase at t=6300s, it cannot be triggered on-demand. | **FAILED** | Need to implement an on-demand phase override or crowd density surge trigger that creates concession bottlenecks. |
| **Verifies instant system adaptation** | The system prompt summary is updated, and the agent adapts, but without scenario injection, this cannot be demonstrated on demand. | **FAILED** | AI and UI can theoretically adapt (the agent has tools to query state/incidents), but the triggers themselves must be functional. |

---

## 4. Recommended Fix & Verification Strategy

Since code modifications are restricted to read-only for this task, the following **design specification** is proposed for the implementer agent to fully close the R3 gaps.

### Step 1: Update Telemetry Intervals (Backend + Frontend)
* **Backend Config (`backend/app/core/config.py`)**:
  - Update `sim_tick_seconds: int = 1` so the simulator ticks once per real second.
  - Update `sim_speed: int = 300` or adjust accordingly so that the match timeline advances at the desired rate. For example, if we tick every 1 real second and want to advance 5 minutes of sim time per tick (to keep the match moving fast), set speed accordingly.
* **Frontend Polling (`frontend/src/App.tsx`)**:
  - Change the polling interval from `5000` to `1000` (1 second), which is <= 2s and ensures real-time telemetry changes are visible immediately.

### Step 2: Implement Scenario API in Backend
* **FastAPI Router (`backend/app/api/routes.py`)**:
  - Create a new POST endpoint `/api/scenario` that accepts a payload indicating which scenario to inject:
    ```json
    {
      "scenario": "gate_malfunction" | "medical_emergency" | "halftime_surge"
    }
    ```
* **Simulator Engine (`backend/app/simulator/engine.py`)**:
  - Add an injection method `inject_scenario(self, name: str)` on `StadiumSimulator`:
    - **`gate_malfunction`**: Find North Gate (`G-N`, mapping it to "Gate 2 Turnstile") and set its status to `"closed"`, throughput to `0`, and queue time to a high value (e.g., `45` minutes). This will immediately trigger the system prompt's bottleneck indicators.
    - **`medical_emergency`**: Inject a high-severity incident at zone `L-N` (mapping it to "Section 104"), with description `"Medical Emergency: Fan unconscious at Section 104. First Aid dispatched."`.
    - **`halftime_surge`**: Manually advance the simulator's `sim_time` to the halftime timeline (`fixtures.HALFTIME_AT`), or force concourse crowd densities (`C-L-N`, etc.) to 100% capacity to trigger concession queues and bottlenecks.

### Step 3: Implement Scenario Injection Panel in Frontend
* **Create a Component (`frontend/src/components/ScenarioPanel.tsx`)**:
  - Build a simple panel containing three buttons:
    - 🔴 **Trigger Gate 2 Malfunction**
    - 🔴 **Trigger Medical Emergency (Sec. 104)**
    - 🔴 **Trigger Half-Time Concession Surge**
  - Add a post request handler in `frontend/src/api.ts` to call `/api/scenario` when clicked.
  - Position this panel inside `frontend/src/App.tsx` (e.g., either above or next to the `RoleSwitcher`).

### Step 4: Verification Method for the Implementer
1. **Interval Verification**:
   - Open browser developer tools (Network tab) and confirm that `/state` requests are sent every 1.0 seconds.
   - Confirm that the simulator time (returned in `match.sim_time`) updates continuously.
2. **Scenario Verification**:
   - Click "Trigger Gate 2 Malfunction". The UI should instantly show "North Gate (Gate 2)" status as "closed" with a 45 min queue. The organizer chat suggestion or action recommendation should flag this gate and suggest rerouting fans.
   - Click "Trigger Medical Emergency (Sec. 104)". The active incidents list on the dashboard should instantly display a high-severity incident at Section 104.
   - Click "Trigger Half-Time Concession Surge". The match phase should immediately shift to "halftime", and concourse densities should spike, generating crowd alerts.
