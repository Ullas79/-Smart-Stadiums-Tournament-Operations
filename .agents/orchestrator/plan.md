# Efficiency, Computational Speedup, and Latency Optimization Plan

This plan outlines the optimization enhancements required for the SmartStadium AI codebase to align with the follow-up request dated 2026-07-11T11:30:07Z.

## Milestones

### Milestone 11: Backend Computational Speedup & Caching (R1)
* **Objective**: Optimize Dijkstra shortest-path calculations and knowledge base keyword search by implementing intelligent caching.
* **Tasks**:
  1. Audit current pathfinding implementation in `backend/app/tools/handlers.py` and knowledge search in `backend/app/knowledge/store.py`.
  2. Implement an in-memory route lookup cache (e.g., using `functools.lru_cache` or a dictionary cache with TTL) for identical `(source, destination, accessible_only)` tuples.
  3. Implement caching for the top keyword/BM25 retrieval results in `KnowledgeStore.search()` using the query string as the key.
  4. Ensure cached entries maintain exact relevance scoring and don't introduce correctness issues.

### Milestone 12: Simulator Engine & State Optimization (R2)
* **Objective**: Optimize the MetLife Stadium telemetry tick loop to handle 80,000+ simulated fans without event loop blocking or memory leaks.
* **Tasks**:
  1. Audit `backend/app/simulator/engine.py` (`StadiumSimulator.step()` and `snapshot()`) and `backend/app/models/state.py` / `stadium.py`.
  2. Replace linear lists (`O(N)`) scanning with fast hash-map/dictionary lookup tables (`O(1)`) for zone densities and gate statuses.
  3. Reduce redundant object allocations and list comprehensions in the high-frequency tick loops.
  4. Prevent memory leaks and ensure simulator steps execute in sub-millisecond durations.

### Milestone 13: Frontend Render & Bundle Optimization (R3)
* **Objective**: Eliminate unnecessary React re-renders and reduce bundle loading times using memoization and chunk splitting.
* **Tasks**:
  1. Audit React component render behaviors in `frontend/src/components/OpsDashboard.tsx`, `ChatPanel.tsx`, and `ScenarioPanel.tsx`.
  2. Leverage `useMemo` and `useCallback` for expensive metric/chart calculations and handler dependencies.
  3. Configure Vite manual chunk splitting in `vite.config.ts` to separate large vendor packages and optimize bundle size.

### Milestone 14: E2E Verification & Forensic Audit
* **Objective**: Verify that 100% of tests pass cleanly, the production bundle completes without warnings, and the auditor reports clean.
* **Tasks**:
  1. Run backend tests (`pytest`).
  2. Run frontend tests (`npm test`).
  3. Verify frontend production build (`npm run build`) runs without warnings or TypeScript compiler errors.
  4. Run the Forensic Auditor (`teamwork_preview_auditor`) to ensure genuine implementation with zero hardcoding or cheating.
