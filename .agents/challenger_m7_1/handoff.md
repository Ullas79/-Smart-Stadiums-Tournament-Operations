# Handoff Report — Milestone 7 Security Verification & Challenge

**Date**: 2026-07-11
**Agent ID**: challenger_m7_1

---

## 1. Observation

- **Input Safety Scan**: In `backend/app/agent/loop.py` lines 205-248, the `_is_unsafe` method checks prompt strings using exact substring searches and regexes:
  ```python
  jailbreak_keywords = [
      "ignore previous instructions",
      "dump system prompt",
      "you are now in developer mode",
      "execute all tools",
      "system prompt",
      "jailbreak",
      "override constraints",
  ]
  ...
  ssn_pattern = r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"
  cc_pattern = r"\b(?:\d[ -]*?){13,16}\b"
  ...
  env_pattern_1 = r"\$\{[A-Za-z0-9_]+\}"
  env_pattern_2 = r"%[A-Za-z0-9_]+%"
  ```
  We observed that variations like newlines (`"system\nprompt"`), dot separators (`"123.45.6789"`), and variable patterns without curly braces (`$GOOGLE_API_KEY`) bypass these checks.

- **Direct Route Execution**: In `backend/app/api/routes.py` lines 127-145, the REST API endpoints are exposed:
  ```python
  @router.post("/api/incidents/dispatch", status_code=200)
  @router.post("/incidents/dispatch", status_code=200)
  ...
  def dispatch_incident_route(req: DispatchRequest, request: Request) -> dict[str, Any]:
  ```
  No role or authentication decorators are applied. In our test `test_rbac_bypass_via_direct_api_endpoint`, a TestClient post to `/api/incidents/dispatch` without headers succeeded with status 200 and successfully mutated the simulator state.

- **Rate Limit Middleware**: In `backend/app/main.py` lines 76-103:
  ```python
  ip = request.client.host if request.client else "unknown"
  forwarded = request.headers.get("X-Forwarded-For")
  if forwarded:
      ip = forwarded.split(",")[0].strip()
  ```
  In `test_rate_limit_bypass_via_x_forwarded_for`, we verified that changing the `X-Forwarded-For` header allowed 5 requests to succeed when the rate limit was configured to 2.

- **Payload Size Middleware**: In `backend/app/main.py` lines 106-121:
  ```python
  content_length = request.headers.get("content-length")
  if content_length:
      ...
  ```
  In `test_payload_limit_bypass_missing_content_length`, we verified that a request missing `content-length` bypassed the check and returned status 200.

- **Test Suite Results**: Running `.venv\Scripts\pytest` returned:
  ```
  tests\test_adversarial_security.py .......                               [  4%]
  tests\test_challenger_m7.py ......                                       [ 21%]
  ======================= 163 passed, 1 warning in 17.65s =======================
  ```

---

## 2. Logic Chain

1. **Jailbreak/PII/Env Bypass**: Since the `_is_unsafe` check uses simple substring matches and specific regexes (Observation 1), a payload structured differently (e.g. `$VAR` instead of `${VAR}`, dots instead of hyphens, newlines instead of spaces) will fail to match. Thus, the validation passes through to the LLM.
2. **RBAC Bypass**: Because the backend exposes REST routes for incident dispatch/resolution directly on the FastAPI router and does not check for user authentication or authorization (Observation 2), these endpoints can be invoked by anyone. Thus, the client can bypass the chatbot interface and mutate state directly.
3. **Rate Limit Bypass**: Since `RateLimitMiddleware` retrieves the IP from `X-Forwarded-For` and prioritizes it (Observation 3), a client supplying different values in that header will be treated as distinct users. Thus, the rate limits are bypassed.
4. **Payload Limit Bypass**: Since `PayloadSizeLimitMiddleware` skips its checks if the `content-length` header is missing (Observation 4), a chunked request omitting this header bypasses the size verification entirely.

---

## 3. Caveats

- We did not implement code fixes in the backend repository because our role is strictly review and verification, and we have a key constraint against modifying implementation code.
- Test client behavior in pytest uses simulated HTTP requests. Real network routing might involve intermediary proxies which could overwrite or drop `X-Forwarded-For` headers.

---

## 4. Conclusion

The security implementations for Milestone 7 succeed in preventing basic malicious chatbot tool calls and queries. However, they suffer from high-risk design bypasses:
1. REST endpoints (dispatch/resolve) lack RBAC/auth checks and are open to direct state mutation.
2. Rate-limiting is easily circumvented via header spoofing.
3. Payload limit checks can be avoided using chunked transfer encoding.
4. Input safety checks are easily bypassed via lexical variations.

---

## 5. Verification Method

To verify these bypasses independently, execute the test suites:
1. Activate backend virtual environment and run the test command:
   ```powershell
   cd backend
   .venv\Scripts\pytest tests/test_challenger_m7.py
   .venv\Scripts\pytest tests/test_adversarial_security.py
   ```
2. Verify that all 6 tests in `test_challenger_m7.py` and 7 tests in `test_adversarial_security.py` pass. If they pass, it confirms that the bypasses are valid and successful.
