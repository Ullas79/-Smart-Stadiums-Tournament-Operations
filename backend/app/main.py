"""FastAPI application factory.

Wires the simulator, knowledge store, tool context, Gemini client, and agent
together, and starts the simulator's asyncio tick task on startup.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Callable, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import ipaddress
import time
from collections import defaultdict

from .agent.loop import Agent
from .api.routes import router
from .core.config import settings
from .core.llm import make_llm_client
from .knowledge.store import KnowledgeStore
from .models.stadium import StadiumModel
from .simulator import fixtures
from .simulator.engine import StadiumSimulator
from .tools.handlers import ToolContext
from .tools.registry import registry as default_registry


def default_agent_builder(
    model: StadiumModel, sim: StadiumSimulator, knowledge: KnowledgeStore
) -> Agent:
    """Production wiring: real Gemini client (or offline fallback).

    Args:
        model: The loaded stadium model containing venue configurations.
        sim: The active stadium simulator engine.
        knowledge: The knowledge store for vector search.

    Returns:
        An initialized Agent instance configured with the tools and context.

    """
    ctx = ToolContext(simulator=sim, model=model, knowledge=knowledge)
    return Agent(client=make_llm_client(), registry=default_registry, ctx=ctx)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manages the lifecycle of the FastAPI application.

    Initializes the stadium model, starts the simulator engine, wires the agent,
    and manages cleanup on shutdown.

    Args:
        app: The FastAPI application instance.

    """
    model = fixtures.load_stadium_model()
    sim = StadiumSimulator(model=model, tick_seconds=settings.sim_tick_seconds, speed=settings.sim_speed)
    await sim.start()
    knowledge = KnowledgeStore()
    agent = app.state._agent_builder(model, sim, knowledge)

    app.state.simulator = sim
    app.state.agent = agent
    app.state.model = model
    try:
        yield
    finally:
        await sim.stop()





def is_trusted_ip(ip_str: str, trusted_list: list[str]) -> bool:
    """Checks if an IP address is in the list of trusted proxies/ranges."""
    if ip_str in trusted_list:
        return True
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

    def __init__(self, app: Any):
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


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that checks Content-Length to limit request payload size."""

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security hardening headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


def create_app(
    agent_builder: Callable[[StadiumModel, StadiumSimulator, KnowledgeStore], Agent] | None = None
) -> FastAPI:
    """Creates and configures the FastAPI application instance.

    Args:
        agent_builder: Optional custom agent builder function for testing.

    Returns:
        The configured FastAPI application instance.

    """
    app = FastAPI(
        title="Smart Stadiums Unified Assistant",
        description="GenAI assistant for the FIFA World Cup 2026 Final at MetLife Stadium.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {exc!s}"},
        )

    app.state._agent_builder = agent_builder or default_agent_builder
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(PayloadSizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.include_router(router)
    return app


app = create_app()

