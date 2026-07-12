# Challenge Report: Milestone M2 Verification

## Challenge Summary

**Overall risk assessment**: LOW

Milestone M2 (Telemetry & Simulation Verification) is fully compliant with the requirements. The telemetry simulator, state polling, custom event triggers, and state recovery have been verified via static and dynamic E2E testing. The system responds instantly to injected events and recovers completely upon reset.

---

## Challenges

### [Low] Challenge 1: Polling Interval Hardcoding
- **Assumption challenged**: The 1.5s polling interval is hardcoded in the React frontend (`App.tsx`). If the network latency exceeds 1.5s or backend response time degrades under load, consecutive state requests might stack up, causing client-side resource strain or request duplication.
- **Attack scenario**: Simultaneous user sessions under high concurrent load causing backend latency to spike above 1.5s.
- **Blast radius**: Increased traffic to `/state` endpoint, potential resource starvation on the backend.
- **Mitigation**: Implement dynamic delay/jitter or switch from `setInterval` to nested `setTimeout` where the next poll is only scheduled after the previous response completes.

### [Low] Challenge 2: Deterministic Simulator Ticking
- **Assumption challenged**: The backend simulator uses a simple sleep tick loop (`await asyncio.sleep(self.tick_seconds)`). If the thread becomes blocked by heavy CPU operations (e.g., Dijkstra route calculations or TF-IDF calculations), the simulator tick will drift and skip match schedule events.
- **Attack scenario**: A surge of GenAI concierge queries causing heavy route search CPU usage, delaying the event loop.
- **Blast radius**: The match clock and stadium state update sluggishly or inconsistently.
- **Mitigation**: Calculate actual elapsed time using monotonic clock timestamps instead of assuming uniform intervals in simulator steps.

---

## Stress Test Results

| Scenario / Verification | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|
| **Static Polling Interval Check** | Polling interval defined in `App.tsx` must be $\le 2.0$s. | Found `setInterval(poll, 1500)` (1.5s interval). | **PASS** |
| **Telemetry Simulator Step** | Simulator retrieves initial state (`venue_name="MetLife Stadium"`) and starts at phase `"pre_open"` with 0 incidents. | Loaded `MetLife Stadium`, phase `"pre_open"`, 0 active incidents. | **PASS** |
| **Gate Malfunction Scenario** | Triggering `gate_malfunction` yields success, spawns a high-severity `entry_bottleneck` incident at "Gate 2 (South Gate)", sets gate `G-S` status to `"restricted"`, throughput to `0`, queue to `45.0` mins. | Created incident `INC-SCENARIO-GATE-...` type `entry_bottleneck`, status `restricted`, throughput `0`, queue `45.0` mins. | **PASS** |
| **Medical Emergency Scenario** | Triggering `medical_emergency` spawns a high-severity `medical` incident at "Section 104 (Lower North)". | Created incident `INC-SCENARIO-MEDICAL-...` type `medical`, location `"Section 104 (Lower North)"`. | **PASS** |
| **Concession Surge Scenario** | Triggering `concession_surge` spawns a high-severity `congestion` incident at "Concourse A (Club North)" and sets zone `C-N` crowd density to `0.90` (90%). | Created incident `INC-SCENARIO-CONCESSION-...` type `congestion`, zone `C-N` density `0.90`. | **PASS** |
| **Reset Stadium State** | Triggering `reset` clears all scenario-injected incidents, returns gate `G-S` queue to `0.0` mins / `"open"`, and resets zone `C-N` density to nominal `0.0`. | All scenario incidents deleted, gate `G-S` returned to `"open"` / `0.0` mins, zone `C-N` density returned to `0.0`. | **PASS** |

---

## Unchallenged Areas

- **Actual Network Congestion** — The tests were performed locally using Starlette `TestClient` (in-memory HTTP server). Network-induced latency or jitter was not simulated.
- **Concurrent Concierge Interaction during Incident Injection** — Focus was constrained to simulation telemetry and API routes under R3; E2E LLM behavior under load belongs to M6.
