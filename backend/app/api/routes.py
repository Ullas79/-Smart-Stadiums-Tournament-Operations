"""FastAPI routes: /chat, /state, /role, /health.

The agent + simulator + tool context live on the app state (set up in
`app.main.create_app`). Tests may override `app.state.agent` with a fake that
exposes the same `run(message, role, history, language)` interface.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.chat import ChatRequest, ChatResponse, RoleInfo, RolesResponse
from ..models.roles import ROLE_DESCRIPTIONS, Role, allowed_tools

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/role", response_model=RolesResponse)
def get_roles() -> RolesResponse:
    return RolesResponse(
        roles=[
            RoleInfo(role=r, description=ROLE_DESCRIPTIONS[r], tools=sorted(allowed_tools(r)))
            for r in Role
        ]
    )


@router.get("/state")
def get_state(request: Request):
    sim = request.app.state.simulator
    return sim.snapshot().model_dump()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    agent = request.app.state.agent
    result = agent.run(message=req.message, role=req.role, history=req.history, language=req.language)
    return ChatResponse(
        reply=result.reply,
        role=req.role,
        language=req.language,
        tool_events=result.tool_events,
        snapshot_summary=result.snapshot_summary,
    )
