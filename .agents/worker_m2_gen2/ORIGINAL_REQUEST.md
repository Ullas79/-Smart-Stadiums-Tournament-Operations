## 2026-07-12T03:56:47Z
You are worker_m2_gen2, a teamwork_preview_worker.
Your working directory is: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m2_gen2\
Your mission is to implement Phase 2: Security Hardening & Input Validation across the SmartStadium AI codebase.

Please read the following input files for full context and concrete fix strategies:
1. Rate Limiter & Payload Limit: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\explorer_m2_1\handoff.md
2. Prompt Injection Scanner: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\explorer_m2_2\handoff.md
3. Simulator Thread Safety & Tool Validation: C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\explorer_m2_3\handoff.md

Your concrete implementation tasks:
1. Rate Limiter IP Spoofing Prevention:
   - Modify `backend/app/core/config.py` to add `trusted_proxies` settings.
   - Modify `backend/app/main.py` (`RateLimitMiddleware.dispatch`) to check against trusted proxies list and only extract `X-Forwarded-For` from trusted clients.
   - Update `backend/tests/test_adversarial_security.py` (`test_rate_limiting_ip_spoofing_bypass` or similar) to ensure spoofed IPs are blocked.

2. Payload Size Limit Bypass:
   - Modify `backend/app/main.py` (`PayloadSizeLimitMiddleware.dispatch`) to wrap the ASGI `_receive` method, count total bytes read, and return 413 if it exceeds the limit (to block chunked/missing Content-Length bypasses).
   - Update `backend/tests/test_adversarial_security.py` to assert that requests with missing Content-Length but large bodies are rejected with 413.

3. Prompt Injection Scanner Multi-pattern Robustness:
   - Replace the `_is_unsafe` method in `backend/app/agent/loop.py` with the regex/unicode-normalization implementation proposed in explorer_m2_2's handoff.md.
   - Update `backend/tests/test_adversarial_security.py` and `backend/tests/test_challenger_m7.py` to assert that bypass attempts are blocked rather than allowed.

4. Simulator Compound Operation Thread Safety:
   - Add thread-safe public accessors (like `get_gate_ids()` and `get_zone_ids()`) returning lists/keys copy under `self._lock` in `backend/app/simulator/engine.py`.
   - Update `backend/app/tools/handlers.py` to use these thread-safe methods instead of direct field access.
   - Guard simulator task start/stop control in `backend/app/simulator/engine.py` with locking to prevent concurrency races.
   - Modify routing logic (`_shortest_path` and `_build_graph` in `handlers.py`) to accept and use a single snapshot of the stadium state.

5. Tool Argument Validation:
   - Define explicit Pydantic models for all tool arguments in `backend/app/tools/registry.py` (with typing.Literal for enums to maintain flat schemas).
   - Clean up schemas using a helper to remove `title` and `additionalProperties` so they match Gemini expectations.
   - Validate incoming parameters in `ToolRegistry.execute` using `model_validate()` and handle validation errors by returning structured error dictionary.

Validation & Verification Requirements:
- You must run the backend pytest suite (`.venv\Scripts\python.exe -m pytest -v`) and verify that 100% of the 178+ tests pass cleanly.
- You must run the frontend production build (`npm run build` or `npm run build` equivalent) to ensure there are no compilation errors.
- Document all modified files and testing commands/outputs in your handoff report at `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m2_gen2\handoff.md`.
- Maintain a liveness heartbeat by updating `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\.agents\worker_m2_gen2\progress.md` with your status and timestamp.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please report back when complete with the path to your handoff report.
