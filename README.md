# Smart Stadiums Unified Assistant — FIFA World Cup 2026 Final

A GenAI-enabled, role-aware assistant for the **FIFA World Cup 2026 Final at MetLife Stadium** (East Rutherford, NJ). One agentic function-calling loop serves three roles — **fan, volunteer, organizer** — and covers all four challenge tracks: dynamic crowd management, smart indoor navigation, real-time decision support, and multi-language assistance.

Built on **Google Gemini** (function calling + multilingual), with a synthetic but venue-grounded **MetLife Stadium simulator** that ticks live state (crowd density, gate throughput, incidents, transit load) so the assistant's answers visibly change as the match progresses.

> **PromptWars 2026 — Main Challenge 4: Smart Stadiums & Tournament Operations.** Collaborating with Google for Developers.

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (React/TS)                                         │
│  Role switcher │ Chat panel │ Live ops dashboard            │
└──────────────┬──────────────────────────────┬───────────────┘
               │ POST /chat                    │ GET /state
┌──────────────▼──────────────────────────────▼───────────────┐
│ FastAPI backend                                             │
│  api/ ─ agent/ ─ tools/ ─ knowledge/ ─ simulator/ ─ core/    │
│                    │                        │                │
│                    ▼                        ▼                │
│             Gemini (function calling)   MetLife state        │
│             + RAG context               (asyncio tick)       │
└─────────────────────────────────────────────────────────────┘
```

- **Agent loop** (`app/agent/loop.py`) — a single role-aware function-calling loop. The user's role is injected into the system prompt and **enforced server-side** via a per-role tool allowlist on every call.
- **Simulator** (`app/simulator/engine.py`) — advances the match clock (gates open → arrival → pre-kickoff → live → halftime → full-time) and evolves crowd density, gate queues, incidents, and transit load on an asyncio tick.
- **Tools** (`app/tools/`) — 10 role-guarded tools: `get_crowd_density`, `get_all_zones_status`, `find_route` (accessibility-aware indoor graph), `lookup_schedule`, `get_gate_status`, `report_incident`, `get_incidents`, `recommend_action` (decision support), `translate_response`, `search_knowledge`.
- **Knowledge/RAG** (`app/knowledge/`) — in-memory vector store over stadium FAQs/policies, with Gemini embeddings when a key is present and a deterministic keyword fallback otherwise.

## Roles & capabilities

| Role | Capabilities |
|---|---|
| **Fan** | navigation, schedule, amenities, FAQ, multilingual |
| **Volunteer** | above + report/view incidents, assist-guidance |
| **Organizer** | full ops view + decision-support recommendations + crowd-flow actions |

## Fidelity statement

The MetLife Stadium model is **structurally faithful** to the real venue — capacity (~82,500), bowl levels, concourses, gate taxonomy, parking lots, and the NJ Transit Meadowlands rail connection. Fine-grained details (exact gate lettering, concession placement) are illustrative where public data is ambiguous.

---

## Quick start

### 1. Configure environment
```bash
cp .env.example .env
# Set GOOGLE_API_KEY in .env (https://aistudio.google.com/apikey)
```

Without a key the backend runs in **offline mode** (deterministic fallback responses) so you can still demo the dashboard and wiring.

### 2. Run the backend
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows  (or: source .venv/bin/activate)
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 3. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### 4. (Optional) Docker
```bash
docker compose up --build
# Frontend: http://localhost:5173   Backend: http://localhost:8000
```

### 5. Production deployment: backend on Render, frontend on Vercel

The backend needs a **persistent process** (the MetLife simulator runs an
asyncio tick task in the background), so it deploys to **Render** as a Docker
web service — not serverless. The frontend is a static Vite build, deployed to
**Vercel**. See `MANUAL_DEPLOY.md` for the full step-by-step runbook.

Quick summary:
1. **Backend → Render**: create a Blueprint from this repo (`render.yaml`),
   set `GOOGLE_API_KEY` and `BACKEND_CORS_ORIGINS` (your Vercel URL). Render
   builds `backend/Dockerfile` and serves it at `https://<your-backend>.onrender.com`.
2. **Frontend → Vercel**: import the repo, set Root Directory = `frontend`,
   set `VITE_API_BASE=https://<your-backend>.onrender.com`, deploy.
3. Verify: `https://<your-backend>.onrender.com/health` → `{"status":"ok"}`,
   then open the Vercel URL.

> **⚠️ Render Free Tier — Cold Start Notice**
>
> Render's free web services **spin down after 15 minutes of inactivity**.
> The first request after spin-down triggers a cold start that takes
> **30–60 seconds** while the container rebuilds and the simulator
> re-initializes. To avoid this during a live demo or judging session:
>
> 1. **Use [UptimeRobot](https://uptimerobot.com/)** (free) — set up an
>    HTTP monitor to ping `https://<your-backend>.onrender.com/health`
>    every **14 minutes**. This keeps the container alive 24/7 within
>    Render's 750 free instance-hours/month.
> 2. **Or manually ping** the `/health` endpoint a few minutes before
>    your demo to pre-warm the service.
>
> Free tier limits: **512 MB RAM**, **0.1 vCPU** (shared), **100 GB
> bandwidth/month**. This application is well within all limits — the
> in-memory simulator uses < 10 MB and there is no database dependency.

---

## Testing

```bash
# Backend (172 tests including concurrency stress tests)
cd backend && .venv/Scripts/python.exe -m pytest -q

# Frontend (7 component tests)
cd frontend && npm test
```

Tests use **no real Gemini calls** — the agent loop is exercised with scripted fake responses, so the suite runs offline and deterministically.

## Demo script

1. Open the UI at http://localhost:5173. The **live ops dashboard** polls `/state` every 5s and updates crowd bars, gate status, incidents, and transit.
2. Pick the **Fan** role, language **English**, and ask: *"How do I get to my seat in Lower North?"* → the agent calls `find_route`.
3. Switch language to **Spanish** and ask *"Which restroom is least crowded?"* → `get_all_zones_status` + multilingual reply.
4. Switch to **Volunteer** and ask *"Where are the active incidents?"* → `get_incidents`.
5. Switch to **Organizer** and ask *"Give me operational recommendations."* → `recommend_action` returns phase-aware decisions (open secondary gates, dispatch first aid, etc.).
6. Wait and watch the dashboard change as the simulator advances match phases — the same question yields different answers over time.

## Project layout
```
backend/app/   core, models, simulator, knowledge, tools, agent, api
backend/tests/ simulator, tools, agent, api, integration
frontend/src/  App, api, types, components (RoleSwitcher, ChatPanel, OpsDashboard)
docs/superpowers/  specs/ + plans/
```

## Design & plan
- Spec: `docs/superpowers/specs/2026-07-07-smart-stadiums-assistant-design.md`
- Plan: `docs/superpowers/plans/2026-07-07-smart-stadiums-assistant.md`

## Security notes
- Gemini API key is server-side only; never exposed to the frontend.
- Role authorization is enforced **server-side** before each tool runs — the frontend role value is a hint, never trusted.
- Prompt-injection hardening: system-prompt fencing + per-role tool allowlist.
- No PII is collected.

## License
MIT — built for the PromptWars 2026 hackathon.
