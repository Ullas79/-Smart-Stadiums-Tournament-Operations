## 2026-07-11T12:05:41Z
You are a versatile implementation worker (teamwork_preview_worker) working in workspace C:\Users\hp\-Smart-Stadiums-Tournament-Operations. Your folder is C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_worker_accessibility.

Your task is to implement the accessibility and inclusive design improvements across both the frontend and backend of SmartStadium AI as identified in our audit.

Here are the specific implementation requirements:

1. **Frontend React Components**:
   - Locate components: App.tsx, components/ChatPanel.tsx, components/ScenarioPanel.tsx, components/OpsDashboard.tsx.
   - Update these components by merging the structural, semantic HTML, ARIA landmarks, aria-live alert regions, and keyboard navigation enhancements provided in the explorer files:
     - C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_1\proposed_App.tsx
     - C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_1\proposed_ChatPanel.tsx
     - C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_1\proposed_ScenarioPanel.tsx
     - C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_1\proposed_OpsDashboard.tsx
   - Be careful to keep any other existing application features intact during the copy/merge.

2. **Frontend Styling and WCAG Contrast compliance**:
   - Locate CSS files: frontend/src/index.css and other component .css stylesheets.
   - Apply the styles and focus visible outline rules from C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_1\proposed_styles.css.
   - Apply the WCAG 4.5:1 / 3:1 contrast ratio fixes defined in the patch file: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_explorer_accessibility_2\accessibility_contrast_fixes.patch. (If you cannot run git apply directly, you can manually apply the border-color, color, background-color, and opacity overrides specified in the patch).

3. **Backend Indoor Wayfinding (Dijkstra) and GenAI Prompts**:
   - Locate files: backend/app/tools/handlers.py and backend/app/agent/prompt.py.
   - Update handlers.py wayfinding:
     - Add the helper _waypoint_to_zone_id mapping waypoint IDs to zone IDs.
     - Parse both "accessible" and "accessible_only" in find_route argument reading.
     - In _build_graph, implement dynamic cost weighting. If accessible_only is true, do NOT drop non-accessible edges. Instead, penalize stairs (add 10000.0 meters) and escalators (add 20000.0 meters) so they are avoided but allowed as a physical last resort.
     - Add dynamic penalties based on live telemetry (zone density >= 0.85 add 1500.0, >= 0.50 add 300.0; restricted gate status add 1500.0, closed gate status add 99999.0; active incident severity mapping: low 500.0, medium 1500.0, high 5000.0).
     - In _shortest_path, include simulator sim_time (int(snap.match.sim_time)) in the cache key of _ROUTE_CACHE so cached routes invalidate as simulation advances.
   - Update prompt.py system prompts:
     - Append the detailed screen-reader output formatting guidelines (prohibiting ASCII art, Visual flowcharts, unlabeled tables; requiring step-by-step lists and table headers with text descriptions) to the string returned by build_system_prompt.

4. **Testing and Verification**:
   - Execute the backend test suite: running .venv\Scripts\python.exe -m pytest -v in backend/ and verify that all 163+ tests pass cleanly. Write a new unit test in backend/tests/test_tools.py verifying that accessible routing from gate to seats succeeds (even though it uses stairs as a last resort) and includes the correct penalty.
   - Execute the frontend test suite: running npm test inside frontend/ and verify that all 7+ tests pass cleanly.
   - Execute the production frontend build: running npm run build inside frontend/ and verify it compiles without errors or warnings.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please report your progress and implementation status. When completed, write your handoff report to C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\teamwork_preview_worker_accessibility\handoff.md.
