# Project: SmartStadium AI

## Architecture
SmartStadium AI is a GenAI-enabled Smart Stadium & Tournament Operations ecosystem featuring:
- **Backend (FastAPI)**:
  - Uvicorn server running FastAPI app.
  - Telemetry Simulator: Async background engine simulating 80,000+ fans, generating real-time metrics for crowd density, gate queues, concession waits, and active security incidents.
  - GenAI Concierge Agent: Wraps the Gemini API using the `google-genai` SDK (with offline fallback client) and supports role-based server-side tool execution guards for `fan`, `volunteer`, and `organizer`. Includes prompt injection filtering and context-based vector search (TF-IDF fallback).
  - Navigation routing: Dijkstra-based shortest-path indoor routing service.
- **Frontend (React + TypeScript + Vite)**:
  - Real-time Operations Dashboard: Visualizes stadium zones (North Gate, Concourse A, East VIP, South Exits), alert notifications when capacity exceeds 85%, and staff dispatch panel.
  - Fan Portal: User chat interface with multi-language selector and wayfinding route visualization.
  - Scenario Injection panel: Interacts with the backend to trigger spikes ("Gate 2 Turnstile Malfunction", "Medical Emergency at Section 104", "Half-Time Concession Surge").

## Code Layout
- `backend/app/main.py`: App lifespan, background simulator, and initialization.
- `backend/app/core/config.py`, `gemini.py`: Configuration and GenAI client.
- `backend/app/models/`: `stadium.py` (data structures), `state.py`, `chat.py` (API structures), `roles.py` (tool permissions).
- `backend/app/simulator/engine.py`, `fixtures.py`: Simulator tick loop and match phases.
- `backend/app/knowledge/store.py`, `docs.py`: TF-IDF/embeddings store and FAQ knowledge base.
- `backend/app/tools/handlers.py`, `registry.py`: Wayfinding routing, state retrieval, and incident resolving.
- `backend/app/agent/prompt.py`, `loop.py`: Prompt assembly, security guards, and reasoning loop.
- `backend/app/api/routes.py`: FastAPI endpoints.
- `frontend/src/App.tsx`, `api.ts`, `types.ts`: Main frontend entry and state polling.
- `frontend/src/components/`: UI components (`OpsDashboard.tsx`, `ChatPanel.tsx`, `RoleSwitcher.tsx`).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Python Refactoring | Refactor `backend/app/` for docstrings, type hints, duplicate imports, and clean exceptions | None | DONE |
| M2 | Frontend TypeScript & Accessibility | Refactor `frontend/src/` for explicit interfaces, WCAG ARIA labels, unhandled promises, no `any` | None | DONE |
| M3 | E2E Integration & Integrity Auditing | Run full regression tests (pytest + vitest + build) and run Forensic Auditor for clean verification | M1, M2 | DONE |
| M11 | Backend Computational Speedup & Caching | Implement caching for Dijkstra paths and keyword search | None | DONE |
| M12 | Simulator Engine & State Optimization | Optimize simulator step/snapshot loops with fast lookups | M11 | DONE |
| M13 | Frontend Render & Bundle Optimization | Memoize React components and configure Vite chunking | M12 | DONE |
| M14 | Regression & Forensic Audit | Run E2E suites and forensic auditor to verify optimization | M11, M12, M13 | DONE |
| M15 | E2E Concurrency & Stress Testing | Audit, enhance thread-safety, fix cache bypass, and implement concurrent scenario stress tests | M14 | DONE |

## Interface Contracts
### API Endpoints
- `GET /api/health`: Return server health status.
- `GET /api/state`: Return complete live stadium state (zones, queue times, incidents, current simulation phase).
- `POST /api/role`: Switch active agent/user role.
- `POST /api/chat`: Send prompt, execute agent loop, return text response and tool-call audit.
- `POST /api/simulator/scenario`: Inject incident (e.g. `gate_malfunction`, `medical_emergency`, `concession_surge`).
