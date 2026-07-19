# Manual Deployment Runbook

This is the work **you** need to do by hand (in the Render + Vercel dashboards
and your Gemini account). Everything else is already in the repo:
- `render.yaml` — Render Blueprint for the backend
- `backend/Dockerfile` — container build (honors Render's `$PORT`)
- `frontend/vercel.json` — Vite static build config
- `frontend/src/api.ts` — already reads `VITE_API_BASE` for cross-origin calls

Architecture: **Backend on Render** (persistent process — required because the
MetLife simulator runs an asyncio tick task) **+ Frontend on Vercel** (static).

---

## 0. Prerequisites

- [ ] A GitHub repo with all code pushed (this repo).
- [ ] A Google Gemini API key → https://aistudio.google.com/apikey (free tier works).
- [ ] Accounts on Render (https://render.com) and Vercel (https://vercel.com),
      both signed in via GitHub.

---

## 1. Deploy the backend to Render

1. **Render dashboard → New → Blueprint.**
2. Select this GitHub repo. Render detects `render.yaml` and proposes the
   `smart-stadiums-backend` web service.
3. On the env-vars screen, fill the two `sync: false` secrets:
   - `GOOGLE_API_KEY` → paste your Gemini key.
   - `BACKEND_CORS_ORIGINS` → **leave blank for now**; you'll set it after you
     know your Vercel URL (Step 2). You can also come back and edit it later.
4. Click **Apply / Create Service**. Render builds `backend/Dockerfile` and
   starts it on an auto-assigned URL, e.g.
   `https://smart-stadiums-backend-xxxx.onrender.com`.
5. Wait for the build + deploy to finish (first build is slow).
6. **Smoke test** — open:
   `https://<your-backend>.onrender.com/health` → should return
   `{"status":"ok"}`.
7. **Bonus smoke test** — open:
   `https://<your-backend>.onrender.com/state` → should return JSON with
   `venue_name: "MetLife Stadium"` and a `crowd` array of 12 zones.
8. (Optional) open `/docs` for the FastAPI Swagger UI.

> The simulator's background tick task starts automatically via the FastAPI
> lifespan. No cron or worker needed.

> If `GOOGLE_API_KEY` is missing, the backend runs in **offline mode**
> (deterministic fallback replies) — `/state` and `/role` still work, but
> `/chat` won't call Gemini. Set the key to enable real answers.

---

## 2. Deploy the frontend to Vercel

1. **Vercel dashboard → Add New → Project.**
2. Import this GitHub repo.
3. **Set Root Directory** to `frontend` (Vercel asks "Configure Project" → pick
   the `frontend` folder). Vercel auto-detects Vite.
4. **Set Environment Variables:**
   - `VITE_API_BASE` = `https://<your-backend>.onrender.com` (from Step 1).
5. Click **Deploy.** Vercel runs `npm install && npm run build` and serves
   `frontend/dist`.
6. Note your Vercel URL, e.g. `https://smart-stadiums.vercel.app`.

> If you skip `VITE_API_BASE`, the frontend calls relative paths and will try
> to hit Vercel itself (404s). You must set it to the Render backend URL.

---

## 3. Connect the two (CORS)

The backend only allows origins listed in `BACKEND_CORS_ORIGINS`.

1. Go back to **Render → your backend service → Environment**.
2. Set `BACKEND_CORS_ORIGINS` = your Vercel URL, e.g.
   `https://smart-stadiums.vercel.app`.
   (Comma-separated if you have preview URLs too, e.g.
   `https://smart-stadiums.vercel.app,https://smart-stadiums-git-main.vercel.app`.)
3. Render auto-redeploys on env change. Wait for it to go live.
4. Open the Vercel URL. The dashboard should populate and chat should work.

---

## 4. Verify the full system

- [ ] Vercel page loads, **live ops dashboard** shows MetLife zones/gates/transit.
- [ ] Dashboard numbers change every ~5s (simulator ticking on Render).
- [ ] **Fan** role: ask "How do I get to my seat in Lower North?" → you get a
      real Gemini-powered route reply (if `GOOGLE_API_KEY` is set).
- [ ] Switch language to Spanish → reply comes back in Spanish.
- [ ] **Organizer** role: "Give me operational recommendations." → phase-aware
      recommendations appear.
- [ ] Browser DevTools Network: `/chat`, `/state` calls return 200 with no CORS
      errors.

---

## 5. Notes & gotchas

- **Cold starts (Render free tier):** Free web services **spin down after
  15 minutes of inactivity**. The next request triggers a **30–60 second**
  cold start while the Docker container rebuilds and the simulator
  re-initializes from `sim_time = -600`. To keep the service warm:
  1. **Recommended — [UptimeRobot](https://uptimerobot.com/)** (free account):
     create an HTTP(s) monitor targeting
     `https://<your-backend>.onrender.com/health` with a **14-minute interval**.
     This pings the backend before Render's 15-minute idle timeout, keeping the
     container alive 24/7 within the 750 free instance-hours/month quota.
  2. **Quick alternative:** manually open `/health` in a browser tab a few
     minutes before your demo session to pre-warm the service.
- **Free tier resource limits:** 512 MB RAM, 0.1 vCPU (shared), 100 GB
  outbound bandwidth/month. This application fits comfortably — the in-memory
  simulator + knowledge store use < 10 MB and there is no database dependency.
- **Vercel function timeout:** not relevant — the backend on Render has no
  10s limit. A `/chat` call may take a few seconds (Gemini + tool loop); that's
  fine on Render.
- **Vertex AI alternative:** if you prefer Vertex AI over the API-key Developer
  API, uncomment the Vertex env vars in `render.yaml` and set your GCP project.
- **Secrets:** never commit `.env`. `GOOGLE_API_KEY` lives only in Render's env.
- **Redeploys:** pushing to `main` auto-redeploys both Render (backend) and
  Vercel (frontend) if you connected the branch.

---

## TL;DR

| Step | Where | What |
|------|-------|------|
| 1 | Render | New Blueprint from repo → set `GOOGLE_API_KEY` |
| 2 | Vercel | Import repo, Root Dir = `frontend`, set `VITE_API_BASE=<render url>` |
| 3 | Render | Set `BACKEND_CORS_ORIGINS=<vercel url>` |
| 4 | Browser | Open Vercel URL, verify dashboard + chat |
