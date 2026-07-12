"""User roles and per-role tool allowlists.

The allowlist is the single source of truth for what each role may invoke.
It is enforced server-side in the tool registry BEFORE any handler runs;
the frontend role value is only a hint and is never trusted.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Represents the role of the user interacting with the assistant."""

    FAN = "fan"
    VOLUNTEER = "volunteer"
    ORGANIZER = "organizer"
    STAFF = "staff"



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
    Role.STAFF: frozenset(
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
            "set_gate_status",
            "dispatch_staff",
            "mitigate_bottleneck",
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
    Role.STAFF: (
        "On-ground facility and operations staff. Controls gate statuses, dispatches staff/volunteers, "
        "and mitigates crowd bottlenecks."
    ),
}


def allowed_tools(role: Role) -> frozenset[str]:
    """Gets the set of tools allowed for a given role.

    Args:
        role: The Role to look up.

    Returns:
        A frozenset of tool name strings.
    """
    return ROLE_TOOLS[role]

