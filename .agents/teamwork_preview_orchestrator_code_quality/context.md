# Context and Technical Notes

## Current Activity
- Decomposing the tasks and planning Phase 1 execution.

## Initial Test Execution Status
- We need to run existing tests to see if everything builds and passes. Let's delegate this to a worker to run backend `pytest` and frontend tests/build to establish a baseline.

## Technical Notes
- **Pytest command**: `.venv\Scripts\python.exe -m pytest -v` (run from `backend/`)
- **Frontend test command**: `npm test` (run from `frontend/`)
- **Frontend build command**: `npm run build` (run from `frontend/`)
