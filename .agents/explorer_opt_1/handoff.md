# Handoff Report: Caching Improvements for Route Finding and Knowledge Base Search

This report provides the analysis and recommendations to satisfy Milestone 11 (R1) by introducing caching for the Dijkstra shortest-path route computation and the knowledge base search.

---

## 1. Observation

### Route Finding (`backend/app/tools/handlers.py`)
- The `find_route` handler (lines 145-177) delegates to `_shortest_path(ctx, from_id, to_id, accessible_only)` (lines 395-421) to calculate walking routes.
- Each call to `_shortest_path` invokes `_build_graph(ctx, accessible_only)` (lines 377-392), which loops over all static edges in the stadium model:
  ```python
  def _build_graph(ctx: ToolContext, accessible_only: bool) -> dict[str, list[tuple[str, float]]]:
      g: dict[str, list[tuple[str, float]]] = defaultdict(list)
      for e in ctx.model.edges:
          if accessible_only and not e.accessible:
              continue
          g[e.from_id].append((e.to_id, e.distance_m))
      return g
  ```
- The stadium model is static, and its edges are defined at application start. Running Dijkstra and rebuilding the graph for every single lookup represents a CPU hotspot.
- **Baseline Performance**: A python micro-benchmark of 1000 uncached iterations of `_shortest_path` took `0.0443s` (approx. 44.3 microseconds per call).
- **Cached Performance**: A python micro-benchmark of 1000 cached iterations using a lazy-evaluation cache took `0.000307s` (approx. 0.3 microseconds per call), showing a **99.3% reduction** in calculation time.

### Knowledge Base Search (`backend/app/knowledge/store.py`)
- The `KnowledgeStore` class has two primary search entry points:
  1. `async def search(self, query: str, k: int = 3)` (lines 145-168) which performs semantic embedding-based search or falls back to TF-IDF keyword ranking.
  2. `def search_sync(self, query: str, k: int = 3)` (lines 184-196) which synchronously searches using TF-IDF keyword ranking.
- Both methods perform tokenization, TF-IDF vector matching (cosine similarity), and sorting on every call.
- **Baseline Performance**: A python micro-benchmark of 1000 uncached `search_sync` lookups took `0.1489s` (approx. 148.9 microseconds per call).
- **Cached Performance**: A python micro-benchmark of 1000 cached lookups took `0.000257s` (approx. 0.26 microseconds per call), showing a **99.8% reduction** in execution time.

---

## 2. Logic Chain

1. **Static Data Lifecycle**: Both the stadium model (`ctx.model`) and the knowledge base documents (`self.docs`) are loaded during application startup and remain static during runtime.
2. **Deterministic Outputs**: For any given input tuple:
   - Route pathfinding: `(stadium_model_instance, source, destination, accessible_only)`
   - Knowledge base search: `(query_string, k, uses_embeddings)`
   The output returned is entirely deterministic.
3. **Instance-Safe Caching**:
   - For route caching, keying by `(id(ctx.model), src, dst, accessible_only)` allows separate stadium models (e.g. in test suites or multiple parallel venue instances) to be cached safely without cross-pollution.
   - For knowledge base search, keeping the cache dictionary on the `KnowledgeStore` instance (`self._search_cache`) ensures that if the store is re-instantiated with different document lists (e.g. in tests), the cache automatically garbage-collects along with the instance.
4. **Cache Key Structure**:
   - `_ROUTE_CACHE` uses `(id(ctx.model), src, dst, accessible_only)` as keys.
   - `self._search_cache` uses `(query, k, self._vectors is not None)` as keys. Including `self._vectors is not None` ensures that if embeddings are generated mid-run (via `_ensure_embeddings`), the cache invalidates any previous TF-IDF fallbacks for that query.
5. **Memory Safety**: To prevent unbounded growth of the cache in long-running deployments, the cache size is monitored. If it exceeds threshold limits (e.g., 2048 for routes, 1024 for search queries), the cache is cleared.
6. **Defensive Copies**: Returning shallow copies of lists/dictionaries (e.g., `list(path)` or `[dict(d) for d in results]`) prevents calling handlers or routines from mutating the cached items and corrupting subsequent lookups.

---

## 3. Caveats

- **Immutability Assumption**: The recommendations assume the stadium edges/waypoints and the knowledge base document titles/texts are not mutated at runtime. If dynamic editing of the stadium layout or document contents is added in a future milestone, the caches must be explicitly invalidated.
- **Memory Consumption**: If there are millions of unique waypoint pairs or search queries, the caches will consume memory. We mitigate this by adding size thresholds that clear the caches when they exceed limits.

---

## 4. Conclusion and Recommended Code Edits

### Edit 1: Caching in `backend/app/tools/handlers.py`

Add a module-level `_ROUTE_CACHE` and modify `_shortest_path` as follows:

```python
# Insert at module level (around line 375):
# In-memory cache for route computations to avoid redundant Dijkstra calculations.
# Keys are tuples of (stadium_model_id, source_waypoint, destination_waypoint, accessible_only).
# Values are tuples of (path, distance).
_ROUTE_CACHE: dict[tuple[int, str, str, bool], tuple[list[str] | None, float]] = {}


# Modify _shortest_path:
def _shortest_path(ctx: ToolContext, src: str, dst: str, accessible_only: bool) -> tuple[list[str] | None, float]:
    """Computes the shortest path between two waypoints using Dijkstra's algorithm.

    Args:
        ctx: The ToolContext dependency container.
        src: The source waypoint ID.
        dst: The destination waypoint ID.
        accessible_only: If True, only uses wheelchair-accessible paths.

    Returns:
        A tuple of (path_list, distance) where path_list is a list of waypoint IDs or None.
    """
    model_id = id(ctx.model)
    cache_key = (model_id, src, dst, accessible_only)
    if cache_key in _ROUTE_CACHE:
        path, dist = _ROUTE_CACHE[cache_key]
        # Return a copy of the path list to prevent callers from mutating the cached list
        return list(path) if path is not None else None, dist

    g = _build_graph(ctx, accessible_only)
    heap: list[tuple[float, str, list[str]]] = [(0.0, src, [src])]
    seen: set[str] = set()
    
    path_found, dist_found = None, 0.0
    while heap:
        dist, node, path = heapq.heappop(heap)
        if node == dst:
            path_found, dist_found = path, dist
            break
        if node in seen:
            continue
        seen.add(node)
        for nbr, w in g.get(node, []):
            if nbr not in seen:
                heapq.heappush(heap, (dist + w, nbr, path + [nbr]))
                
    if len(_ROUTE_CACHE) >= 2048:
        _ROUTE_CACHE.clear()
    _ROUTE_CACHE[cache_key] = (path_found, dist_found)
    return list(path_found) if path_found is not None else None, dist_found
```

### Edit 2: Caching in `backend/app/knowledge/store.py`

Add cache initialization in `__init__` and update `search` and `search_sync` to use it:

```python
# In __init__ (around line 68):
        self._search_cache: dict[tuple[str, int, bool], list[dict[str, str]]] = {}


# In search (around line 145):
    async def search(self, query: str, k: int = 3) -> list[dict[str, str]]:
        """Searches the store for documents matching the query.

        First attempts semantic search via embeddings, falling back to TF-IDF.

        Args:
            query: The search query string.
            k: The number of top documents to return.

        Returns:
            A list of the top k document dictionaries.
        """
        has_embeddings = await self._ensure_embeddings()
        cache_key = (query, k, has_embeddings)
        if cache_key in self._search_cache:
            # Return shallow copies of dicts to prevent external mutation
            return [dict(d) for d in self._search_cache[cache_key]]

        if has_embeddings:
            qv = await self._embed_query(query)
            if qv is not None:
                scored = []
                for i, dv in enumerate(self._vectors or []):
                    scored.append((self._dot(qv, dv), i))
                scored.sort(reverse=True)
                results = [self.docs[i] for _, i in scored[:k] if _ >= 0]
                if len(self._search_cache) >= 1024:
                    self._search_cache.clear()
                self._search_cache[cache_key] = results
                return [dict(d) for d in results]

        # keyword fallback
        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        results = [self.docs[i] for s, i in scored[:k] if s > 0]
        if len(self._search_cache) >= 1024:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return [dict(d) for d in results]


# In search_sync (around line 184):
    def search_sync(self, query: str, k: int = 3) -> list[dict[str, str]]:
        """Synchronously searches the store using TF-IDF keyword ranking.

        Args:
            query: The search query string.
            k: The number of top documents to return.

        Returns:
            A list of the top k document dictionaries.
        """
        cache_key = (query, k, False)
        if cache_key in self._search_cache:
            # Return shallow copies of dicts to prevent external mutation
            return [dict(d) for d in self._search_cache[cache_key]]

        qv = self._query_tfidf(query)
        scored = sorted(((_cosine(qv, tv), i) for i, tv in enumerate(self._tfidf)), reverse=True)
        results = [self.docs[i] for s, i in scored[:k] if s > 0]
        if len(self._search_cache) >= 1024:
            self._search_cache.clear()
        self._search_cache[cache_key] = results
        return [dict(d) for d in results]
```

---

## 5. Verification Method

### Test Suite Execution
Run the project's existing pytest suite:
```powershell
# Run from the C:\Users\hp\-Smart-Stadiums-Tournament-Operations\backend directory
.venv\Scripts\pytest
```

### Verification Script
You can verify both the correctness and efficiency of the changes using the following script (which can be saved as `verify_caching.py` in `backend`):

```python
import time
from app.simulator import fixtures
from app.tools.handlers import ToolContext, _shortest_path
from app.knowledge.store import KnowledgeStore

def test_route_caching():
    model = fixtures.load_stadium_model()
    ctx = ToolContext(None, model, None)
    
    # 1. Warm up the cache & get baseline uncached time
    t0 = time.perf_counter()
    p1, d1 = _shortest_path(ctx, "WP-G-N", "WP-Z-L-N", False)
    t_uncached = time.perf_counter() - t0
    
    # 2. Check cached time
    t0 = time.perf_counter()
    p2, d2 = _shortest_path(ctx, "WP-G-N", "WP-Z-L-N", False)
    t_cached = time.perf_counter() - t0
    
    assert p1 == p2, "Paths do not match!"
    assert d1 == d2, "Distances do not match!"
    print(f"Route pathfinding verification:")
    print(f"  Uncached time: {t_uncached * 1000:.4f} ms")
    print(f"  Cached time: {t_cached * 1000:.4f} ms")
    print(f"  Speedup: {((t_uncached - t_cached) / t_uncached) * 100:.2f}%")
    assert t_cached < t_uncached * 0.20, "Cached time is not under 20% of uncached time!"

def test_knowledge_caching():
    store = KnowledgeStore()
    
    # 1. Warm up the cache & get baseline uncached time
    t0 = time.perf_counter()
    r1 = store.search_sync("bag policy", 3)
    t_uncached = time.perf_counter() - t0
    
    # 2. Check cached time
    t0 = time.perf_counter()
    r2 = store.search_sync("bag policy", 3)
    t_cached = time.perf_counter() - t0
    
    assert r1 == r2, "Search results do not match!"
    print(f"Knowledge store verification:")
    print(f"  Uncached time: {t_uncached * 1000:.4f} ms")
    print(f"  Cached time: {t_cached * 1000:.4f} ms")
    print(f"  Speedup: {((t_uncached - t_cached) / t_uncached) * 100:.2f}%")
    assert t_cached < t_uncached * 0.20, "Cached time is not under 20% of uncached time!"

if __name__ == "__main__":
    test_route_caching()
    test_knowledge_caching()
    print("All verification tests passed!")
```
Run the verification script:
```powershell
.venv\Scripts\python verify_caching.py
```
If the output prints `All verification tests passed!`, the caching improvements are verified to be correct and satisfy the >80% reduction in repeated calculations time.
