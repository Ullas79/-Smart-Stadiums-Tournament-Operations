"""Tool registry: Gemini function declarations + Python handlers + role guards.

The registry is the single source of truth mapping a tool name to:
  - its `types.FunctionDeclaration` (sent to Gemini),
  - its Python handler (executed server-side),
  - the set of roles allowed to invoke it (enforced before execution).

Role enforcement happens here, server-side, on every call. The frontend role
value is never trusted for authorization.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ..models.roles import Role, allowed_tools
from . import handlers

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field
from typing import Literal, Optional

class GetCrowdDensityArgs(BaseModel):
    zone_id: str = Field(..., description="Zone identifier, e.g. 'L-N', 'C-CL-S', 'U-E'.")

class GetAllZonesStatusArgs(BaseModel):
    pass

class FindRouteArgs(BaseModel):
    from_waypoint_id: str = Field(
        ...,
        description="Start point: a zone_id (e.g. 'L-N'), gate_id (e.g. 'G-S'), concourse (e.g. 'C-L-N'), or waypoint_id (e.g. 'WP-G-N')."
    )
    to_waypoint_id: str = Field(
        ...,
        description="Destination, same format as from."
    )
    accessible: bool = Field(
        False,
        description="If true, only wheelchair-accessible routes (elevator/ramp/flat)."
    )

class LookupScheduleArgs(BaseModel):
    pass

class GetGateStatusArgs(BaseModel):
    gate_id: Optional[str] = Field(
        None,
        description="Optional gate id, e.g. 'G-N'. Omit for all gates."
    )

class ReportIncidentArgs(BaseModel):
    type: Literal["medical", "congestion", "lost_child", "entry_bottleneck"]
    location: str = Field(
        ...,
        description="Human-readable location, e.g. 'Lower North concourse'."
    )
    severity: Literal["low", "medium", "high"]
    description: str = Field(
        "",
        description="Detailed description."
    )

class GetIncidentsArgs(BaseModel):
    pass

class RecommendActionArgs(BaseModel):
    scenario: Optional[str] = Field(
        None,
        description="Optional scenario description to focus the recommendation."
    )

class TranslateResponseArgs(BaseModel):
    text: str = Field(
        ...,
        description="The text to translate."
    )
    target_language: str = Field(
        ...,
        description="Target language, e.g. 'Spanish', 'Arabic', 'Japanese'."
    )

class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        ...,
        description="Natural-language query over stadium FAQs and policies."
    )
    k: Optional[int] = Field(
        None,
        description="Max results to return."
    )

class SetGateStatusArgs(BaseModel):
    gate_id: str = Field(
        ...,
        description="Gate identifier, e.g. 'G-N', 'G-S'."
    )
    status: Literal["open", "restricted", "closed"] = Field(
        ...,
        description="The new status of the gate."
    )

class DispatchStaffArgs(BaseModel):
    incident_id: str = Field(
        ...,
        description="The incident ID to dispatch staff to."
    )
    assigned_staff: str = Field(
        ...,
        description="Name/ID of the staff or volunteer to dispatch."
    )

class MitigateBottleneckArgs(BaseModel):
    zone_id: str = Field(
        ...,
        description="Zone identifier, e.g. 'L-N', 'C-N'."
    )
    strategy: Optional[str] = Field(
        None,
        description="Optional strategy/action taken, e.g. 'open_turnstiles', 'divert_flow'."
    )

_SCHEMAS_PYDANTIC: dict[str, type[BaseModel]] = {
    "get_crowd_density": GetCrowdDensityArgs,
    "get_all_zones_status": GetAllZonesStatusArgs,
    "find_route": FindRouteArgs,
    "lookup_schedule": LookupScheduleArgs,
    "get_gate_status": GetGateStatusArgs,
    "report_incident": ReportIncidentArgs,
    "get_incidents": GetIncidentsArgs,
    "recommend_action": RecommendActionArgs,
    "translate_response": TranslateResponseArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "set_gate_status": SetGateStatusArgs,
    "dispatch_staff": DispatchStaffArgs,
    "mitigate_bottleneck": MitigateBottleneckArgs,
}

def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for k, v in schema.items():
        if k in {"title", "additionalProperties", "defaultValue", "default"}:
            continue
        if isinstance(v, dict):
            cleaned[k] = _clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [_clean_schema(item) if isinstance(item, dict) else item for item in v]
        else:
            cleaned[k] = v

    if "anyOf" in cleaned:
        types = [t for t in cleaned["anyOf"] if isinstance(t, dict) and t.get("type") != "null"]
        if len(types) == 1:
            cleaned.update(types[0])
        elif len(types) > 1:
            cleaned.update(types[0])
        del cleaned["anyOf"]

    return cleaned

# Populate _SCHEMAS dynamically
_SCHEMAS: dict[str, dict[str, Any]] = {
    name: _clean_schema(model.model_json_schema())
    for name, model in _SCHEMAS_PYDANTIC.items()
},
}

_DESCRIPTIONS: dict[str, str] = {
    "get_crowd_density": "Get live crowd density for a single stadium zone.",
    "get_all_zones_status": "Get live crowd density for every zone, plus current match phase.",
    "find_route": "Find an indoor walking route between two points (gate, concourse, or zone), optionally wheelchair-accessible.",
    "lookup_schedule": "Get the match schedule and current phase for the World Cup Final.",
    "get_gate_status": "Get entry gate throughput, queue, and status (open/restricted/closed).",
    "report_incident": "Report a new on-ground incident (volunteers and organizers only).",
    "get_incidents": "List currently active incidents (volunteers and organizers only).",
    "recommend_action": "Get decision-support recommendations based on live operations (organizers only).",
    "translate_response": "Mark a text for translation into the fan's language; the assistant translates in its reply.",
    "search_knowledge": "Search stadium FAQs, policies, and amenity information.",
    "set_gate_status": "Update the status of a stadium entry/exit gate (staff only).",
    "dispatch_staff": "Dispatch a staff member or volunteer to an active incident (staff only).",
    "mitigate_bottleneck": "Mitigate crowd congestion in a zone by executing a flow redirection strategy (staff only).",
}


Handler = Callable[[dict[str, Any], handlers.ToolContext], dict[str, Any]]


class ToolRegistry:
    """Registry mapping tool names to schemas, handlers, and permitted roles."""

    def __init__(self) -> None:
        """Initializes the ToolRegistry with default handlers."""
        self._handlers: dict[str, Handler] = {
            "get_crowd_density": handlers.get_crowd_density,
            "get_all_zones_status": handlers.get_all_zones_status,
            "find_route": handlers.find_route,
            "lookup_schedule": handlers.lookup_schedule,
            "get_gate_status": handlers.get_gate_status,
            "report_incident": handlers.report_incident,
            "get_incidents": handlers.get_incidents,
            "recommend_action": handlers.recommend_action,
            "translate_response": handlers.translate_response,
            "search_knowledge": handlers.search_knowledge,
            "set_gate_status": handlers.set_gate_status,
            "dispatch_staff": handlers.dispatch_staff,
            "mitigate_bottleneck": handlers.mitigate_bottleneck,
        }

    # ---- declarations for Gemini ----
    def declarations_for_role(self, role: Role) -> list[Any]:
        """Return `types.FunctionDeclaration` objects for the tools a role may use.

        Args:
            role: The role to query tool declarations for.

        Returns:
            A list of Google GenAI SDK FunctionDeclaration objects.
        """
        from google.genai import types

        names = allowed_tools(role)
        decls = []
        for name in names:
            decls.append(
                types.FunctionDeclaration(
                    name=name,
                    description=_DESCRIPTIONS[name],
                    parameters=_SCHEMAS[name],
                )
            )
        return decls

    def tool_names_for_role(self, role: Role) -> list[str]:
        """Gets the sorted list of allowed tool names for the role.

        Args:
            role: The role to query.

        Returns:
            A list of tool name strings.
        """
        return sorted(allowed_tools(role))

    # ---- execution with role guard ----
    def is_allowed(self, name: str, role: Role) -> bool:
        """Checks if a tool is allowed to be executed by a specific role.

        Args:
            name: The name of the tool.
            role: The role attempting execution.

        Returns:
            True if allowed, False otherwise.
        """
        return name in allowed_tools(role)

    def execute(self, name: str, tool_args: dict[str, Any] | None, role: Role, ctx: handlers.ToolContext) -> dict[str, Any]:
        """Executes a tool handler with role authorization checks.

        Args:
            name: The name of the tool to execute.
            tool_args: The arguments dictionary for the tool (optional).
            role: The role executing the tool.
            ctx: The tool context.

        Returns:
            A dictionary representing the tool output or error.
        """
        if name not in self._handlers:
            return {"error": f"Unknown tool '{name}'."}
        if not self.is_allowed(name, role):
            return {"error": f"PermissionDenied: Role '{role.value}' is not authorized to call '{name}'."}
        try:
            actual_args = tool_args or {}
            return self._handlers[name](actual_args, ctx)
        except Exception as exc:
            logger.exception("Tool execution failed: %s", name)
            return {"error": f"Tool '{name}' failed: {exc!s}"}


# A shared default registry.
registry = ToolRegistry()

