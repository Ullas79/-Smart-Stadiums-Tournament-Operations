# Scope: E2E Testing Track

## Architecture
The E2E test suite validates the integration of the FastAPI backend and the React/TS frontend. The test suite is designed as an opaque-box, requirement-driven suite. It interacts with the FastAPI REST API (either using `fastapi.testclient.TestClient` or over HTTP) to verify that all functional requirements are satisfied.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1.1 | Test Infrastructure Design | Create `TEST_INFRA.md` outlining the test runner, directory structure, and feature inventory | None | DONE |
| M1.2 | Tier 1 (Feature Coverage) Tests | Implement >=35 tests covering F1-F7 features (>=5 tests per feature) | M1.1 | IN_PROGRESS |
| M1.3 | Tier 2 (Boundary/Edge Cases) Tests | Implement >=35 tests covering edge/boundary behaviors of F1-F7 (>=5 tests per feature) | M1.2 | IN_PROGRESS |
| M1.4 | Tier 3 (Cross-Feature Combinations) | Implement >=7 tests covering pairwise interactions of features | M1.3 | IN_PROGRESS |
| M1.5 | Tier 4 (Real-World Workloads) | Implement >=5 tests covering complex end-to-end user workflows | M1.4 | IN_PROGRESS |
| M1.6 | Suite Verification & Publication | Run all tests, ensure they pass, and publish `TEST_READY.md` at the project root | M1.5 | PLANNED |

## Interface Contracts under Test
The E2E tests will exercise and assert the contracts of the following endpoints:
1. `GET /health` - Health status check.
2. `GET /role` - Returns role metadata and tool permissions.
3. `GET /state` - Returns live stadium snapshots (zones, gates, incidents, transit, match state).
4. `POST /chat` - Executes agentic turns and retrieves tool audits.
5. `POST /api/simulator/scenario` (or similar endpoint) - Triggers scenario injection.
6. `POST /api/incident/dispatch` (or similar endpoint) - Triggers volunteer/staff dispatch.

## Features under Test
- **F1: Control Room Dashboard**: Check zone densities, gates, transit, incident lists.
- **F2: Bottleneck Alerts at 85%**: Alerts triggered in `recommend_action` or dashboard when zones >= 85%.
- **F3: Staff Dispatch Panel**: Assigning volunteers to incidents and tracking incident resolution status.
- **F4: Multi-Language Concierge**: Multilingual chat query routing, translate tools, response in ES/FR/AR/PT/etc.
- **F5: Wayfinding Indoor Navigation**: Dijkstra-based shortest routing paths with elevator/ramp options.
- **F6: Telemetry Simulator**: Periodic ticking of time, phase progression, queue calculations.
- **F7: Scenario Injection Panel**: Spikes/incidents injection and simulator adjustment.
