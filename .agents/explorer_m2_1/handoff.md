# Phase 2 Security Hardening Analysis Report: Rate Limiter and Payload Size Limit

## Summary
This report analyzes two backend security hardening requirements:
1. **Rate Limiter X-Forwarded-For Spoofing**: Clients can spoof their IP address by specifying arbitrary values in the `X-Forwarded-For` header, bypassing the IP-based rate limiter.
2. **Payload Size Limit Bypass**: Clients can bypass payload size checks by omitting the `Content-Length` header (e.g., using `Transfer-Encoding: chunked`).

We present the root causes, logic chains, and concrete, actionable fix strategies to resolve both vulnerabilities in `backend/app/main.py` and `backend/app/core/config.py`.

---

## 1. Observation

### Rate Limiter IP Spoofing
In `backend/app/main.py` (lines 83-88):
```python
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
```
The middleware unconditionally extracts and trusts the IP address from the `X-Forwarded-For` header without checking the direct client host IP.

This vulnerability is verified by `test_rate_limiting_ip_spoofing_bypass` in `backend/tests/test_adversarial_security.py` (lines 135-162):
```python
            # 1. First request with IP 1.1.1.1
            headers1 = {"X-Forwarded-For": "1.1.1.1"}
            r1 = client.get("/health", headers=headers1)
            assert r1.status_code == 200

            # 2. Second request with same IP 1.1.1.1 should fail with 429
            r2 = client.get("/health", headers=headers1)
            assert r2.status_code == 429

            # 3. Third request with spoofed IP 2.2.2.2 should bypass the limit and return 200
            headers2 = {"X-Forwarded-For": "2.2.2.2"}
            r3 = client.get("/health", headers=headers2)
            assert r3.status_code == 200
```

### Payload Size Limit Bypass
In `backend/app/main.py` (lines 109-121):
```python
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > settings.max_payload_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Payload Too Large"},
                    )
            except ValueError:
                pass
        return await call_next(request)
```
The middleware only performs size validation if the `Content-Length` header is present. If the header is missing, the request body is not validated at all.

This vulnerability is verified by `test_payload_size_missing_content_length_bypass` in `backend/tests/test_adversarial_security.py` (lines 198-211):
```python
            # Construct a request with no Content-Length header but a large body size
            scope = {
                "type": "http",
                "method": "POST",
                "path": "/chat",
                "headers": [], # No Content-Length header!
            }
            req = Request(scope=scope)
            
            # Run the middleware dispatch
            import asyncio
            response = asyncio.run(middleware.dispatch(req, dummy_call_next))
            # It should bypass the middleware and return 200 (passed) because content-length is missing
            assert response.status_code == 200
```

---

## 2. Logic Chain

### Rate Limiter IP Spoofing
1. The `RateLimitMiddleware` checks if the `X-Forwarded-For` header is present in the request.
2. If it is present, the middleware parses the first IP in the list and sets `ip` to that value.
3. Because the middleware performs no validation of `request.client.host` (the immediate connection peer), any external client can inject an arbitrary IP in the `X-Forwarded-For` header.
4. The middleware tracks requests against this injected IP. A client rotating the spoofed header value will never trigger rate limits.
5. **Conclusion**: To prevent spoofing, the middleware must only trust the `X-Forwarded-For` header if the direct client (`request.client.host`) matches a list of configured, trusted proxy IP ranges.

### Payload Size Limit Bypass
1. The `PayloadSizeLimitMiddleware` reads `request.headers.get("content-length")`.
2. If `content-length` is absent, the middleware does not perform any checks and forwards the request to the ASGI application.
3. According to HTTP protocol specifications, clients can send data without a `Content-Length` header by using `Transfer-Encoding: chunked`.
4. As a result, a client can stream an arbitrarily large body, consuming CPU/Memory and bypassing the maximum payload size protection.
5. **Conclusion**: To prevent bypasses, the middleware must wrap the ASGI `receive` function of the request to monitor the incoming byte stream dynamically, raising an error (returning 413) if the total received bytes exceed the configured maximum payload size.

---

## 3. Caveats
- **Proxy Configuration**: If a reverse proxy (e.g. AWS ALB, Nginx, Cloudflare) is present, the deployer *must* configure the `trusted_proxies` environment variable. If it is not configured, the default behavior will be to ignore `X-Forwarded-For` entirely and rate limit based on the immediate peer IP (`request.client.host`), which could cause all requests from the proxy to share the same rate limiting bucket.
- **Client IP in Test Client**: In standard FastAPI `TestClient` tests, the client host resolves to `"testclient"`. Thus, during test suite runs, `"testclient"` must be added to the trusted proxy list if we want to simulate proxy rate limiting, or we must test the behavior of the middleware under trusted/untrusted client conditions.

---

## 4. Conclusion & Actionable Fix Strategy

### Part A: Configuration Settings (`backend/app/core/config.py`)
Add a new setting `trusted_proxies` to support configured trusted IP ranges or individual IPs.

**Before:**
```python
    # Security
    max_payload_size_bytes: int = 1048576  # 1MB
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
```

**After:**
```python
    # Security
    max_payload_size_bytes: int = 1048576  # 1MB
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    trusted_proxies: str = "127.0.0.1"  # Comma-separated list of trusted proxy IPs/CIDRs

    @property
    def trusted_proxies_list(self) -> list[str]:
        """Parses the configured trusted proxies into a list of strings.

        Returns:
            A list of IP addresses or CIDR ranges.
        """
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]
```

### Part B: Rate Limiter Spoofing Fix (`backend/app/main.py`)
Add helper logic to validate that the client IP is a trusted proxy before extracting `X-Forwarded-For`.

**Before:**
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Zero-dependency IP-based sliding window rate-limiting middleware."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
```

**After:**
Add `import ipaddress` at the top. Add helper `is_trusted_ip` and modify `RateLimitMiddleware.dispatch`:
```python
import ipaddress
from fastapi import HTTPException  # ensure imported

def is_trusted_ip(ip_str: str, trusted_list: list[str]) -> bool:
    """Checks if an IP address is in the list of trusted proxies/ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for pattern in trusted_list:
        try:
            if "/" in pattern:
                if ip in ipaddress.ip_network(pattern, strict=False):
                    return True
            else:
                if ip == ipaddress.ip_address(pattern):
                    return True
        except ValueError:
            continue
    return False

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Zero-dependency IP-based sliding window rate-limiting middleware."""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_host = request.client.host if request.client else "unknown"
        ip = client_host

        trusted = settings.trusted_proxies_list
        if trusted and is_trusted_ip(client_host, trusted):
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()

        now = time.time()
        window = settings.rate_limit_window_seconds
        limit = settings.rate_limit_requests

        # Clear expired timestamps
        self.requests[ip] = [t for t in self.requests[ip] if now - t < window]

        if len(self.requests[ip]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
            )

        self.requests[ip].append(now)
        return await call_next(request)
```

### Part C: Payload Size Limit Bypass Fix (`backend/app/main.py`)
Wrap the ASGI `_receive` method to intercept and measure incoming body chunks dynamically.

**Before:**
```python
class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that checks Content-Length to limit request body size."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > settings.max_payload_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Payload Too Large"},
                    )
            except ValueError:
                pass
        return await call_next(request)
```

**After:**
```python
class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that checks Content-Length and incoming request body stream to limit size."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > settings.max_payload_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Payload Too Large"},
                    )
            except ValueError:
                pass

        # Protect against chunked transfer encoding or spoofed Content-Length
        # by wrapping the ASGI receive channel to monitor actual bytes read.
        max_size = settings.max_payload_size_bytes
        total_received = 0
        original_receive = request._receive
        limit_exceeded = False

        async def custom_receive():
            nonlocal total_received, limit_exceeded
            message = await original_receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                total_received += len(body)
                if total_received > max_size:
                    limit_exceeded = True
                    raise HTTPException(
                        status_code=413,
                        detail="Payload Too Large",
                    )
            return message

        request._receive = custom_receive

        try:
            return await call_next(request)
        except HTTPException as exc:
            if exc.status_code == 413 or limit_exceeded:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload Too Large"},
                )
            raise exc
```

---

## 5. Verification Method

To verify these changes:
1. Run the test suite:
   ```bash
   cd backend
   .venv\Scripts\python -m pytest
   ```
2. Update the adversarial security tests in `backend/tests/test_adversarial_security.py` so they verify that rate limiter spoofing and payload size bypass are **successfully blocked**.

### Updated Test for Rate Limiting Spoofing
In `backend/tests/test_adversarial_security.py` (lines 135-162), update the test to:
```python
def test_rate_limiting_ip_spoofing_prevented():
    app = create_app()
    
    # Configure tight rate limit: 1 request per 10 seconds
    original_requests = settings.rate_limit_requests
    original_window = settings.rate_limit_window_seconds
    original_proxies = settings.trusted_proxies
    
    # Do NOT trust "testclient" proxy (default)
    settings.rate_limit_requests = 1
    settings.rate_limit_window_seconds = 10
    settings.trusted_proxies = "127.0.0.1" # client host is "testclient", not in this list

    try:
        with TestClient(app) as client:
            # 1. First request with IP 1.1.1.1 in X-Forwarded-For
            r1 = client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
            assert r1.status_code == 200

            # 2. Second request with same IP should fail with 429
            r2 = client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
            assert r2.status_code == 429

            # 3. Third request with different IP 2.2.2.2 in X-Forwarded-For should STILL fail with 429
            # because the rate limiter ignores X-Forwarded-For from untrusted "testclient"
            r3 = client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"})
            assert r3.status_code == 429
    finally:
        settings.rate_limit_requests = original_requests
        settings.rate_limit_window_seconds = original_window
        settings.trusted_proxies = original_proxies
```

### Updated Test for Payload Size Limit Bypass
In `backend/tests/test_adversarial_security.py` (lines 164-215), update the assertion for missing Content-Length:
```python
            # ...
            # Run the middleware dispatch
            import asyncio
            
            # Since our custom_receive throws HTTPException, the middleware dispatch should catch it
            # and return a 413 JSONResponse, NOT bypass and return a 200 JSONResponse.
            response = asyncio.run(middleware.dispatch(req, dummy_call_next))
            assert response.status_code == 413
            # ...
```
