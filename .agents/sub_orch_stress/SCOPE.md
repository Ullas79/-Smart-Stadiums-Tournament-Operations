# Scope: E2E Stress Testing and Readiness Pass

## Architecture
- **Backend Simulator**: `StadiumSimulator` under `backend/app/simulator/engine.py` coordinates crowd movement and scenario alerts across gates and zones.
- **Pathfinding & Routing**: Dijkstra shortest path (`find_route`) caching and dynamic route penalty updates for bottleneck mitigation.
- **Incident Dispatch**: Organizers and staff volunteer assignment tracking.
- **Frontend App**: React component suite, vitest tests, and Vite build pipeline.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Explore Codebase & Tests | Investigate existing codebase, Dijkstra pathfinding caches, volunteer dispatch logic, concurrent scenario execution, and the current pytest/vitest tests. | none | DONE |
| 2 | Enhance Stress Testing (R1) | Design and implement/enhance backend automated stress tests for concurrent scenario injections under peak crowd densities (>85%) across all match phases (pre_match, first_half, halftime, second_half, post_match), ensuring Dijkstra pathfinding, volunteers dispatch, and route penalties update instantly without deadlocks or race conditions. | M1 | DONE |
| 3 | Regression Verification (R2) | Run and pass 100% of all 166+ pytest tests, vitest component tests, and clean production builds with zero TypeScript errors or warnings. | M2 | DONE |
| 4 | Documentation & Reports (R3) | Polish and update `PROJECT.md`, `TEST_INFRA.md`, and verify accuracy of audit reports under `.agents/` (`victory_auditor`, `security_auditor`, `accessibility_auditor`). | M3 | DONE |

## Interface Contracts
- Dynamic scenario inputs must update the simulator's status and trigger route penalty recalculations instantly.
- Volunteer dispatch status changes must reflect in subsequent telemetry snapshot updates.
