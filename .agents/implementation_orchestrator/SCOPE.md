# Scope: Implementation Track

## Architecture
SmartStadium AI is a GenAI-enabled Smart Stadium & Tournament Operations ecosystem featuring:
- **Backend (FastAPI)**:
  - Uvicorn server running FastAPI app.
  - Telemetry Simulator: Async background engine simulating 80,000+ fans, generating real-time metrics.
  - GenAI Concierge Agent: Wraps the Gemini API using `google-genai` SDK with offline fallback.
  - Navigation routing: Dijkstra-based shortest-path indoor routing.
- **Frontend (React + TypeScript + Vite)**:
  - Real-time Operations Dashboard.
  - Fan Portal: User chat interface with multi-language selector.
  - Scenario Injection panel.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M2 | Telemetry & Simulation Verification | Verify telemetry simulator runs <=2s, scenario injection handles Gate 2 Malfunction, Medical Emergency, Half-Time Surge | None | DONE |
| M3 | Control Room & Crowd Management | Verify dashboard rendering of 4 zones, bottleneck alerts at >85%, volunteer dispatch controls | None | PLANNED |
| M4 | Fan Concierge & Wayfinding | Verify multi-language assistant (4 languages: EN, ES, FR, AR) and wayfinding route visualization | None | PLANNED |
| M5 | Security, Accessibility & Quality | Verify prompt injection guards, input sanitization, WCAG contrast compliance, responsive layouts | None | PLANNED |
| M6 | E2E Integration & Hardening | Phase 1: Pass 100% E2E test suite (Tiers 1-4); Phase 2: Adversarial coverage hardening (Tier 5) | M2, M3, M4, M5 | PLANNED |

## Interface Contracts
### API Endpoints
- `GET /api/health`: Return server health status.
- `GET /api/state`: Return complete live stadium state (zones, queue times, incidents, current simulation phase).
- `POST /api/role`: Switch active agent/user role.
- `POST /api/chat`: Send prompt, execute agent loop, return text response and tool-call audit.
- `POST /api/simulator/scenario`: Inject incident (`gate_malfunction`, `medical_emergency`, `concession_surge`).

### Code Layout
- `backend/app/main.py`: App lifespan, background simulator, and initialization.
- `backend/app/core/config.py`, `gemini.py`: Configuration and GenAI client.
- `backend/app/models/stadium.py`, `state.py`, `chat.py`, `roles.py`.
- `backend/app/simulator/engine.py`, `fixtures.py`.
- `backend/app/knowledge/store.py`, `docs.py`.
- `backend/app/tools/handlers.py`, `registry.py`.
- `backend/app/agent/prompt.py`, `loop.py`.
- `backend/app/api/routes.py`.
- `frontend/src/App.tsx`, `api.ts`, `types.ts`.
- `frontend/src/components/RoleSwitcher.tsx`, `ChatPanel.tsx`, `OpsDashboard.tsx`.
