"""User roles and per-role tool allowlists.

The allowlist is the single source of truth for what each role may invoke.
It is enforced server-side in the tool registry BEFORE any handler runs;
the frontend role value is only a hint and is never trusted.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    FAN = "fan"
    VOLUNTEER = "volunteer"
    ORGANIZER = "organizer"


# Tool names each role is permitted to call. Additive: a role sees its own tools
# only. Organizers are the most privileged; fans the least.
ROLE_TOOLS: dict[Role, frozenset[str]] = {
    Role.FAN: frozenset(
        {
            "get_crowd_density",
            "get_all_zones_status",
            "find_route",
            "lookup_schedule",
            "get_gate_status",
            "translate_response",
            "search_knowledge",
        }
    ),
    Role.VOLUNTEER: frozenset(
        {
            "get_crowd_density",
            "get_all_zones_status",
            "find_route",
            "lookup_schedule",
            "get_gate_status",
            "report_incident",
            "get_incidents",
            "translate_response",
            "search_knowledge",
        }
    ),
    Role.ORGANIZER: frozenset(
        {
            "get_crowd_density",
            "get_all_zones_status",
            "find_route",
            "lookup_schedule",
            "get_gate_status",
            "report_incident",
            "get_incidents",
            "recommend_action",
            "translate_response",
            "search_knowledge",
        }
    ),
}


ROLE_DESCRIPTIONS: dict[Role, str] = {
    Role.FAN: (
        "A spectator attending the match. Wants navigation, schedule, amenities, "
        "FAQs, and help in their own language."
    ),
    Role.VOLUNTEER: (
        "On-ground volunteer staff. Helps fans, reports and views incidents, "
        "and needs situational awareness of crowd and gates."
    ),
    Role.ORGANIZER: (
        "Tournament operations controller. Needs the full live operational picture, "
        "decision-support recommendations, and authority to manage incidents and crowd flow."
    ),
}


def allowed_tools(role: Role) -> frozenset[str]:
    return ROLE_TOOLS[role]
