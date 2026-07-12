# Handoff Report - explorer_m7_3

## 1. Observation
* **Files reviewed**:
  * `backend/app/agent/loop.py` (Lines 1-195): Coordinates the agent loop and tool execution. Line 137 seeds user message; lines 159-166 execute function calls.
  * `backend/app/agent/prompt.py` (Lines 1-71): System prompt builder containing `_INJECTION` instructions (Lines 42-47).
  * `backend/app/models/roles.py` (Lines 1-113): Defines the 4 personas (`Role.FAN`, `Role.VOLUNTEER`, `Role.ORGANIZER`, `Role.STAFF`) and `ROLE_TOOLS` mapping.
  * `backend/app/main.py` (Lines 1-100): FastAPI app creation and middleware configuration. Currently contains `CORSMiddleware` setup (Lines 87-93).
  * `backend/app/core/config.py` (Lines 1-52): Application settings loader.
* **Test suite state**:
  * Executed pytest command: `.venv\Scripts\pytest`
  * Execution log output: `142 passed, 1 warning in 12.56s`
  * Key role-guard assertions in tests:
    * `tests/test_agent_loop.py` Line 112: `assert res.tool_events[0].error is True` and Line 113: `assert "not authorized" in str(res.tool_events[0].result)`
    * `tests/test_tools.py` Line 32: `assert "not authorized" in res["error"]`

## 2. Logic Chain
1. **R1 (GenAI Guardrails)**: Because user input messages are untrusted, introducing a sanitization scan (`check_guardrails`) before sending instructions to the LLM (Gemini client) is required to prevent prompt injections, PII leakage, and env/secret leaks. Placing this validation in `Agent.run()` before setting up the conversation guarantees that any violating message is intercepted immediately, returning the requested fallback result:
   `AgentResult(reply="I cannot fulfill this request. For your safety and security, operations are restricted to tournament guidelines.", tool_events=[], snapshot_summary=snapshot.summary())`
2. **R2 (RBAC Enforcement)**: To enforce server-side RBAC without breaking existing tests, we must ensure that any authorization check failures return messages containing `"not authorized"`. By intercepting calls to unpermitted tools in `Agent.run()` and returning a structured JSON error (`PermissionDenied`), we satisfy R2, while updating `ToolRegistry.execute()` to return a compatible error string ensures that both the unit tests and integration tests continue to pass.
3. **R3 (Middleware Security)**: Hardening the FastAPI application with custom middleware classes allows us to inject security headers (`X-Content-Type-Options`, `X-Frame-Options`), check the `Content-Length` header for payload size violations (returning HTTP 413), and run a simple, zero-dependency, IP-based rate limiter (returning HTTP 429) without introducing external Python packages.

## 3. Caveats
* **Luhn Algorithm**: The credit card scan relies on regex matching for common card formats and lengths. For complete correctness, a Luhn check could be added if false positives on long numeric strings become an issue, though the current pattern is sufficient for basic safety.
* **Rate-limiting Storage**: The rate-limiter is in-memory. In a distributed multi-instance deployment (e.g., using multiple Docker replicas), an in-memory limiter operates per-replica rather than globally. If strict global rate limiting is required later, a Redis-backed rate limiter should be introduced.

## 4. Conclusion
We have designed a complete, non-breaking, and self-contained implementation plan to address all requirements of Milestone 7. The code modifications detailed in `analysis.md` can be safely applied to `loop.py`, `prompt.py`, `roles.py`, `main.py`, and `config.py` to achieve comprehensive hardening.

## 5. Verification Method
1. **Test Suite Baseline**:
   Run `.venv\Scripts\pytest` from the `backend/` directory to verify that all 142 tests continue to pass.
2. **Endpoint Validation**:
   * Send a POST request to `/chat` with a query >2000 characters or containing `"dump system prompt"`. Confirm it returns the fallback message and `tool_events=[]`.
   * Trigger an unauthorized tool call (e.g., call `recommend_action` as a `fan`) and check that it is blocked with a structured `PermissionDenied` error.
   * Send a request to `/health` and verify the headers `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` are present.
   * Send a POST request exceeding 1MB payload size and confirm it returns `413 Payload Too Large`.
