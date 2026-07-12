# Milestone 7 Security Hardening Pass Review Report

**Date**: 2026-07-11T09:37:46+05:30  
**Reviewer**: Security Reviewer 2 (`reviewer_m7_2`)  

---

## Part 1: Quality Review

### Review Summary
**Verdict**: **APPROVE**

The security hardening implementation for Milestone 7 is robust, highly complete, and aligns perfectly with the requirements. It provides defense-in-depth:
1. **Application-level**: Input pre-scans for message length, keywords, PII (SSN, credit cards), and environment variable exfiltration patterns.
2. **Loop-level**: A secure RBAC interceptor within the agent loop that verifies `registry.is_allowed(fc.name, role)` prior to invoking any tool, logging unauthorized attempts securely without executing them.
3. **Registry-level**: A server-side role guard that enforces allowlists as the single source of truth, ignoring any untrusted frontend role declarations.
4. **Network-level / HTTP-level**: Middlewares for CORS, security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`), payload size limitations (1MB max), and sliding-window rate limiting.

All backend tests (150/150 passed) and frontend tests (7/7 passed, production build succeeded) verify the changes are regression-free and stable.

---

### Findings

#### [Minor] Finding 1: Unbounded Key Memory Growth in `RateLimitMiddleware`
- **Where**: `backend/app/main.py` (lines 81-103, inside `RateLimitMiddleware.dispatch`)
- **Why**: 
  When clearing expired timestamps, the code runs:
  ```python
  self.requests[ip] = [t for t in self.requests[ip] if now - t < window]
  ```
  If an IP makes requests and then stops, its key remains in the `self.requests` dictionary indefinitely with an empty list `[]`. Over long periods of operation with highly diverse client IPs, this will result in unbounded dictionary key growth and gradual memory leak.
- **Suggestion**:
  Remove the key if its timestamp list becomes empty:
  ```python
  self.requests[ip] = [t for t in self.requests[ip] if now - t < window]
  if not self.requests[ip]:
      del self.requests[ip]
  ```

#### [Minor] Finding 2: IP Spoofing via `X-Forwarded-For`
- **Where**: `backend/app/main.py` (lines 85-87, inside `RateLimitMiddleware.dispatch`)
- **Why**:
  The middleware parses the `X-Forwarded-For` header without verifying if the request came from a trusted reverse proxy:
  ```python
  forwarded = request.headers.get("X-Forwarded-For")
  if forwarded:
      ip = forwarded.split(",")[0].strip()
  ```
  If the backend is exposed directly to clients without an intermediate trusted proxy that strips or overrides this header, an attacker can bypass rate limiting by sending a random IP in `X-Forwarded-For`, or initiate a denial-of-service against an innocent user by spoofing their IP.
- **Suggestion**:
  Only trust `X-Forwarded-For` if the client host matches a whitelist of trusted proxies (e.g., Cloudflare IPs or internal load balancer subnets), or rely strictly on `request.client.host` if no proxy is used.

#### [Minor] Finding 3: Content-Length Bypass on Payload Limit
- **Where**: `backend/app/main.py` (lines 110-121, inside `PayloadSizeLimitMiddleware.dispatch`)
- **Why**:
  The middleware checks the `content-length` header:
  ```python
  content_length = request.headers.get("content-length")
  ```
  If an attacker sends a request with `Transfer-Encoding: chunked`, the `content-length` header is missing, bypassing the check and potentially allowing very large bodies to stream into memory/disk.
- **Suggestion**:
  While Starlette handles stream limits internally, it is safer to check the request stream's length dynamically if chunked transfer is expected, or reject chunked transfers if they are not needed by the API.

---

### Verified Claims

- **Security Headers are set** → verified via `test_security_headers` (TestClient GET /health checks headers) → **PASS**
- **Payload size limits block requests** → verified via `test_payload_size_limit` (temporarily setting limit to 15 bytes and sending standard request) → **PASS**
- **Rate limiting blocks requests** → verified via `test_rate_limiting` (sending 3 requests with limit 2/5s) → **PASS**
- **Jailbreak/PII/Env variables blocked in pre-scan** → verified via `test_prompt_injection_fallback_length`, `test_prompt_injection_fallback_keywords`, `test_prompt_injection_fallback_pii`, `test_prompt_injection_fallback_env_exfiltration` → **PASS**
- **RBAC guards block unauthorized tool calls** → verified via `test_rbac_guards_prevent_tool_calls` (both direct execution and agent loop response intercept) → **PASS**

---

### Coverage Gaps

- **Production Reverse Proxy / TLS Termination Setup** — risk level: **LOW** — recommendation: **Accept Risk** (out of scope for local simulator architecture; should be configured during infrastructure deployment).

---

### Unverified Items

- None. All security and loop claims were verified using the test suite.

---
---

## Part 2: Adversarial Review

### Challenge Summary
**Overall risk assessment**: **LOW**

The security design implements a multi-tier defense (pre-scan, model safety prompt instructions, loop-level RBAC intercept, registry-level RBAC enforcement). While individual layers have minor limitations (e.g. regex/keyword bypasses), the system as a whole degrades gracefully and successfully prevents unauthorized behavior.

---

### Challenges

#### [Low] Challenge 1: Obfuscation of Prompt Injection
- **Assumption challenged**: Pre-scan detects jailbreak keywords using basic exact-substring checks.
- **Attack scenario**: An attacker sends `i g n o r e  p r e v i o u s  i n s t r u c t i o n s` or base64-encoded instructions to bypass the `_is_unsafe` filter.
- **Blast radius**: The pre-scan filter is bypassed.
- **Mitigation**: The system prompt's instructions (`_INJECTION`) act as a secondary defense, instructing the model to reject role changes or instruction disclosure. If the model is somehow jailbroken and still attempts to call unauthorized tools, the loop-level RBAC interceptor and server-side registry block the call immediately.

---

### Stress Test Results

- **Attempt to call `recommend_action` as Fan role** → model attempts execution → loop-level intercept detects unauthorized tool → returned PermissionDenied error → **PASS**
- **Exceeding Rate Limit (3 requests within window)** → blocked with HTTP 429 → **PASS**
- **Payload size 2KB with 15B limit** → blocked with HTTP 413 → **PASS**

---

### Unchallenged Areas

- **Gemini API credential exposure / key management** — out of scope, relies on local environment environment variables (`GOOGLE_API_KEY`).
