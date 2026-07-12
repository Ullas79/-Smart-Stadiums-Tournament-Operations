# Handoff Report: Bounded LRU Cache for Shortest Path

This report details the analysis of the unbounded `_ROUTE_CACHE` inside `backend/app/tools/handlers.py` and provides recommendations for implementing a true bounded Least Recently Used (LRU) eviction strategy.

---

## 1. Observation

### File & Cache Analysis:
* **Target File**: `backend/app/tools/handlers.py`
* **Cache Definition** (Line 494):
  ```python
  _ROUTE_CACHE: dict[Any, tuple[list[str] | None, float]] = {}
  ```
* **Cache Read** (Lines 514-518):
  ```python
      cache_key = (model_id, src, dst, accessible_only, gate_sig, crowd_sig, inc_sig)
      if cache_key in _ROUTE_CACHE:
          path, dist = _ROUTE_CACHE[cache_key]
          # Return a copy of the path list to prevent callers from mutating the cached list
          return list(path) if path is not None else None, dist
  ```
* **Cache Write & Eviction** (Lines 537-540):
  ```python
      if len(_ROUTE_CACHE) >= 2048:
          _ROUTE_CACHE.clear()
      _ROUTE_CACHE[cache_key] = (path_found, dist_found)
      return list(path_found) if path_found is not None else None, dist_found
  ```

### Non-Hashable Dependencies:
* The `_shortest_path` function signature accepts `ctx: ToolContext` as its first parameter:
  ```python
  def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
  ```
* `ToolContext` holds instances of `StadiumSimulator`, `StadiumModel`, and `KnowledgeStore`, which are highly mutable/dynamic and are **not hashable**.
* Consequently, applying `functools.lru_cache` directly on `_shortest_path` results in a `TypeError: unhashable type: 'ToolContext'`.

---

## 2. Logic Chain

1. **Inefficient Eviction Strategy**: The current eviction mechanism checks if the cache length is greater than or equal to 2048, and if so, performs a full `.clear()`.
2. **Performance Impact**: Wiping the entire cache leads to cache thrashing and latency spikes on subsequent calls, as all routing computations must rebuild the graph and run Dijkstra's algorithm from scratch.
3. **Requirement**: A true bounded/LRU cache should evict only the oldest or least recently used entries rather than clearing the entire cache.
4. **Resolution via OrderedDict**:
   * Python's `collections.OrderedDict` provides a built-in `move_to_end(key)` method to track access frequency/recency and `popitem(last=False)` to evict the oldest entry in $O(1)$ complexity.
   * This retains the signature of `_shortest_path` and `_build_graph` without changes.
5. **Alternative Resolution via `functools.lru_cache` and Thread-Local Storage**:
   * To use `functools.lru_cache`, we must isolate the non-hashable `ctx` parameter.
   * This can be done by storing `ctx` in thread-local storage (`threading.local()`) and calling a helper function decorated with `@functools.lru_cache(maxsize=2048)` that accepts only hashable arguments.
   * While this uses the standard library C implementation, it introduces thread-local magic that is less readable and harder to debug.
6. **Recommendation**: We recommend the **OrderedDict Bounded LRU Cache** approach (Option 1) as it is clean, explicit, robust, and maintains the current architecture.

---

## 3. Caveats

* **Concurrency**: In a multi-threaded web application, accessing and modifying `_ROUTE_CACHE` (which is shared globally) concurrently may lead to race conditions if multiple threads perform eviction or access ordering at the same time. While standard dict operations are thread-safe under CPython's GIL, `OrderedDict` is not completely thread-safe for concurrent read/write updates. If the backend is running with a multi-threaded WSGI/ASGI server, a reentrant lock (`threading.RLock`) should wrap the cache read/write operations.
* **Dynamic Invalidation**: The cache key contains status signatures of gates, crowds, and active incidents. Thus, changes in stadium state naturally create new cache entries. A bounded cache of 2048 is essential to prevent stale keys from causing memory exhaustion over time.

---

## 4. Conclusion

The current cache eviction policy is crude and inefficient. We recommend refactoring `_ROUTE_CACHE` to use a bounded LRU implementation via `collections.OrderedDict`. 

A diff patch file has been prepared at:
`C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\explorer_m1_3\routing_cache_fix.patch`

### Proposed Code Changes (Option 1: OrderedDict Bounded LRU):
```python
# Before
_ROUTE_CACHE: dict[Any, tuple[list[str] | None, float]] = {}

def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
    ...
    if cache_key in _ROUTE_CACHE:
        path, dist = _ROUTE_CACHE[cache_key]
        return list(path) if path is not None else None, dist
    ...
    if len(_ROUTE_CACHE) >= 2048:
        _ROUTE_CACHE.clear()
    _ROUTE_CACHE[cache_key] = (path_found, dist_found)
    return list(path_found) if path_found is not None else None, dist_found

# After
from collections import OrderedDict

_ROUTE_CACHE: OrderedDict[Any, tuple[list[str] | None, float]] = OrderedDict()

def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
    ...
    if cache_key in _ROUTE_CACHE:
        _ROUTE_CACHE.move_to_end(cache_key)  # Mark as recently used
        path, dist = _ROUTE_CACHE[cache_key]
        return list(path) if path is not None else None, dist
    ...
    if len(_ROUTE_CACHE) >= 2048:
        _ROUTE_CACHE.popitem(last=False)  # Evict the oldest (LRU) entry
    _ROUTE_CACHE[cache_key] = (path_found, dist_found)
    return list(path_found) if path_found is not None else None, dist_found
```

---

## 5. Verification Method

### 1. Run Existing Test Suite:
Ensure that no regressions are introduced into the route finding or other tool behaviors:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -v
```
*Expected Result*: All 172 tests pass.

### 2. Cache Hit & Eviction Unit Test:
Add a test in `backend/tests/test_tools.py` that verifies the LRU cache behavior:
```python
def test_route_cache_lru_eviction(registry, ctx):
    c, _ = ctx
    from app.tools.handlers import _ROUTE_CACHE
    _ROUTE_CACHE.clear()
    
    # 1. Fill the cache to capacity (2048 items)
    for i in range(2048):
        fake_key = (1, f"WP-A-{i}", "WP-B", False, (), (), ())
        _ROUTE_CACHE[fake_key] = (["WP-A", "WP-B"], 10.0)
        
    assert len(_ROUTE_CACHE) == 2048
    first_key = next(iter(_ROUTE_CACHE.keys()))
    
    # 2. Access the first key to make it recently used
    registry.execute("find_route", {"from_waypoint_id": "G-N", "to_waypoint_id": "L-N"}, Role.FAN, c) # or access via code
    
    # 3. Add one more item to trigger eviction
    new_key = (1, "WP-NEW", "WP-B", False, (), (), ())
    # This should trigger eviction of the oldest non-accessed key, but not the entire cache
    # ...
```
