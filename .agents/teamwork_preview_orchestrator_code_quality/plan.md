# Code Quality Improvement Plan - SmartStadium AI

## Architecture
- **Backend**: FastAPI web framework, Pydantic data schemas, asyncio stadium telemetry simulation, knowledge store retrieval.
- **Frontend**: React + Vite, TypeScript, Tailwind CSS styling, Vitest component test environment.

## Milestones
| Phase | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| Phase 1 | Critical Bug Fixes | Fix duplicate route decorators, shadowing in ToolRegistry, ChatPanel stale closures, unbounded route cache | None | PLANNED |
| Phase 2 | Security Hardening | X-Forwarded-For spoofing prevention, payload limit enforcement, prompt injection scanner improvements, simulator thread safety, tool input validations | Phase 1 | PLANNED |
| Phase 3 | Architecture & Type Safety | Standardize ToolResult type, async KnowledgeStore, React Error Boundaries, AbortController cancellation, circular imports resolution | Phase 2 | PLANNED |
| Phase 4 | Quality & Coverage | Magic number config extraction, CSS color consolidation, write pytest tests (KnowledgeStore, cache eviction, concurrency), accessibility assertions, strict typing (mypy) | Phase 3 | PLANNED |

## Phase Detail & Target Files

### Phase 1: Critical Bug Fixes & Route/Cache Cleanup
1. **Duplicate Router Decorators**: `backend/app/api/routes.py:127-150` (`dispatch_incident_route` and `resolve_incident_route`). Ensure only one `@router.post` exists per route.
2. **Variable Shadowing**: `backend/app/tools/registry.py:215` in `ToolRegistry.execute` (`args or {}` vs `args: dict[str, Any]`).
3. **ChatPanel Bugs**: `frontend/src/components/ChatPanel.tsx` stale closures and undefined variable bugs. Fix the `submit` signature and capture correct message state.
4. **Unbounded Route Cache**: `backend/app/tools/handlers.py` - wrap `_ROUTE_CACHE` with bounds/TTL or `functools.lru_cache`.

### Phase 2: Security Hardening & Input Validation
5. **Rate Limiter Origin Verification**: `backend/app/main.py` - prevent spoofing of `X-Forwarded-For` by checking `request.client.host` or a configured trusted proxy list.
6. **Payload Size Checks**: `backend/app/main.py` - measure the request body size from the stream directly or enforce via GZipMiddleware / middleware limits.
7. **Prompt Injection Scanner**: `backend/app/agent/loop.py` - improve robustness of regex/checks against pluralization, spacing, and PII bypasses.
8. **Simulator Thread Safety**: `backend/app/simulator/engine.py` - use a unified `RLock` or asyncio Lock to serialize check-and-act boundaries across simulation commands.
13. **Tool Input Validation**: `backend/app/tools/handlers.py` & `registry.py` - use explicit Pydantic models to validate tool arguments.

### Phase 3: Architecture & Type Safety
9 & 15. **Standardized ToolResult**: Standardize return types from tool handlers. Define a `ToolResult` model and ensure all handlers return it.
10. **Async KnowledgeStore**: `backend/app/knowledge/store.py` - add async methods and use thread pools for heavy embedding generation.
11. **React Error Boundaries**: `frontend/src/` - add boundary components around `ChatPanel`, `OpsDashboard`, and `ScenarioPanel`.
12. **ChatPanel Cancellation**: `frontend/src/components/ChatPanel.tsx` - implement `AbortController` to cancel active fetch queries when unmounting or switching roles.
14. **Circular Imports**: Resolve import cycles between `main.py`, `agent/loop.py`, and `core/gemini.py` using isolation/type checking.

### Phase 4: Quality, Accessibility & Test Coverage
16. **Magic Numbers Configuration**: `backend/app/simulator/engine.py` - move penalties/rates to config settings.
17. **CSS Consolidation**: `frontend/src/index.css` - clean up colors/spacing into shared design tokens.
18 & 19. **Unit/Integration Tests**: Write target tests for KnowledgeStore, Cache invalidation, Concurrency, and Accessibility.
20. **Strict Type Annotations**: Resolve mypy issues and enforce full annotation of public functions.
