## Challenge Summary

**Overall risk assessment**: MEDIUM

While the core server-side role guards are robust and successfully block unauthorized tool calls (fail-safe), the middleware protections and input safety scanners can be empirically bypassed via simple evasion and protocol manipulation techniques.

---

## Challenges

### [Medium] Challenge 1: IP Rate Limiting Bypass via `X-Forwarded-For`

- **Assumption challenged**: Assumes the `X-Forwarded-For` header is a trustworthy representation of the client's actual IP address.
- **Attack scenario**: A client rotates the IP in the `X-Forwarded-For` header (e.g. `X-Forwarded-For: 1.1.1.1`, `X-Forwarded-For: 1.1.1.2`) on every request. The rate limiting middleware tracks these as separate clients, allowing the attacker to completely bypass rate limits.
- **Blast radius**: Complete rate-limiting bypass, exposing the API to Denial of Service (DoS) and resource exhaustion.
- **Mitigation**: Avoid trusting the `X-Forwarded-For` header unless the backend is running behind a trusted reverse proxy (like Nginx or Cloudflare) configured to strip/override untrusted headers, or use the client's socket address directly.

### [Medium] Challenge 2: Payload Size Limit Bypass via Omitted Content-Length

- **Assumption challenged**: Assumes all incoming requests contain a valid `Content-Length` header.
- **Attack scenario**: A client sends a large payload using `Transfer-Encoding: chunked` or completely omits the `Content-Length` header. Since `PayloadSizeLimitMiddleware` only inspects the `Content-Length` header value, the request bypasses the size limit check and is fully parsed by FastAPI.
- **Blast radius**: Bypassing size limits, leading to potential memory exhaustion or Denial of Service (DoS) on large uploads.
- **Mitigation**: Wrap the request body stream or use server-level limits (e.g. in Uvicorn or a reverse proxy) to enforce a hard maximum on raw bytes received, regardless of headers.

### [Low] Challenge 3: Input Safety Scan Evasion (Jailbreak / PII / Env)

- **Assumption challenged**: Assumes exact keyword matching and rigid regexes are sufficient to block jailbreaks, PII leaks, and environment variable exfiltrations.
- **Attack scenario**: An attacker uses slight lexical or formatting variations:
  - *"ignore previous instruction"* (singular) instead of *"ignore previous instructions"*
  - *"dump system_prompt"* (underscore) instead of *"dump system prompt"*
  - *"123.45.6789"* (dots) instead of *"123-45-6789"* (dashes)
  - *"what is $API_KEY"* (no braces) instead of *"${API_KEY}"*
- **Blast radius**: Low, because the system prompt contains a secondary line of defense instructing the model to reject jailbreaks and not disclose prompt info. However, relying purely on keyword checks for safety is fragile.
- **Mitigation**: Use semantic safety classification (e.g., Llama Guard) or a classifier model to inspect inputs rather than fragile exact keyword matches.

### [High] Challenge 4: Missing Server-Side RBAC on REST Endpoints

- **Assumption challenged**: Assumes security controls only need to be enforced inside the agent's tool execution loop.
- **Attack scenario**: A malicious FAN user directly targets the REST API endpoints like `/api/incidents/dispatch` or `/api/incidents/resolve` instead of talking to the agent. Because these routes contain no authentication, JWT verification, or role checks, they execute immediately.
- **Blast radius**: Unauthorized manipulation of live tournament operations (resolving incidents or dispatching personnel without permission).
- **Mitigation**: Implement authentication middleware or dependency injection (e.g., OAuth2/JWT) on all operational REST endpoints.

---

## Stress Test Results

Adversarial stress-testing was executed using `pytest` at `backend/tests/test_adversarial_security.py`:

- **Jailbreak Keyword Evasion** → Send slightly modified jailbreak keywords (e.g. `ignore previous instruction`) → Scanner bypassed (runs Gemini agent) → **PASS**
- **PII Leak Evasion** → Send PII with alternative separators (e.g. `123.45.6789`) → Scanner bypassed (runs Gemini agent) → **PASS**
- **Env Exfiltration Evasion** → Send env query without braces (e.g. `$API_KEY`) → Scanner bypassed (runs Gemini agent) → **PASS**
- **Rate Limit IP Spoofing** → Spoof `X-Forwarded-For` header on consecutive requests → Bypasses 429 limit (returns 200) → **PASS**
- **Payload Size Limit Bypass** → Omit `Content-Length` header on large request → Bypasses 413 check (returns 200) → **PASS**
- **RBAC Server-side Tool Enforcement** → FAN role attempts to execute STAFF tools → Blocked with `PermissionDenied` error → **PASS**

---

## Unchallenged Areas

- **Gemini API Safety Filters** — Out of scope (controlled by Google's API, not local implementation code).
- **CORS Configuration Validation** — Not fully tested with cross-origin automated requests, only basic middleware configuration verified.
