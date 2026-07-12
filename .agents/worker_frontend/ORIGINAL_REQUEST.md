## 2026-07-10T18:27:55Z
You are worker_frontend, a Frontend Quality Refactoring Engineer.
Your working directory is C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_frontend\.
Your task is to refactor all React and TypeScript files in frontend/src/ to ensure type safety, WCAG-aligned accessibility, and clean asynchronous behavior.

Specifically, you need to address the following findings from the codebase quality audit:
1. TypeScript Type Escapes (elimination of 'any'):
   - In frontend/src/api.ts, replace 'any' in Promise<{ status: string; incident: any }> with a proper type, e.g. using the incident-related types from frontend/src/types.ts.
   - In frontend/src/components/ScenarioPanel.tsx, resolve 'catch (err: any)' by typing the catch error or casting it to a structured Error/unknown type before using.
2. Unhandled Promises:
   - In frontend/src/components/ChatPanel.tsx: ensure the call to 'submit(input)' in the form onSubmit handler does not discard/leave the promise unhandled. Wrap it or handle it cleanly.
   - In frontend/src/components/ScenarioPanel.tsx: handle/await the async 'handleTrigger' function call inside the button click handlers.
3. WCAG-aligned ARIA Accessibility:
   - In frontend/src/components/OpsDashboard.tsx: locate the crowd density bar cells (represented as div elements with title attributes) and add role="progressbar", aria-valuenow (with the rounded percentage capacity value), aria-valuemin="0", and aria-valuemax="100".
   - Hide decorative emojis inside headings or interactive button elements from screen readers by wrapping them in '<span aria-hidden="true">' (e.g. the stadium emoji in frontend/src/App.tsx, and the incident emojis in frontend/src/components/ScenarioPanel.tsx).
   - In frontend/src/components/ScenarioPanel.tsx, update the root element from a plain 'div' to a semantic '<section aria-label="Scenario Injection Panel">' or similar.

Verify your work by running:
- Frontend test suite: 'npm test' (run inside frontend/)
- Frontend production build: 'npm run build' (run inside frontend/)
Verify that all 7 tests pass and the Vite build completes cleanly with zero typescript compiler errors or bundle warnings.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your changes and verification outcomes to handoff.md inside C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_frontend\ and send a message back to the orchestrator (conversation ID f09f8cab-9d9c-4655-adff-ac1106092d27).
