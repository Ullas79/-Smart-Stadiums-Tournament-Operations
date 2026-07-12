## 2026-07-11T04:05:00Z

You are the Security Hardening Worker (teamwork_preview_worker).
Your ID is worker_security.
Your working directory is C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_security.
Your task is to implement the security hardening requirements for Milestone 7 based on the synthesis report (C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\orchestrator\synthesis.md).

Specifically, you need to modify:
1. `backend/app/core/config.py`: Add the following properties to the Settings class:
   - max_payload_size_bytes: int = 1048576  # 1MB
   - rate_limit_requests: int = 100
   - rate_limit_window_seconds: int = 60
   - agent_max_message_chars: int = 2000
2. `backend/app/agent/prompt.py`: Enhance the safety prompt instructions in _INJECTION.
3. `backend/app/agent/loop.py`:
   - Implement an input safety scan method in the Agent class or as a helper function. This must validate message length (< 2000), jailbreak keywords, PII (SSN, credit cards), and env exfiltration.
   - If unsafe, return the fallback AgentResult: AgentResult(reply="I cannot fulfill this request. For your safety and security, operations are restricted to tournament guidelines.", tool_events=[], snapshot_summary=snapshot.summary())
   - Perform the scan at the very start of Agent.run() before token generation.
   - In the function execution loop, check `self.registry.is_allowed(fc.name, role)`. If False, intercept and set `result = {"error": "PermissionDenied: Role '...' is not authorized to call '...'."}` before any state mutation occurs.
4. `backend/app/tools/registry.py`: Update the `execute` method to return `{"error": f"PermissionDenied: Role '{role.value}' is not authorized to call '{name}'."}` when the role is not allowed.
5. `backend/app/main.py`:
   - Implement IP-based sliding window rate-limiting middleware (zero external dependencies).
   - Implement request body size limit middleware checking `Content-Length`.
   - Add security headers middleware: `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`.
   - Ensure CORS is correctly configured.
6. Write unit and integration tests in a new test file (e.g. `backend/tests/test_security_hardening.py`) verifying:
   - Request headers on API responses.
   - Payload size limit (status code 413 for oversized payload).
   - Rate limiting (status code 429 after exceeding limits).
   - Prompt injection fallback.
   - Server-side RBAC guards preventing tool calls (e.g. `Role.FAN` calling `recommend_action` or `set_gate_status`).
7. Run the backend tests to ensure everything compiles and passes cleanly:
   - `.venv\Scripts\python.exe -m pytest -v`
8. Check that frontend vitest tests (`npm test` in frontend/) and production builds (`npm run build` in frontend/) pass. (Use standard powershell run command to execute tests if needed, or implement it in your handoff report).

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.

Document all changes made in C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_security\changes.md and provide build/test command results in C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_security\handoff.md.
