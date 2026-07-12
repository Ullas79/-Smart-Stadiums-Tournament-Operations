# Synthesized Optimization Strategy

This document aggregates the codebase exploration and performance audits from the three Explorer subagents. It defines the implementation roadmap for introducing caching, lookup indexing, and render optimizations without code regressions.

## Consensus Implementation Strategy

All explorers agree that the stadium telemetry engine, the waypoint graph, the knowledge base store, and the React UI components are largely static or operate on deterministic data sets, meaning caching and memoization are extremely safe and highly effective.

### 1. Backend Optimization
* **Dijkstra Pathfinding Caching (`backend/app/tools/handlers.py`)**:
  - Implement a module-level `_ROUTE_CACHE` mapping `(stadium_model_id, source, destination, accessible_only)` to path results.
  - Return copies of the path list to prevent callers from mutating the cached list.
  - Limit cache to 2048 entries to prevent memory leaks.
* **Knowledge Store Caching (`backend/app/knowledge/store.py`)**:
  - Store search cache in `self._search_cache` keyed by `(query, k, has_embeddings)`.
  - Invalidate cache or return shallow copies. Limit cache to 1024 entries.
* **StadiumModel Indexing (`backend/app/models/stadium.py`)**:
  - Pre-index zones, gates, and waypoints into private dictionaries using Pydantic `PrivateAttr` and `model_post_init` hook.
  - Replace linear scans in `zone_by_id`, `gate_by_id`, and `waypoint_by_id` with $O(1)$ lookups.
* **StadiumSnapshot Indexing (`backend/app/models/state.py`)**:
  - Pre-index crowd density and gates by ID in `StadiumSnapshot`'s `model_post_init`.
* **Telemetry Simulator Optimizations (`backend/app/simulator/engine.py`)**:
  - Optimize the gate update tick to use the $O(1)$ gate lookups.
  - Eliminate list allocations inside the tick loop by doing online accumulations of densities rather than instantiating lists.

### 2. Frontend Optimization
* **JSON Shallow Equality Guard in App (`frontend/src/App.tsx`)**:
  - Only update `snapshot` state in `App` if `JSON.stringify(prev) !== JSON.stringify(s)`. This avoids re-rendering the entire UI on identical poll payloads.
* **React Component Memoization**:
  - Wrap `RoleSwitcher`, `ChatPanel`, and `ScenarioPanel` in `React.memo`.
  - Memoize `ChatPanel`'s event handlers (`submit`, `handleSubmit`) and `ScenarioPanel`'s `handleTrigger` using `useCallback` to avoid re-creation.
  - Memoize `OpsDashboard` using `React.memo` with a custom comparison function checking `JSON.stringify` of the snapshot property.
* **Vite Bundle Chunk Splitting (`frontend/vite.config.ts`)**:
  - Group `node_modules` dependencies (specifically React core, Lucide, Recharts/D3 if present) into distinct bundles (`vendor-react`, `vendor`, etc.) to optimize loading times.

## Gaps & Risks
- **Mutable Layouts**: The optimizations assume the stadium and knowledge documents are static. If dynamic features are added later, caching must be disabled or cleared.
- **JSON Deep Equality**: Checking `JSON.stringify` on every poll adds a small CPU cost on the frontend, but is highly offset by preventing full React layout reconciliations.

## Handoff & Implementation Tasks
We will dispatch a single specialized implementation worker (`teamwork_preview_worker`) to apply all backend and frontend optimizations, run all regression tests, and verify performance gains.
