# Changes Log — Security Hardening

Implementations and modifications performed for Milestone 7 Security Hardening requirements.

## Files Modified

### 1. `backend/app/core/config.py`
- Added the following properties to the `Settings` class:
  - `agent_max_message_chars: int = 2000`
  - `max_payload_size_bytes: int = 1048576` (1MB)
  - `rate_limit_requests: int = 100`
  - `rate_limit_window_seconds: int = 60`

### 2. `backend/app/agent/prompt.py`
- Enhanced the system prompt `_INJECTION` string to explicitly instruct the agent to ignore jailbreaks, developer mode override attempts, and commands asking to dump the system prompt or show environment details.

### 3. `backend/app/agent/loop.py`
- Added input safety scan method `_is_unsafe` validating:
  - Message length (< 2000 characters using `settings.agent_max_message_chars`)
  - Jailbreak keywords (e.g., "ignore previous instructions", "dump system prompt", "you are now in developer mode", "execute all tools", "system prompt", "jailbreak", "override constraints")
  - PII (SSNs `\b\d{3}[- ]\d{2}[- ]\d{4}\b`, credit cards `\b(?:\d[ -]*?){13,16}\b`)
  - Environment exfiltration patterns (substrings: `os.environ`, `os.getenv`, `process.env`; regex pattern: `${VAR}` or `%VAR%`)
- Enforced the pre-scan safety check at the very beginning of `Agent.run()` before calling Gemini, returning a secure fallback result if trigger matches.
- In the function execution loop, added verification using `self.registry.is_allowed(fc.name, role)`. Intercepts and sets `result = {"error": "PermissionDenied: Role '...' is not authorized to call '...'."}` before any state mutation occurs.

### 4. `backend/app/tools/registry.py`
- Updated the `execute` method to return `{"error": f"PermissionDenied: Role '{role.value}' is not authorized to call '{name}'."}` when the role is not authorized.

### 5. `backend/app/main.py`
- Implemented `RateLimitMiddleware` (zero-dependency sliding-window in-memory IP rate limiting).
- Implemented `PayloadSizeLimitMiddleware` (checks `Content-Length` header against `Settings.max_payload_size_bytes` and returns HTTP 413).
- Implemented `SecurityHeadersMiddleware` (injects security hardening headers `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` on all responses).
- Registered these middlewares in `create_app` in correct order alongside `CORSMiddleware`.

### 6. `backend/tests/test_security_hardening.py`
- Created a new test file containing:
  - `test_security_headers`: checks that `X-Content-Type-Options` and `X-Frame-Options` headers are present and correct on response headers.
  - `test_payload_size_limit`: tests that requests exceeding `max_payload_size_bytes` return HTTP 413.
  - `test_rate_limiting`: tests that exceeding `rate_limit_requests` in `rate_limit_window_seconds` returns HTTP 429.
  - `test_prompt_injection_fallback_length`: verifies fallback reply is returned when input exceeds max characters.
  - `test_prompt_injection_fallback_keywords`: verifies fallback reply is returned for jailbreak attempt strings.
  - `test_prompt_injection_fallback_pii`: verifies fallback reply is returned for SSN/credit card strings.
  - `test_prompt_injection_fallback_env_exfiltration`: verifies fallback reply is returned for environment exfiltration attempts.
  - `test_rbac_guards_prevent_tool_calls`: verifies server-side RBAC checks block unauthorized tool execution in both the tool registry and the agent execution loop, returning a `PermissionDenied` error message.
