# Accessibility Audit Report: Wayfinding & GenAI Instructions

This report details the findings and proposed solutions from the accessibility audit of the backend indoor wayfinding pathfinding engine and the GenAI assistant instructions for screen-reader compatibility.

---

## 1. Observation

During the read-only exploration of the codebase, the following patterns and details were observed:

### Wayfinding & Graph Pathfinding (`backend/app/tools/handlers.py`)

- **Accessibility Flag Parsing** (lines 156-158):
  ```python
  from_id = args.get("from_waypoint_id", "")
  to_id = args.get("to_waypoint_id", "")
  accessible_only = bool(args.get("accessible", False))
  ```
  The parameter parsed from tool arguments is `"accessible"`, whereas the system description and requirements refer to `"accessible_only"`.

- **Hard Graph Filtering** (lines 381-396):
  ```python
  def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:
      g: dict[str, list[tuple[str, float]]] = defaultdict(list)
      for e in ctx.model.edges:
          if accessible_only and not e.accessible:
              continue
          g[e.from_id].append((e.to_id, e.distance_m))
      return g
  ```
  If `accessible_only` is true, any edge where `accessible` is `False` is dropped entirely from the adjacency graph.

- **Edge Accessibility Definition** (`backend/app/models/stadium.py`, lines 120-139):
  ```python
  accessible=kind in (EdgeKind.ELEVATOR, EdgeKind.RAMP, EdgeKind.FLAT),
  ```
  Stairs (`EdgeKind.STAIRS`) and escalators (`EdgeKind.ESCALATOR`) are marked non-accessible.

- **Venue Connections to Seating Zones** (`backend/app/simulator/fixtures.py`, lines 185-197):
  ```python
  # Lower concourse -> seats
  for zid in ["L-N", "L-S", "L-E", "L-W"]:
      add(f"C-{zid}", f"Z-{zid}", EdgeKind.STAIRS, 30)
  
  # Vertical connectors: lower <-> club <-> upper (escalator + elevator)
  for side in ["N", "S", "E", "W"]:
      ...
      add(f"C-CL-{side}", f"Z-C-{side}", EdgeKind.STAIRS, 25)
      add(f"C-U-{side}", f"Z-U-{side}", EdgeKind.STAIRS, 25)
  ```
  The only connections from concourse waypoints (e.g., `WP-C-L-N`) to seating zone waypoints (e.g., `WP-Z-L-N`) are defined as `EdgeKind.STAIRS` (which are non-accessible).

- **Static Shortest Path Cache** (lines 399, 414-419):
  ```python
  _ROUTE_CACHE: dict[tuple[int, str, str, bool], tuple[list[str] | None, float]] = {}
  ...
  model_id = id(ctx.model)
  cache_key = (model_id, src, dst, accessible_only)
  if cache_key in _ROUTE_CACHE:
      path, dist = _ROUTE_CACHE[cache_key]
      return list(path) if path is not None else None, dist
  ```
  The shortest-path calculation caching key consists only of `model_id`, `src`, `dst`, and `accessible_only`. It does not account for any dynamic simulator attributes.

### GenAI System Prompt (`backend/app/agent/prompt.py`)

- **Assistant Instructions**:
  The current prompt `_BASE` (lines 15-40) specifies roles and basic capabilities but does not contain any formatting instructions or guidelines regarding output accessibility (such as screen-reader compatibility).

---

## 2. Logic Chain

From the observations above, the following logical steps lead to our conclusions:

1. **Routing to Seating Zones Fails Under Accessibility Checks**:
   - Every path from a gate or concourse to a seating zone (e.g., `WP-Z-L-N`) terminates with a concourse-to-seats edge.
   - In `fixtures.py`, every concourse-to-seats edge is defined with `EdgeKind.STAIRS`.
   - In `stadium.py`, `EdgeKind.STAIRS` maps to `accessible=False`.
   - In `handlers.py`, when `accessible_only=True` is passed, `_build_graph` excludes all non-accessible edges (`if accessible_only and not e.accessible: continue`).
   - Consequently, the graph constructed when `accessible_only=True` has no paths connecting the concourses to any seating zones. Dijkstra's search fails (`path is None`), returning a "No route found" error.
   - **Solution**: Replace the hard edge exclusion with a cost-based penalty (Dijkstra edge weighting). When `accessible_only=True`, add a large distance penalty (e.g., `+10,000` meters) to stairs and escalators. This instructs Dijkstra to strictly prefer elevators/ramps where they exist (e.g., for level transitions) but still allows stairs when they are the only physical way to reach the destination.

2. **Routing Does Not Avoid Live Bottlenecks**:
   - Edge weights are statically defined as `e.distance_m` (observation 2).
   - Dynamic telemetry in `StadiumSnapshot` (`state.py`) details crowd density by zone (`crowd`), gate status (`gates`), and active incidents (`incidents`).
   - The pathfinding algorithm does not inspect this telemetry to steer users away from restricted gates, crowded concourses, or zones with active emergencies.
   - **Solution**: Implement dynamic weight adjustments based on live telemetry:
     - Penalize edges connecting to high-density zones (occupancy/capacity >= 0.85).
     - Penalize edges connecting to gates marked as `"restricted"` or `"closed"`.
     - Penalize edges in zones containing active incidents (scale penalty by severity: low/medium/high).

3. **Routing Cache Serving Stale Routes**:
   - If dynamic penalties are applied to edge weights, the routing results will change as stadium conditions shift.
   - Because `_ROUTE_CACHE` uses only static parameters (observation 5), a route calculated during normal conditions would be served from the cache even after an incident blocks that path.
   - **Solution**: Include the current simulator time (`int(snap.match.sim_time)`) or another dynamic indicator in the cache key. This ensures the cache automatically invalidates when the simulation state changes.

4. **Risk of Screen-Reader Incompatible Outputs**:
   - LLMs natively tend to produce visual formatting, such as ASCII diagrams/arrows (e.g., `[Gate] ---> [Elevator]`) or markdown tables when requested to format schedules or paths.
   - Such layouts are parsed character-by-character by screen readers (e.g., reading out "bracket G hyphen N bracket equals equals equals equals..."), making them unintelligible.
   - **Solution**: Inject explicit instructions in `prompt.py` directing the model to output clean, screen-reader friendly markdown, enforcing linear bullet points, avoiding ASCII drawings/flowcharts, and providing textual summaries for tables.

---

## 3. Caveats

- **Static Model Limitations**: The actual physical architecture of the stadium is represented in memory via the fixtures in `fixtures.py`. We assume the existing set of waypoints and edges is complete, and we do not attempt to add new "accessible" edges to the stadium model, since we are a read-only exploration agent.
- **Dijkstra Weight Unit Scale**: Adding static distance penalties (e.g., `+10,000` meters for stairs) works because the venue distances are small (~25 to 60 meters). A `10,000` meter penalty ensures that any available elevator/ramp path (typically ~45 meters) will be heavily preferred.
- **Cache Hit Rate**: Incorporating `sim_time` directly in the cache key means cache hits will only occur if multiple route requests are made within the same simulator tick. Since ticks happen asynchronously, this is safe and prevents memory bloat while avoiding stale results.

---

## 4. Conclusion & Proposed Solutions

To establish WCAG-compliant wayfinding and screen-reader friendly output, the following modifications are proposed:

### Proposed Patch for `backend/app/tools/handlers.py`

Implement dynamic edge weighting that handles accessibility prioritization, bottleneck avoidance, and cache invalidation.

```python
# Proposed helper to map waypoint IDs to zone IDs for density/incident queries
def _waypoint_to_zone_id(wp_id: str) -> str | None:
    if wp_id.startswith("WP-Z-"):
        return wp_id[5:]  # e.g., WP-Z-L-N -> L-N
    elif wp_id.startswith("WP-C-"):
        concourse = wp_id[3:]  # e.g., C-L-N
        if concourse.startswith("C-L-"):
            return "L-" + concourse[-1]
        elif concourse.startswith("C-CL-"):
            return "C-" + concourse[-1]
        elif concourse.startswith("C-U-"):
            return "U-" + concourse[-1]
    return None

# Proposed update to find_route to accept both parameter variations
def find_route(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from_id = args.get("from_waypoint_id", "")
    to_id = args.get("to_waypoint_id", "")
    accessible_only = bool(args.get("accessible_only", args.get("accessible", False)))
    ...

# Proposed update to _build_graph implementing dynamic weights
def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:
    g: dict[str, list[tuple[str, float]]] = defaultdict(list)
    snap = ctx.snapshot()
    active_incidents = [i for i in snap.incidents if i.status == "active"]
    
    for e in ctx.model.edges:
        weight = e.distance_m
        
        # 1. Accessibility Penalty (Stairs/Escalators avoided, but not completely removed)
        if accessible_only:
            if not e.accessible:
                if e.kind.value == "stairs":
                    weight += 10000.0
                elif e.kind.value == "escalator":
                    weight += 20000.0  # Avoid escalators entirely for wheelchair users
        
        # 2. Dynamic Telemetry & Bottleneck Penalties
        for node in (e.from_id, e.to_id):
            # Zone density
            zone_id = _waypoint_to_zone_id(node)
            if zone_id:
                cd = snap.crowd_by_zone(zone_id)
                if cd:
                    if cd.density >= 0.85:
                        weight += 1500.0  # High density bottleneck
                    elif cd.density >= 0.50:
                        weight += 300.0   # Moderate congestion
            
            # Gate status
            if node.startswith("WP-G-"):
                gate_id = node[3:]
                gs = snap.gate_by_id(gate_id)
                if gs:
                    if gs.status == "restricted":
                        weight += 1500.0
                    elif gs.status == "closed":
                        weight += 99999.0  # Closed gate avoidance
            
            # Active Incidents
            for inc in active_incidents:
                target_zone = zone_id or (node[3:] if node.startswith("WP-G-") else None)
                if inc.zone_id == target_zone:
                    severity_map = {"low": 500.0, "medium": 1500.0, "high": 5000.0}
                    weight += severity_map.get(inc.severity.value, 1000.0)

        g[e.from_id].append((e.to_id, weight))
    return g

# Proposed update to _shortest_path cache key to include live sim_time
def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
    snap = ctx.snapshot()
    model_id = id(ctx.model)
    # Include sim_time to ensure cache invalidates when simulator advances state
    cache_key = (model_id, src, dst, accessible_only, int(snap.match.sim_time))
    ...
```

### Proposed Update for `backend/app/agent/prompt.py`

Append explicit accessibility and formatting instructions to the system prompt returned by `build_system_prompt`:

```python
_ACCESSIBILITY = """ACCESSIBILITY & SCREEN-READER OUTPUT GUIDELINES:
1. NEVER output ASCII art, visual flowcharts, character-based maps, or character diagrams (e.g., "[Gate] ---> [Concourse] ==[Elevator]==> [Seats]") to explain routes, navigation, or layouts. These are unintelligible to screen readers, which read them character-by-character.
2. Use clear, semantic, linear bulleted lists or step-by-step descriptions for routes (e.g., "Step 1: Go through North Gate. Step 2: Take the elevator to the Club Level...").
3. Avoid unlabeled tables or complex grid layouts. If you must present schedules or queues in tabular form, precede the table with a clear textual summary and ensure column headers are descriptive.
4. When wheelchair-accessible routing (using `accessible_only=True` or `accessible=True` in `find_route`) is requested, explicitly mention that the route is accessible and details elevator/ramp usage while skipping stairs and bottlenecks.
5. Avoid excessive punctuation (such as ">>>", "===>", "---") and non-standard layout separators.
"""

def build_system_prompt(role: Role, snapshot: StadiumSnapshot, language: str = "en") -> str:
    role_desc = ROLE_DESCRIPTIONS[role]
    return (
        f"{_BASE}\n\n"
        f"CURRENT USER ROLE: {role.value} — {role_desc}\n"
        f"You may only use the tools available to this role; attempts to use "
        f"unauthorized tools will be blocked.\n\n"
        f"LIVE STADIUM STATE:\n{snapshot.summary()}\n\n"
        f"USER LANGUAGE: {language}\n\n"
        f"{_INJECTION}\n\n"
        f"{_ACCESSIBILITY}"
    )
```

---

## 5. Verification Method

To verify these changes independently once implemented:

1. **Unit and Integration Tests**:
   - Run backend tests using `python -m pytest` inside `backend/` to confirm that all existing route calculations and agent tests still pass without regressions.
   - Add a new unit test in `backend/tests/test_tools.py` verifying that routing from `G-N` to `L-N` (seating zone) succeeds when `accessible=True` or `accessible_only=True` is requested, and that the calculated distance includes the penalty for using stairs (as stairs are the only way to reach the seating zones).
   
2. **Behavioral Invalidation Check**:
   - Trigger the `gate_malfunction` scenario using `/simulator/scenario` (sets `G-S` to restricted).
   - Call `find_route` from `G-S` to `L-S` and from `G-N` to `L-S`. Compare the path selected. The path should bypass `G-S` (due to the penalty) if any alternative gate path is cheaper.
   - Trigger a high-density concession surge on Club Level concourse and verify that routes from `G-W` to `C-E` route around the club level concourses or dense sectors where possible.

3. **GenAI Output Verification**:
   - Prompt the agent: *"How do I get from West Gate to Lower North seats? Provide step-by-step instructions. Also show me the match schedule."*
   - Verify that the response does not contain characters like `--->`, `===>`, ascii layouts, or unlabeled markdown tables. It should consist of clean semantic text, structured paragraphs, and list items.
