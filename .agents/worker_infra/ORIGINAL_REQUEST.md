## 2026-07-10T12:04:02Z
Create the file C:\Users\hp\-Smart-Stadiums-Tournament-Operations\TEST_INFRA.md with the following content.

# E2E Test Infra: SmartStadium AI

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| F1 | Control Room Dashboard | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| F2 | Bottleneck Alerts at 85% | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| F3 | Staff Dispatch Panel | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| F4 | Multi-Language Concierge | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| F5 | Wayfinding Indoor Navigation | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| F6 | Telemetry Simulator | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| F7 | Scenario Injection Panel | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Test runner**: `pytest`
- **Location**: Run command `cd backend && pytest tests/test_e2e_suite.py` (or similar)
- **Invocation**: Executes a comprehensive suite of at least 82 tests validating both successful API flows and edge/boundary conditions.
- **Test case format**: Python test cases using `fastapi.testclient.TestClient(app)` to send requests to FastAPI routes and assert expected response structures and simulation behavior.
- **Directory layout**:
  - `backend/tests/test_e2e_suite.py` will contain all the 82+ tests.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity | Description |
|---|----------|--------------------|------------|-------------|
| 1 | Standard Match Arrival | F1, F4, F5, F6 | Medium | Fan arrives, checks schedule, gets wayfinding path, checks crowds. |
| 2 | High Congestion Alert & Mitigation | F1, F2, F3, F6 | High | Zone exceeds 85% capacity, alerts trigger, organizer checks recommendations, dispatches staff. |
| 3 | Emergency Scenario Injection | F1, F3, F6, F7 | High | Inject incident via panel, verify state updates, check incident visibility, resolve incident. |
| 4 | Multilingual Volunteer Assistant | F1, F4, F5, F6 | Medium | Volunteer queries incidents in French/Spanish, navigates, checks gate queues. |
| 5 | End-to-End Stadium Operations | All Features | High | Comprehensive operations sequence from pre-match gates open to post-match exit. |

## Coverage Thresholds
- Tier 1: ≥5 per feature (35+ tests total)
- Tier 2: ≥5 per feature (35+ tests total)
- Tier 3: pairwise coverage of major feature interactions (7+ tests total)
- Tier 4: ≥5 realistic application scenarios (5+ tests total)
- Total E2E Tests: >= 82

## API Interface Contracts Under Test
1. `GET /health` -> Returns `{"status": "ok"}`
2. `GET /role` -> Returns allowed roles and tools metadata
3. `GET /state` -> Returns current stadium simulation snapshot
4. `POST /chat` -> Role-aware chat assistant query with history and tool-call details
5. `POST /api/simulator/scenario` -> Inject dynamic scenarios (`gate_malfunction`, `medical_emergency`, `concession_surge`)
6. `POST /api/incidents/dispatch` -> Dispatch volunteer/staff to active incident: `{"incident_id": str, "assigned_staff": str}`
7. `POST /api/incidents/resolve` -> Mark active incident as resolved: `{"incident_id": str}`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
