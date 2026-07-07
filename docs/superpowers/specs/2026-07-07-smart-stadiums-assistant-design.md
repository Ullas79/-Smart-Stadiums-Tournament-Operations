# Smart Stadiums Unified Assistant — FIFA World Cup 2026 (MetLife Final)

**Status:** Approved design (2026-07-07)
**Challenge:** PromptWars 2026 — Main Challenge 4: Smart Stadiums & Tournament Operations
**Collaboration:** Google for Developers

## 1. Problem statement & alignment

Build a GenAI-enabled architecture that optimizes venue operations and elevates the tournament experience for fans, organizers, volunteers, and on-ground staff at the FIFA World Cup 2026 Final, hosted at MetLife Stadium (East Rutherford, NJ).

The solution targets the four named tracks through a single coherent product:

- **Dynamic crowd management** — live per-zone density, gate throughput, flow-aware rerouting.
- **Smart indoor navigation** — accessibility-aware wayfinding across the venue's indoor graph.
- **Real-time decision support** — staff/organizer recommendations grounded in live state.
- **Multi-language assistance** — multilingual fan-facing answers via Gemini's native multilinguality plus a translate tool.

Judging priorities addressed: **problem-statement alignment** (one product touching all tracks and all user types at a recognizable, named venue) and **code quality** (a single, well-bounded agentic loop that is straightforward to test and maintain). Security, efficiency, testing, and accessibility are addressed as secondary criteria below.

## 2. Decisions locked during brainstorming

| Decision | Choice | Rationale |
|---|---|---|
| Focus | Unified fan/staff assistant | Strongest problem alignment; covers all four tracks and all user types. |
| GenAI provider | Google Gemini + Vertex AI | Matches "Google for Developers" collaboration; grounding, function calling, multimodal, multilingual. |
| Tech stack | FastAPI (Python) + React/TS | Clean async backend ideal for LLM orchestration; polished demoable UI. |
| Data approach | Synthetic stadium simulator | Self-contained demo, no external flakiness; controllable state for repeatable demos. |
| Architecture | Single role-aware agent with function calling (Approach A) | One clean orchestration loop; high code quality; genuinely agentic. |
| Venue | MetLife Stadium, WC2026 Final | Recognizable, narrative anchor (the Final); structurally faithful model. |

## 3. Architecture

A FastAPI backend hosts a single **role-aware Gemini agent** running a function-calling loop. A **synthetic MetLife Stadium simulator** generates live state (crowd density per zone, schedule, gate status, incidents, transit load) and ticks on an asyncio schedule. A small **RAG layer** holds static knowledge (FAQs, policies, amenities). A React/TS frontend provides a role switcher (fan / volunteer / organizer), a chat panel, and a live ops dashboard.

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (React/TS)                                         │
│  Role switcher │ Chat panel │ Live ops dashboard            │
└──────────────┬──────────────────────────────┬───────────────┘
               │ /chat                        │ /state (poll/SSE)
┌──────────────▼──────────────────────────────▼───────────────┐
│ FastAPI backend                                             │
│  api/ ─ agent/ ─ tools/ ─ knowledge/ ─ simulator/ ─ core/    │
│                    │                        │                │
│                    ▼                        ▼                │
│             Gemini (function calling)   MetLife state        │
│             + RAG context               (asyncio tick)       │
└─────────────────────────────────────────────────────────────┘
```

### Data flow

`User msg → /chat → agent loop`:

1. Build system prompt from role + current stadium snapshot summary.
2. Call Gemini with the tool set + retrieved RAG context.
3. If Gemini emits a tool call, execute it against the simulator/knowledge (with server-side role guard) and feed the structured result back.
4. Loop until Gemini produces a final answer.
5. Stream the answer to the frontend; the dashboard subscribes to `/state`.

The simulator advances crowd/incidents/gates/transit independently of the agent on its own tick, so the world state the agent reads evolves even within a single conversation.

## 4. Backend components (`backend/app/`)

- `agent/` — agent loop, role-aware system-prompt builder, tool registry.
- `tools/` — function tools wrapping simulator + knowledge; role-guarded.
- `simulator/` — MetLife state engine ticking on asyncio.
- `knowledge/` — RAG index (in-memory vectors; swappable to Vertex AI Search).
- `api/` — FastAPI routes: `/chat`, `/state`, `/role`.
- `models/` — pydantic schemas (messages, roles, tool I/O, stadium state).
- `core/` — config, security, Gemini client.

Each module has one clear purpose, a well-defined interface, and can be tested independently.

## 5. Simulator & data model — MetLife Stadium, WC2026 Final

### Fidelity stance

The model is **structurally faithful** to the real venue — capacity, bowl levels, concourses, gate taxonomy, parking lots, and the Meadowlands rail connection — while some fine-grained details (exact gate lettering, concession placement) are illustrative where public data is ambiguous. The README states this explicitly.

### Static model (loaded from fixtures)

- `Venue` — name, city, capacity (~82,500), geo, final-match metadata.
- `Level` — Lower Bowl, Club Level, Upper Bowl, Suites.
- `Zone` — seating sections grouped into zones (e.g., 100s / 200s / 300s); each carries level, capacity, nearest gate, nearest concourse.
- `Gate` — label, served zones, current status (open / closed / restricted), throughput.
- `Amenity` — restrooms, concessions, first-aid, retail, ATM, water stations; each geo-located within a concourse/zone.
- `Waypoint` / `Path` — a small indoor graph connecting gates ↔ concourses ↔ zones ↔ amenities, enabling real `find_route` with accessibility-aware edges (elevator / escalator / ramp / stairs).
- `ParkingLot` + `TransitNode` — surrounding lots and the NJ Transit Meadowlands rail station, for arrival/departure flow.
- `Match` — fixture(s) culminating in the Final; kickoff / halftime / full-time timestamps drive crowd dynamics.

### Dynamic state (ticks every N seconds via asyncio)

- `CrowdDensity` per zone — evolves with a flow model: arrival surge pre-kickoff, settlement during play, concourse spike at halftime, exit surge at full-time; flows between connected zones along the path graph.
- `GateStatus` — throughput fluctuates; gates can hit capacity and trigger redirect recommendations.
- `Incidents` — probabilistic events (medical, congestion, lost child, entry bottleneck) that spawn with location and severity and resolve over time.
- `TransitLoad` — rail/bus congestion tracks match phase.

### Demo effect

The agent's answers visibly change as the match progresses: at kickoff it reports dense gates and reroutes a fan; at halftime it flags concourse congestion and recommends the least-crowded restroom; for organizers it surfaces an incident and recommends opening a secondary gate. The same query returns different, time-aware, venue-specific answers.

## 6. Function-calling tools (role-guarded)

| Tool | Roles | Purpose |
|---|---|---|
| `get_crowd_density(zone)` | all | Per-zone density. |
| `get_all_zones_status()` | all | Full zone density map. |
| `find_route(from, to, accessibility)` | all | Accessibility-aware indoor wayfinding. |
| `lookup_schedule(match_id?)` | all | Fixtures incl. the Final. |
| `get_gate_status(gate?)` | all | Gate throughput/status. |
| `report_incident(type, location, severity)` | volunteer, organizer | Create an incident. |
| `get_incidents()` | volunteer, organizer | List active incidents. |
| `recommend_action(scenario)` | organizer | Decision-support recommendation. |
| `translate_response(text, lang)` | all | Multilingual output. |
| `search_knowledge(query)` | all | RAG fallback over FAQs/policies/amenities. |

## 7. Roles & capabilities

- **Fan** — navigation, schedule, amenities, FAQ, multilingual.
- **Volunteer** — above, plus report/view incidents and assist-guidance.
- **Organizer** — full ops view, decision-support recommendations, crowd-flow actions.

Role is injected into the system prompt (shifting tool emphasis and answer framing) **and** enforced server-side via a per-role tool allowlist before any tool executes.

## 8. Error handling

- Tool execution errors are caught and returned as structured results so Gemini can recover.
- LLM calls retry with exponential backoff, then fall back to a graceful user-facing message.
- Simulator outages serve last-known cached state.
- All I/O validated with pydantic schemas.

## 9. Security (medium-impact criterion)

- Gemini API key kept server-side only; never exposed to the frontend.
- **Role-based authorization enforced server-side before each tool runs** — the frontend role is a hint, never trusted.
- Prompt-injection hardening: system-prompt fencing, per-role tool allowlist, input sanitization.
- No PII collected; rate limiting on public endpoints.

## 10. Testing (low-impact, easy wins)

- Pytest unit tests for simulator, tools, and the agent loop with a mocked Gemini client.
- One integration test for a full multi-turn conversation using recorded LLM responses.
- Vitest + React Testing Library for key frontend components (role switcher, chat panel, dashboard).

## 11. Efficiency (medium-impact criterion)

- Single LLM round-trip per turn where possible (batched tool results).
- Simulator tick interval tunable; cheap in-process state.
- RAG retrieval limited to top-k relevant chunks; in-memory vectors for the demo scale.

## 12. Accessibility (low-impact criterion)

- Frontend follows semantic HTML and keyboard-navigable controls.
- Wayfinding includes accessibility-aware routing (elevator/ramp edges).
- Multilingual support broadens reach to international fans.

## 13. Repo layout

```
/
  backend/
    app/
      agent/
      tools/
      simulator/
      knowledge/
      api/
      models/
      core/
    tests/
    pyproject.toml
  frontend/
    src/
    package.json
  docs/
    superpowers/
      specs/
        2026-07-07-smart-stadiums-assistant-design.md
  docker-compose.yml
  README.md
  .env.example
```

## 14. Build sequence (high-level)

1. Scaffold repo (`backend/`, `frontend/`, configs, README skeleton, `.env.example`).
2. Build data model + MetLife fixtures + asyncio simulator.
3. Build agent core (Gemini client, role-aware prompt builder, tool registry, function-calling loop).
4. Implement role-guarded tools.
5. Add RAG layer.
6. Expose API (`/chat`, `/state`, `/role`).
7. Build frontend (role switcher, chat, dashboard).
8. Tests (pytest + Vitest + one integration test).
9. README + demo script with explicit fidelity statement.

(A detailed implementation plan follows in the writing-plans step after spec review.)
