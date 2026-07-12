# Progress Tracker

## Current Status
Last visited: 2026-07-11T11:40:00Z
- [x] Milestone 11: Backend Computational Speedup & Caching (DONE)
- [x] Milestone 12: Simulator Engine & State Optimization (DONE)
- [x] Milestone 13: Frontend Render & Bundle Optimization (DONE)
- [x] Milestone 14: Regression & Forensic Audit (DONE - Verdict: CLEAN)

## Iteration Status
Current iteration: 1 / 32

## Retrospective Notes
- **What worked**: Splitting the performance optimizations into distinct analytical domains (Dijkstra/knowledge caching, telemetry/simulator speedup, React rendering, and Vite rollup chunking) allowed specialized exploration. Applying these changes with a single worker kept the backend and frontend changes coordinated.
- **What didn't**: The global route cache uses `id(ctx.model)` which is susceptible to ABA memory allocation recycle hazards if the stadium model is replaced in memory. Since stadium models are static singletons, this risk is mitigated, but placing the cache inside `StadiumModel` is preferred for future flexibility.
- **Lessons learned**: Pre-indexing arrays into dictionaries inside `model_post_init` hooks dramatically reduces traversal complexity from $O(N)$ linear scans to $O(1)$ constant-time lookup. In React polling dashboards, using a deep stringification equality check on the fetched snapshot in `setSnapshot` effectively bails out rendering cascades when data remains unchanged.
