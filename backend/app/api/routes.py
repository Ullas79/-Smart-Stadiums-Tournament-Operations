"""FastAPI routes: /chat, /state, /role, /health.

The agent + simulator + tool context live on the app state (set up in
`app.main.create_app`). Tests may override `app.state.agent` with a fake that
exposes the same `run(message, role, history, language)` interface.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from ..models.chat import ChatRequest, ChatResponse, RoleInfo, RolesResponse
from ..models.roles import ROLE_DESCRIPTIONS, Role, allowed_tools
from .auth import verify_role_token

router = APIRouter()


class ScenarioRequest(BaseModel):
    """Schema for triggering a simulator scenario."""

    scenario: str


@router.post("/simulator/scenario")
def trigger_scenario_route(req: ScenarioRequest, request: Request, auth_role: str = Depends(verify_role_token)) -> dict[str, Any]:
    """Endpoint to trigger a simulated stadium scenario.

    Args:
        req: The scenario request containing the scenario name.
        request: The FastAPI request instance holding application state.
        auth_role: The role extracted from the API token.

    Returns:
        A dictionary indicating success and details of the triggered incident.

    Raises:
        HTTPException: If the scenario name is invalid or simulation failed.

    """
    if auth_role != "organizer":
        raise HTTPException(status_code=403, detail="Only organizers can trigger scenarios")
        
    sim = request.app.state.simulator
    valid_scenarios = {"gate_malfunction", "medical_emergency", "concession_surge", "reset"}
    if req.scenario not in valid_scenarios:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {req.scenario}")

    try:
        incident = sim.trigger_scenario(req.scenario)
        return {
            "status": "success",
            "incident": incident.model_dump() if incident is not None else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health")
def health() -> dict[str, str]:
    """Simple API health check endpoint.

    Returns:
        A dictionary with the health status.

    """
    return {"status": "ok"}


@router.get("/role", response_model=RolesResponse)
def get_roles() -> RolesResponse:
    """Retrieves all roles, descriptions, and their permitted tools.

    Returns:
        A RolesResponse detailing each Role.

    """
    return RolesResponse(
        roles=[
            RoleInfo(role=r, description=ROLE_DESCRIPTIONS[r], tools=sorted(allowed_tools(r)))
            for r in Role
        ]
    )


@router.get("/state")
def get_state(request: Request) -> dict[str, Any]:
    """Retrieves the current live stadium state snapshot.

    Args:
        request: The FastAPI request instance holding application state.

    Returns:
        A dictionary representing the serialized StadiumSnapshot.

    """
    sim = request.app.state.simulator
    return sim.snapshot().model_dump()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, auth_role: str = Depends(verify_role_token)) -> ChatResponse:
    """Handles an assistant chat request.

    Sends the user message to the agent loop and returns the agent response.

    Args:
        req: The ChatRequest containing message, role, and history.
        request: The FastAPI request instance holding application state.
        auth_role: The role extracted from the API token.

    Returns:
        A ChatResponse containing the agent's reply and any tool events.

    """
    if req.role != auth_role:
        raise HTTPException(status_code=403, detail=f"Cannot execute actions as {req.role.value} with {auth_role} token")
        
    try:
        agent = request.app.state.agent
        result = agent.run(message=req.message, role=req.role, history=req.history, language=req.language)
        return ChatResponse(
            reply=result.reply,
            role=req.role,
            language=req.language,
            tool_events=result.tool_events,
            snapshot_summary=result.snapshot_summary,
        )
    except Exception as exc:
        sim = request.app.state.simulator
        return ChatResponse(
            reply=f"Service Notice: {exc!s}",
            role=req.role,
            language=req.language,
            tool_events=[],
            snapshot_summary=sim.snapshot().summary(),
        )


class DispatchRequest(BaseModel):
    incident_id: str
    volunteer_id: str
    assigned_staff: str | None = None


class ResolveRequest(BaseModel):
    incident_id: str


@router.post("/api/incidents/dispatch", status_code=200)
def dispatch_incident_route(req: DispatchRequest, request: Request) -> dict[str, Any]:
    """Dispatches staff/volunteers to an incident."""
    sim = request.app.state.simulator
    try:
        staff = req.assigned_staff or req.volunteer_id
        updated = sim.dispatch_incident(req.incident_id, staff)
        return {
            "status": "success",
            "incident": updated.model_dump()
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Register dispatch aliases programmatically to avoid duplicate decorators and OpenAPI clashing
for path in ["/incidents/dispatch", "/api/incident/dispatch", "/incident/dispatch"]:
    router.add_api_route(
        path,
        dispatch_incident_route,
        methods=["POST"],
        status_code=200,
        include_in_schema=False,
    )


@router.post("/api/incidents/resolve", status_code=200)
def resolve_incident_route(req: ResolveRequest, request: Request) -> dict[str, Any]:
    """Resolves an incident."""
    sim = request.app.state.simulator
    try:
        updated = sim.resolve_incident(req.incident_id)
        return {
            "status": "success",
            "incident": updated.model_dump()
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Register resolve aliases programmatically to avoid duplicate decorators and OpenAPI clashing
for path in ["/incidents/resolve", "/api/incident/resolve", "/incident/resolve"]:
    router.add_api_route(
        path,
        resolve_incident_route,
        methods=["POST"],
        status_code=200,
        include_in_schema=False,
    )

