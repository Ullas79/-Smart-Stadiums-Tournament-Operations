# Scope: Accessibility, Inclusive Design, and WCAG Compliance Pass

## Architecture
- React + TypeScript frontend (components: `OpsDashboard.tsx`, `ChatPanel.tsx`, `RoleSwitcher.tsx`, `ScenarioPanel.tsx`, etc., styling: `index.css`).
- FastAPI backend (wayfinding: `backend/app/tools/handlers.py`, GenAI prompts: `backend/app/agent/prompt.py`).
- Automated tests: python `pytest` for backend, `vitest`/`npm test` for frontend components.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Analysis | Audit frontend components, styles, and backend wayfinding/prompt files for accessibility compliance gaps. | none | DONE |
| 2 | Frontend WCAG Hardening | Refactor React components (`OpsDashboard`, `ChatPanel`, etc.) to enforce ARIA landmarks, semantic tags, keyboard focus visible, and WCAG 4.5:1 contrast. | M1 | IN_PROGRESS |
| 3 | Backend Wayfinding & AI | Implement `accessible_only=True` in `find_route` tool and add screen-reader guidelines to GenAI prompts. | M1 | IN_PROGRESS |
| 4 | Verification & Audit | Execute all regression tests, verify frontend builds, run Challenger validations, and pass Forensic Auditor. | M2, M3 | PLANNED |

## Interface Contracts
### Wayfinding API & `find_route`
- Function signature: `find_route(source: str, destination: str, accessible_only: bool = False, ...)`
- Logic: When `accessible_only=True`, prioritize/only use elevators and ramps, avoiding stairs and heavy bottleneck areas.
- Prompt constraints: `agent/prompt.py` must contain explicit guidelines for generating screen-reader friendly markdown (no ASCII art/diagrams or unlabeled tables).
