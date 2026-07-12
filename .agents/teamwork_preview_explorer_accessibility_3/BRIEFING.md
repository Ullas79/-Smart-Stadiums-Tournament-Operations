# BRIEFING — 2026-07-11T12:15:00Z

## Mission
Audit wayfinding backend and GenAI prompts for accessibility improvements.

## 🔒 My Identity
- Archetype: teamwork_preview_explorer
- Roles: Read-only exploration agent
- Working directory: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_3
- Original parent: 031630e1-66ac-4716-beda-10dc8fd345f2
- Milestone: accessibility-audit

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- CODE_ONLY network mode: no external HTTP requests/curl/wget/etc.

## Current Parent
- Conversation ID: 031630e1-66ac-4716-beda-10dc8fd345f2
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `backend/app/tools/handlers.py` (wayfinding Dijkstra shortest path calculation)
  - `backend/app/models/stadium.py` (static venue graph, EdgeKind, PathEdge)
  - `backend/app/models/state.py` (live telemetry snapshot, crowd density, gate status, incidents)
  - `backend/app/simulator/fixtures.py` (static venue data loading)
  - `backend/app/agent/prompt.py` (system prompt builder)
  - `backend/app/agent/loop.py` (Gemini chat loop)
  - `backend/app/tools/registry.py` (tool schemas and permissions)
- **Key findings**:
  - `accessible_only=True` (passed as `accessible` in `find_route` tool arguments) currently hard-filters out all edges not marked accessible (Stairs/Escalators).
  - Since all connections to seating zones in `fixtures.py` are strictly defined as `EdgeKind.STAIRS`, this hard-filtering causes route calculation to seating zones to fail (no route found) when accessibility is enabled.
  - The pathfinding algorithm does not consider real-time simulator state (crowd density, gate status, or active incidents) for bottleneck avoidance.
  - The in-memory routing cache is based purely on static coordinates and `accessible_only`, meaning dynamic weights would lead to stale cached paths if the cache key is not updated.
  - The assistant prompt lacks instructions on screen-reader compatibility, risking the output of visually structured ASCII diagrams or complex unlabeled tables.
- **Unexplored areas**: None. Audited all requested components.

## Key Decisions Made
- Audited the backend pathfinding and agent prompt for accessibility gaps.
- Designed a cost-based penalty system for Dijkstra pathfinding to prioritize elevators/ramps and bypass bottlenecks instead of hard-filtering.
- Developed screen-reader friendly markdown guidelines for GenAI prompts.

## Artifact Index
- C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_3\handoff.md — Accessibility audit analysis and proposed changes
