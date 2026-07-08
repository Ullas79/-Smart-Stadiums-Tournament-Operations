"""FastAPI application factory.

Wires the simulator, knowledge store, tool context, Gemini client, and agent
together, and starts the simulator's asyncio tick task on startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.loop import Agent
from .api.routes import router
from .core.config import settings
from .core.gemini import make_client
from .knowledge.store import KnowledgeStore
from .simulator import fixtures
from .simulator.engine import StadiumSimulator
from .tools.handlers import ToolContext
from .tools.registry import ToolRegistry, registry as default_registry


from .agent.loop import Agent
from .api.routes import router
from .core.config import settings
from .core.gemini import make_client
from .knowledge.store import KnowledgeStore
from .simulator import fixtures
from .simulator.engine import StadiumSimulator
from .tools.handlers import ToolContext
from .tools.registry import ToolRegistry, registry as default_registry


def default_agent_builder(model, sim, knowledge):
    """Production wiring: real Gemini client (or offline fallback)."""
    ctx = ToolContext(simulator=sim, model=model, knowledge=knowledge)
    return Agent(client=make_client(), registry=default_registry, ctx=ctx)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


def create_app(agent_builder=None) -> FastAPI:
    app = FastAPI(
        title="Smart Stadiums Unified Assistant",
        description="GenAI assistant for the FIFA World Cup 2026 Final at MetLife Stadium.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state._agent_builder = agent_builder or default_agent_builder
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
