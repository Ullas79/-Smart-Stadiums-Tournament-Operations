# Milestone 12 (R2) Optimization Audit and Recommendations

## 1. Observation
We conducted an audit of the MetLife Stadium telemetry simulator and state models to identify redundant object/list allocations and linear list scans ($O(N)$) for zone density and gate status lookups.

The following specific patterns were identified in the source files:

1. **Linear Scans in `backend/app/models/stadium.py`:**
   - Lines 182-182 (`zone_by_id`):
     ```python
     return next((z for z in self.zones if z.zone_id == zone_id), None)
     ```
   - Lines 193-193 (`gate_by_id`):
     ```python
     return next((g for g in self.gates if g.gate_id == gate_id), None)
     ```
   - Lines 204-204 (`waypoint_by_id`):
     ```python
     return next((w for w in self.waypoints if w.waypoint_id == waypoint_id), None)
     ```
   *Impact:* Every single lookup runs an $O(N)$ scan over all zones, gates, or waypoints in the stadium model.

2. **Linear Scans and Redundant Allocations in Simulator Hot Loop (`backend/app/simulator/engine.py`):**
   - Lines 229, 238, 248 (`_update_gates`):
     ```python
     served = self.model.gate_by_id(gid)
     ```
     This is called inside the loop `for gid, gs in self._gates.items():`. This leads to $O(G^2)$ complexity on every simulation tick.
   - Lines 232, 241, 251 (`_update_gates`):
     ```python
     zs = [self._crowd[z] for z in served.served_zone_ids if z in self._crowd]
     dense = sum(z.density for z in zs) / len(zs) if zs else 0.0
     ```
     This allocates a new list `zs` of `CrowdDensity` objects on every tick for every gate, resulting in garbage collection churn.

3. **Linear Scans in State Models (`backend/app/models/state.py`):**
   - Lines 119-119 (`crowd_by_zone`):
     ```python
     return next((c for c in self.crowd if c.zone_id == zone_id), None)
     ```
     *Impact:* Scans the snapshot's crowd list in $O(Z)$ time.

4. **Linear Scans in Tool Handlers (`backend/app/tools/handlers.py`):**
   - Line 113 (`get_gate_status`):
     ```python
     gs = next((g for g in snap.gates if g.gate_id == gate_id), None)
     ```
     *Impact:* Scans the snapshot's gates list in $O(G)$ time.
   - Line 229 (`recommend_action`):
     ```python
     names = [ctx.model.zone_by_id(c.zone_id).name for c in high_zones if ctx.model.zone_by_id(c.zone_id)]
     ```
     *Impact:* Evaluates `ctx.model.zone_by_id(c.zone_id)` twice for each high crowd zone, causing redundant $O(Z)$ scans.

---

## 2. Logic Chain
- **Step 1:** The `StadiumModel` represents a static venue topology loaded once from fixtures and never modified. Therefore, it is safe to pre-index the lists (`self.zones`, `self.gates`, `self.waypoints`) into dictionaries mapping IDs to objects. Using Pydantic's `PrivateAttr` and `model_post_init` hook (standard in Pydantic v2) ensures these maps are populated once upon model instantiation.
- **Step 2:** Doing so reduces `zone_by_id`, `gate_by_id`, and `waypoint_by_id` lookups from $O(N)$ linear scans to $O(1)$ dictionary lookups.
- **Step 3:** The `StadiumSimulator._update_gates` loop evaluates `self.model.gate_by_id(gid)` for every gate. With the optimized lookup, this loop falls from $O(G^2)$ to $O(G)$ time.
- **Step 4:** The list comprehension `zs = [...]` inside `_update_gates` only exists to compute the average density of the served zones. By iterating directly over `served.served_zone_ids` and looking up crowd density from `self._crowd` (which is a dictionary), we can accumulate the sum and count in local variables. This avoids list allocations on every tick.
- **Step 5:** `StadiumSnapshot` is a point-in-time view generated on demand. By adding `_crowd_by_zone` and `_gates_by_id` private dictionaries populated during its `model_post_init`, we optimize `crowd_by_zone` and gate status lookups to $O(1)$ for tool handlers.

---

## 3. Caveats
- **State Mutability:** If the stadium layout was dynamic, pre-indexing at initialization could go out of sync. However, the stadium model is entirely static.
- **Concurrent Execution:** The simulator steps asynchronously under a background asyncio task. It is critical that `snapshot()` creates copies (using `model_copy()`) to freeze the values. Returning direct references to simulator state objects would result in race conditions. Thus, copying must be preserved.

---

## 4. Conclusion
We recommend implementing pre-indexed lookup caches inside Pydantic models using `PrivateAttr` and `model_post_init`, and refactoring the gate update loop to compute average densities without list allocations.

The proposed modifications are packaged in a diff patch file:
`.agents/explorer_opt_2/optimization.patch`

### Key Code Optimization Snippets:

#### 1. Pre-indexing in `StadiumModel` (`backend/app/models/stadium.py`):
```python
from typing import Any
from pydantic import BaseModel, Field, PrivateAttr

class StadiumModel(BaseModel):
    # ... other fields ...
    _zones_by_id: dict[str, Zone] = PrivateAttr(default_factory=dict)
    _gates_by_id: dict[str, Gate] = PrivateAttr(default_factory=dict)
    _waypoints_by_id: dict[str, Waypoint] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._zones_by_id = {z.zone_id: z for z in self.zones}
        self._gates_by_id = {g.gate_id: g for g in self.gates}
        self._waypoints_by_id = {w.waypoint_id: w for w in self.waypoints}

    def zone_by_id(self, zone_id: str) -> Zone | None:
        return self._zones_by_id.get(zone_id)

    def gate_by_id(self, gate_id: str) -> Gate | None:
        return self._gates_by_id.get(gate_id)

    def waypoint_by_id(self, waypoint_id: str) -> Waypoint | None:
        return self._waypoints_by_id.get(waypoint_id)
```

#### 2. Pre-indexing in `StadiumSnapshot` (`backend/app/models/state.py`):
```python
from typing import Any
from pydantic import BaseModel, Field, PrivateAttr

class StadiumSnapshot(BaseModel):
    # ... other fields ...
    _crowd_by_zone: dict[str, CrowdDensity] = PrivateAttr(default_factory=dict)
    _gates_by_id: dict[str, GateStatus] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._crowd_by_zone = {c.zone_id: c for c in self.crowd}
        self._gates_by_id = {g.gate_id: g for g in self.gates}

    def crowd_by_zone(self, zone_id: str) -> CrowdDensity | None:
        return self._crowd_by_zone.get(zone_id)

    def gate_by_id(self, gate_id: str) -> GateStatus | None:
        return self._gates_by_id.get(gate_id)
```

#### 3. Refactored Gate Updates (`backend/app/simulator/engine.py`):
```python
    def _update_gates(self, phase: MatchPhase) -> None:
        base = {
            MatchPhase.PRE_OPEN: 0,
            MatchPhase.ARRIVAL: 220,
            MatchPhase.PRE_KICKOFF: 320,
            MatchPhase.LIVE: 20,
            MatchPhase.HALFTIME: 40,
            MatchPhase.FULL_TIME: 300,
            MatchPhase.POST_EVENT: 60,
        }.get(phase, 0)
        
        for gid, gs in self._gates.items():
            override = self._gate_overrides.get(gid)
            if override == "closed":
                gs.status = "closed"
                gs.throughput_per_min = 0
                gs.queue_minutes = 99.0
                continue

            if override == "restricted":
                base_tp = base // 2
                tp = max(0, int(base_tp + self._rng.gauss(0, base_tp * 0.1))) if base_tp else 0
            else:
                tp = max(0, int(base + self._rng.gauss(0, base * 0.1))) if base else 0
            
            gs.throughput_per_min = tp
            
            served = self.model.gate_by_id(gid)
            dense = 0.0
            if served:
                total_density = 0.0
                count = 0
                for z in served.served_zone_ids:
                    cd = self._crowd.get(z)
                    if cd:
                        total_density += cd.density
                        count += 1
                dense = total_density / count if count > 0 else 0.0

            if override == "restricted":
                gs.status = "restricted"
                gs.queue_minutes = max(15.0, tp / 60.0 + dense * 12.0)
            elif override == "open":
                gs.status = "open"
                gs.queue_minutes = min(12.0, max(0.0, tp / 60.0 + dense * 6.0))
            else:
                gs.queue_minutes = max(0.0, tp / 60.0 + dense * 6.0)
                gs.status = "restricted" if gs.queue_minutes > 12 else "open"
```

---

## 5. Verification Method
- **Run the backend test suite:**
  Run `python -m pytest` from the `backend/` directory to verify that the simulator's logic and other modules operate correctly and regression-free. All 163 existing tests must pass.
  ```powershell
  cd backend
  python -m pytest
  ```
- **Run verification script:**
  A temporary unit test file (`tests/test_opt_proof.py`) was created and executed during investigation:
  - Subclassed the models with the optimized lookup logic.
  - Verified that all optimized dictionary-based lookups returned exact equality with original linear search output.
  - Re-implemented the optimized `_update_gates` calculations and verified it matches original output to 9 decimal places.
  - The script was executed successfully (`3 passed in 0.11s`) and subsequently removed to ensure clean repository layout compliance.
