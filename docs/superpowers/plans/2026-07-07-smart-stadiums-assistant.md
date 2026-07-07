# Smart Stadiums Unified Assistant — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a role-aware Gemini function-calling assistant for the FIFA World Cup 2026 Final at MetLife Stadium, backed by a synthetic venue simulator.

**Architecture:** FastAPI backend hosts a single role-aware Gemini agent running a manual function-calling loop. An asyncio MetLife simulator ticks live state (crowd/gate/incident/transit). A small RAG layer holds static knowledge. React/TS frontend provides role switcher, chat, and live ops dashboard.

**Tech Stack:** Python 3.11+, FastAPI, pydantic v2, google-genai SDK (Gemini 2.5 Flash), pytest; React + TypeScript + Vite, Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-07-07-smart-stadiums-assistant-design.md`

**SDK notes (verified):**
- `pip install google-genai`; `from google import genai; from google.genai import types`
- Dev API: `genai.Client(api_key=...)` (env `GOOGLE_API_KEY`); Vertex: `genai.Client(vertexai=True, project=..., location=...)`.
- Tools: `types.FunctionDeclaration(name=..., description=..., parameters_json_schema={...})` wrapped in `types.Tool(function_declarations=[...])`.
- Function call inspection: `response.function_calls[0].name / .args / .id`.
- Function response: `types.Part.from_function_response(name=..., response={...})` in a `types.Content(role="user", parts=[...])` (manual contents loop).
- Config: `types.GenerateContentConfig(system_instruction=..., tools=[...], temperature=...)`.
- Model: `gemini-2.5-flash`.
- Async streaming: `client.aio.models.generate_content_stream(...)`.

---

## File structure

```
backend/
  pyproject.toml
  .env.example (root-level)
  app/
    __init__.py
    main.py                      # FastAPI app factory + lifespan (starts simulator)
    core/
      __init__.py
      config.py                  # Settings (pydantic-settings)
      gemini.py                  # Gemini client factory + tool declaration builder
      security.py                # role guard decorator + tool allowlist
    models/
      __init__.py
      roles.py                   # Role enum, role capabilities
      stadium.py                 # Venue, Level, Zone, Gate, Amenity, Waypoint, Path, Parking, Transit, Match
      state.py                   # dynamic state: CrowdDensity, GateStatus, Incident, TransitLoad, Snapshot
      chat.py                    # ChatRequest, ChatResponse, Message, ToolCall, ToolResult
    simulator/
      __init__.py
      fixtures.py                # MetLife static model loaders
      engine.py                  # StadiumSimulator (asyncio tick, flow model, incidents)
    knowledge/
      __init__.py
      store.py                   # In-memory vector RAG over knowledge docs
      docs.py                    # Static knowledge documents
    tools/
      __init__.py
      registry.py                # Tool registry: declarations + Python handlers + role guards
      handlers.py                # Tool handler implementations
    agent/
      __init__.py
      prompt.py                  # Role-aware system prompt builder
      loop.py                    # Function-calling agent loop
    api/
      __init__.py
      routes.py                  # /chat, /state, /role
  tests/
    __init__.py
    conftest.py
    test_simulator.py
    test_tools.py
    test_agent_loop.py
    test_api.py
    test_integration.py
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api.ts
    types.ts
    components/
      RoleSwitcher.tsx
      ChatPanel.tsx
      OpsDashboard.tsx
    __tests__/
      RoleSwitcher.test.tsx
      ChatPanel.test.tsx
docs/
  superpowers/
    plans/2026-07-07-smart-stadiums-assistant.md
    specs/2026-07-07-smart-stadiums-assistant-design.md
docker-compose.yml
README.md
.env.example
.gitignore
```

---

## Tasks

### Task 1: Backend scaffolding & config
- [ ] Create `backend/pyproject.toml` (deps: fastapi, uvicorn, pydantic, pydantic-settings, google-genai, httpx, pytest, pytest-asyncio).
- [ ] Create `app/core/config.py` with `Settings` (gemini api key, model id, sim tick seconds, max tool iterations).
- [ ] Create root `.env.example`, `.gitignore`.
- [ ] Verify: `python -c "import app"`.

### Task 2: Domain models (`app/models/`)
- [ ] `roles.py`: `Role` enum (fan/volunteer/organizer) + `ROLE_TOOLS` allowlist mapping.
- [ ] `stadium.py`: static venue entities.
- [ ] `state.py`: dynamic state entities + `StadiumSnapshot`.
- [ ] `chat.py`: API request/response + message types.
- [ ] Tests: pydantic round-trips.

### Task 3: MetLife fixtures (`app/simulator/fixtures.py`)
- [ ] `load_venue()` → `Venue` (MetLife, ~82,500, East Rutherford NJ).
- [ ] `load_levels_zones()` → 4 levels, ~12 zones across 100s/200s/300s.
- [ ] `load_gates()` → ~8 gates mapped to zones.
- [ ] `load_amenities()` → restrooms/concessions/first-aid/retail/water per concourse.
- [ ] `load_waypoints()` → indoor graph with accessibility-aware edges.
- [ ] `load_transit_parking()` → Meadowlands rail node + parking lots.
- [ ] `load_match()` → Final fixture with kickoff/halftime/full-time offsets.
- [ ] Tests: fixtures load, capacities consistent.

### Task 4: Simulator engine (`app/simulator/engine.py`)
- [ ] `StadiumSimulator.__init__(fixtures, tick_seconds)`.
- [ ] `tick()`: advance match phase, flow crowd between connected zones by phase, update gate throughput, probabilistically spawn/resolve incidents, update transit load.
- [ ] `snapshot()` → `StadiumSnapshot`.
- [ ] `start()/stop()` asyncio task.
- [ ] Tests: crowd rises pre-kickoff; concourse spike at halftime; incident spawns/resolves; snapshot stable.

### Task 5: Knowledge/RAG (`app/knowledge/`)
- [ ] `docs.py`: ~20 knowledge docs (FAQs, policies, amenities).
- [ ] `store.py`: in-memory vector store using `google-genai` embeddings (`gemini-embedding-001`), top-k retrieval; graceful fallback to keyword search if no API key.
- [ ] Tests: retrieval returns relevant doc; fallback works.

### Task 6: Tool registry & handlers (`app/tools/`)
- [ ] `handlers.py`: implement each tool against simulator + knowledge.
- [ ] `registry.py`: `ToolRegistry` mapping name → (FunctionDeclaration, handler, allowed_roles); `for_role(role)` returns allowed tools; `execute(name, args, role)` enforces guard.
- [ ] Tools: `get_crowd_density`, `get_all_zones_status`, `find_route`, `lookup_schedule`, `get_gate_status`, `report_incident`, `get_incidents`, `recommend_action`, `translate_response`, `search_knowledge`.
- [ ] Tests: each handler returns expected shape; role guard blocks unauthorized calls.

### Task 7: Agent loop (`app/agent/`)
- [ ] `prompt.py`: `build_system_prompt(role, snapshot_summary)` — role-specific instructions + current phase + prompt-injection fencing.
- [ ] `loop.py`: `Agent.run(messages, role)` — manual function-calling loop with the verified SDK calls, max iterations, tool execution via registry, returns final text + tool trace.
- [ ] Tests: loop with mocked Gemini client returns final text; handles a function call turn; respects max iterations; tool errors surfaced gracefully.

### Task 8: API (`app/api/routes.py`, `app/main.py`)
- [ ] `POST /chat` → run agent, stream or return ChatResponse.
- [ ] `GET /state` → current snapshot for dashboard.
- [ ] `GET /role` → available roles + capabilities.
- [ ] `main.py`: app factory, CORS, lifespan starts simulator + knowledge store.
- [ ] Tests: TestClient hits `/state`, `/role`, `/chat` with mocked agent.

### Task 9: Frontend scaffold
- [ ] Vite React/TS app, `api.ts` client, `types.ts`.
- [ ] `RoleSwitcher`, `ChatPanel`, `OpsDashboard` components.
- [ ] Poll `/state` for dashboard; `POST /chat` for chat.
- [ ] Tests: RoleSwitcher renders roles; ChatPanel sends request.

### Task 10: Integration test + README
- [ ] `test_integration.py`: full multi-turn conversation with recorded Gemini responses (mocked).
- [ ] `README.md`: setup, run, demo script, fidelity statement.
- [ ] `docker-compose.yml`.
- [ ] Final commit.

---

## Self-review

- **Spec coverage:** All four tracks (crowd/navigation/decision-support/multilingual) → tools in Task 6 + roles in Task 2. Venue grounding → Task 3. Dynamic state → Task 4. Security (role guards, key server-side, prompt fencing) → Tasks 2/6/7. Testing → Tasks 4–9. All spec sections mapped.
- **Placeholders:** None — tasks name exact files and concrete behavior.
- **Type consistency:** `Role` enum used consistently; `StadiumSnapshot` produced by simulator and consumed by agent prompt + API + tools; `ToolRegistry.execute` signature stable across tasks.

(Execution proceeds inline via executing-plans.)
