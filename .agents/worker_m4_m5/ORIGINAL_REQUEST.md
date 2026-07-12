## 2026-07-11T03:25:04Z
You are teamwork_preview_worker. Your working directory is C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m4_m5\.

Your task is to implement the enhancements for Milestone 4 (Persona Coverage & Role-Aware Operations) and Milestone 5 (Decision Support & API Routing).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please perform the following steps:

1. Backend Role & Tools Enhancements:
   - Open and edit `backend/app/models/roles.py`:
     - Add `Role.STAFF = "staff"` (with value `"staff"`) to the `Role` enum.
     - Add a description for `Role.STAFF` in `ROLE_DESCRIPTIONS`: `"On-ground facility and operations staff. Controls gate statuses, dispatches staff/volunteers, and mitigates crowd bottlenecks."`
     - In `ROLE_TOOLS`, map tools for `Role.STAFF` to include: `{"get_crowd_density", "get_all_zones_status", "find_route", "lookup_schedule", "get_gate_status", "report_incident", "get_incidents", "translate_response", "search_knowledge", "set_gate_status", "dispatch_staff", "mitigate_bottleneck"}`.
   - Open and edit `backend/app/tools/handlers.py`:
     - Implement tool handler `set_gate_status(args, ctx)`: parameters `gate_id` (str) and `status` (str, e.g. "open" | "restricted" | "closed"). Find the gate in simulator, update its status, adjust throughput/queues appropriately. Return the updated gate dict.
     - Implement tool handler `dispatch_staff(args, ctx)`: parameters `incident_id` (str) and `assigned_staff` (str). Update the incident in the simulator to record that staff/volunteer is dispatched (e.g. update status/description). Return the updated incident.
     - Implement tool handler `mitigate_bottleneck(args, ctx)`: parameters `zone_id` (str) and optionally `strategy` (str). Reduce the occupancy/density of the crowd zone in the simulator (e.g. reduce density by 25%). Return details.
     - Enhance `recommend_action(args, ctx)`: when incidents or crowd surges (>85% capacity threshold) occur, output concrete, multi-step operational mitigation plans (e.g. "Step 1: Open secondary turnstiles... Step 2: Deploy volunteers...").
   - Open and edit `backend/app/tools/registry.py`:
     - Register the three new tools in `_SCHEMAS`, `_DESCRIPTIONS`, and `_handlers`.
   - Open and edit `backend/app/agent/prompt.py`:
     - Enhance the system instructions to describe all 4 personas (Fans, Organizers, Volunteers, On-Ground Staff) and context about their allowed capabilities.

2. API Routing Enhancements:
   - Open and edit `backend/app/simulator/engine.py`:
     - Add helper methods `dispatch_incident(incident_id, assigned_staff)` and `resolve_incident(incident_id)` to find and update incidents. Handle errors (raise KeyError if not found, raise ValueError if already resolved).
   - Open and edit `backend/app/api/routes.py`:
     - Implement `POST /api/incidents/dispatch` (and register aliases `/incidents/dispatch`, `/api/incident/dispatch`, `/incident/dispatch` using multiple decorators) accepting payload `{"incident_id": str, "volunteer_id": str, "assigned_staff": str}`. Find and dispatch via simulator method. Return 200/201 JSON `{"status": "success", "incident": ...}`. Handle KeyError (404) and ValueError (400).
     - Implement `POST /api/incidents/resolve` (and aliases `/incidents/resolve`, `/api/incident/resolve`, `/incident/resolve`) accepting payload `{"incident_id": str}`. Find and resolve via simulator method. Return 200/201 JSON `{"status": "success", "incident": ...}`. Handle KeyError (404) and ValueError (400).

3. Frontend Role Switcher & Types:
   - Open and edit `frontend/src/types.ts`:
     - Add `"staff"` to the `Role` union type.
   - Open and edit `frontend/src/components/RoleSwitcher.tsx`:
     - Add `{ value: "staff", label: "Staff", emoji: "🛠️" }` to `ROLES`. Ensure proper aria attributes are preserved.

4. Run build and tests:
   - Run python pytest inside `backend/`: `.venv\Scripts\python.exe -m pytest -v`
   - Run vitest tests inside `frontend/`: `npm test` or `npm run test:run`
   - Run production build inside `frontend/`: `npm run build`
   - Verify that everything compiles, builds, and passes cleanly with zero errors.

Update your `progress.md` file in `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m4_m5\progress.md` as you make progress. Report back when finished.
