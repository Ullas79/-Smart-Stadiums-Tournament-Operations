# Milestone 7 Security Hardening Challenge Report

**Date**: 2026-07-11
**Challenger ID**: challenger_m7_1
**Overall Risk Assessment**: HIGH

---

## Challenge Summary

The Milestone 7 security hardening implementation introduces several key mitigations: input safety scanning (jailbreaks, PII, env exfiltration), server-side RBAC guards on tool execution, rate-limiting, and payload size restriction middlewares. 

While these controls function correctly under standard conditions, they are vulnerable to direct bypass attacks due to design limitations in pattern matching, header trust, and endpoint routing. Most notably, restricted write actions (incident dispatch and resolution) are exposed as open REST API routes with zero authentication or role guards, bypassing the chatbot's server-side tool registry entirely.

---

## Challenges

### [Critical] Challenge 1: Server-Side RBAC Bypass via Direct API Endpoints
- **Assumption challenged**: The assumption that restricting tool declarations and enforcing role guards inside the chatbot (`ToolRegistry.is_allowed`) is sufficient to prevent unauthorized users from mutating stadium state.
- **Attack scenario**: A user with the `FAN` role cannot trigger the `dispatch_staff` or `resolve_incident` tool via the assistant chat. However, the backend exposes direct REST endpoints `/api/incidents/dispatch` and `/api/incidents/resolve` which perform these exact mutations. Because these routes do not enforce any role check, authentication, or validation of the request's origin, any unauthenticated client can call them to dispatch staff or resolve active incidents.
- **Blast radius**: High. Attackers can manipulate tournament operations, close out medical emergencies prematurely, or redirect staff to arbitrary locations without authorization.
- **Mitigation**: Add authentication middleware or token verification to all REST routes, and validate that the user's role (extracted from a secure session/JWT) permits operations like dispatch and resolution.

### [High] Challenge 2: Middleware Rate Limit Bypass via X-Forwarded-For Spoofing
- **Assumption challenged**: The assumption that checking the `X-Forwarded-For` header is a safe way to identify client IPs for rate-limiting.
- **Attack scenario**: The `RateLimitMiddleware` extracts the first IP address from the `X-Forwarded-For` header if present. An attacker can generate a randomized IP address for each request and send it in the `X-Forwarded-For` header. The middleware treats each request as originating from a unique client, bypassing the sliding window rate limit completely.
- **Blast radius**: Medium-High. Attackers can perform Denial of Service (DoS) attacks or scrape the stadium FAQ database/agent models continuously without restriction.
- **Mitigation**: Trust `X-Forwarded-For` only if the application is behind a trusted reverse proxy that overrides this header. Otherwise, fall back to `request.client.host` or validate the proxy chain.

### [Medium] Challenge 3: Payload Size Limit Bypass via Chunked Encoding (Missing Content-Length)
- **Assumption challenged**: The assumption that checking the `Content-Length` header is sufficient to limit request payload sizes.
- **Attack scenario**: The `PayloadSizeLimitMiddleware` reads the `Content-Length` header to determine request size. If a client transmits the payload using `Transfer-Encoding: chunked` and omits the `Content-Length` header, the middleware skips the size check entirely.
- **Blast radius**: Medium. Attackers can upload large quantities of text/data to the endpoint, potentially causing high memory consumption, high processing latency, or server exhaustion (DoS).
- **Mitigation**: Instead of only checking the header, wrap the request stream in a limited stream reader that throws an error if the actual byte count read from the body exceeds `settings.max_payload_size_bytes`.

### [Medium] Challenge 4: Input Safety Scan Bypass via Substring & Regex Evacuation
- **Assumption challenged**: The assumption that exact keyword lists and fixed regular expressions can fully filter jailbreaks, PII, and environment variables.
- **Attack scenario**:
  1. **Env Exfiltration**: The scanner blocks `${VAR}` and `%VAR%`. A user requesting `$google_api_key` or `$GOOGLE_API_KEY` (without curly braces) or using indirection (`getattr(os, 'environ')`) bypasses the scanner.
  2. **Jailbreaks**: The scanner checks for specific lowercase phrases like `"system prompt"`. A user requesting `"system\nprompt"` (using newlines), `"system_prompt"` (using underscores), or singular variations like `"ignore previous instruction"` bypasses the check.
  3. **PII**: The scanner looks for specific SSN and credit card patterns with space or hyphen separators. Separators like dots (`123.45.6789`) or underscores (`123_45_6789`) bypass the check.
- **Blast radius**: Medium. Sensitive information (API keys, SSNs) can be leaked if they bypass the scanner and are subsequently processed by the LLM, or the LLM could be jailbroken to override guidelines.
- **Mitigation**: Use semantic/LLM-based classification for prompt safety or use robust, pre-built sanitization libraries rather than custom literal substring/regex matches.

---

## Stress Test Results

The bypasses were verified empirically using pytest suite `tests/test_challenger_m7.py` and `tests/test_adversarial_security.py`. All tests passed, confirming the viability of the bypasses:

- **Jailbreak keywords with newlines/separators** → Expected to bypass static scanner → Actual: Bypassed scanner and invoked agent → **PASS**
- **PII with dot/underscore separators** → Expected to bypass static scanner → Actual: Bypassed scanner and invoked agent → **PASS**
- **Env exfiltration with `$VAR` (no braces)** → Expected to bypass static scanner → Actual: Bypassed scanner and invoked agent → **PASS**
- **Direct `/api/incidents/dispatch` POST** → Expected to allow unauthorized mutation → Actual: Successfully dispatched incident without role check → **PASS**
- **X-Forwarded-For Spoofing** → Expected to bypass rate limiting → Actual: Permitted unlimited requests under tight limit → **PASS**
- **Chunked Transfer (No Content-Length)** → Expected to bypass payload size limit → Actual: Passed middleware check with large body → **PASS**

---

## Unchallenged Areas

- **Gemini Client Tool Declaration Pruning**: Did not test bypassing the tool registry at the LLM level by manually modifying the local SDK tool declarations (since we are restricted to runtime API interactions and test client environments).
- **Network/CORS policy headers**: Checked headers are present (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`), but did not perform browser-level iframe embedding tests.
