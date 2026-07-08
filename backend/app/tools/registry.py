"""Tool registry: Gemini function declarations + Python handlers + role guards.

The registry is the single source of truth mapping a tool name to:
  - its `types.FunctionDeclaration` (sent to Gemini),
  - its Python handler (executed server-side),
  - the set of roles allowed to invoke it (enforced before execution).

Role enforcement happens here, server-side, on every call. The frontend role
value is never trusted for authorization.
"""
from __future__ import annotations

from typing import Any, Callable

from ..core.config import settings
from ..models.roles import Role, allowed_tools
from . import handlers

# JSON-schema parameter definitions for each tool.
_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_crowd_density": {
        "type": "object",
        "properties": {
            "zone_id": {"type": "string", "description": "Zone identifier, e.g. 'L-N', 'C-CL-S', 'U-E'."},
        },
        "required": ["zone_id"],
    },
    "get_all_zones_status": {"type": "object", "properties": {}},
    "find_route": {
        "type": "object",
        "properties": {
            "from_waypoint_id": {
                "type": "string",
                "description": "Start point: a zone_id (e.g. 'L-N'), gate_id (e.g. 'G-S'), concourse (e.g. 'C-L-N'), or waypoint_id (e.g. 'WP-G-N').",
            },
            "to_waypoint_id": {"type": "string", "description": "Destination, same format as from."},
            "accessible": {"type": "boolean", "description": "If true, only wheelchair-accessible routes (elevator/ramp/flat)."},
        },
        "required": ["from_waypoint_id", "to_waypoint_id"],
    },
    "lookup_schedule": {"type": "object", "properties": {}},
    "get_gate_status": {
        "type": "object",
        "properties": {
            "gate_id": {"type": "string", "description": "Optional gate id, e.g. 'G-N'. Omit for all gates."},
        },
    },
    "report_incident": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["medical", "congestion", "lost_child", "entry_bottleneck"]},
            "location": {"type": "string", "description": "Human-readable location, e.g. 'Lower North concourse'."},
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            "description": {"type": "string"},
        },
        "required": ["type", "location", "severity"],
    },
    "get_incidents": {"type": "object", "properties": {}},
    "recommend_action": {
        "type": "object",
        "properties": {
            "scenario": {"type": "string", "description": "Optional scenario description to focus the recommendation."},
        },
    },
    "translate_response": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to translate."},
            "target_language": {"type": "string", "description": "Target language, e.g. 'Spanish', 'Arabic', 'Japanese'."},
        },
        "required": ["text", "target_language"],
    },
    "search_knowledge": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language query over stadium FAQs and policies."},
            "k": {"type": "integer", "description": "Max results to return."},
        },
        "required": ["query"],
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
}


Handler = Callable[[dict, handlers.ToolContext], dict]


class ToolRegistry:
    def __init__(self) -> None:
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
        }

    # ---- declarations for Gemini ----
    def declarations_for_role(self, role: Role) -> list[Any]:
        """Return `types.FunctionDeclaration` objects for the tools a role may use."""
        from google.genai import types

        names = allowed_tools(role)
        decls = []
        for name in names:
            decls.append(
                types.FunctionDeclaration(
                    name=name,
                    description=_DESCRIPTIONS[name],
                    parameters_json_schema=_SCHEMAS[name],
                )
            )
        return decls

    def tool_names_for_role(self, role: Role) -> list[str]:
        return sorted(allowed_tools(role))

    # ---- execution with role guard ----
    def is_allowed(self, name: str, role: Role) -> bool:
        return name in allowed_tools(role)

    def execute(self, name: str, args: dict, role: Role, ctx: handlers.ToolContext) -> dict:
        if name not in self._handlers:
            return {"error": f"Unknown tool '{name}'."}
        if not self.is_allowed(name, role):
            return {"error": f"Role '{role.value}' is not authorized to call '{name}'."}
        try:
            return self._handlers[name](args or {}, ctx)
        except Exception as exc:  # surface structured errors back to the model
            return {"error": f"Tool '{name}' failed: {exc!s}"}


# A shared default registry.
registry = ToolRegistry()
