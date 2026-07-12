"""Dynamic stadium state produced by the simulator."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from .stadium import Gate, Zone


class MatchPhase(str, Enum):
    """Represents the current phase of the match timeline."""

    PRE_OPEN = "pre_open"          # before gates open
    ARRIVAL = "arrival"            # gates open, fans arriving
    PRE_KICKOFF = "pre_kickoff"    # close to kickoff, peak arrival
    LIVE = "live"                  # match in play, fans in seats
    HALFTIME = "halftime"          # concourse spike
    FULL_TIME = "full_time"        # exit surge
    POST_EVENT = "post_event"      # winding down


class CrowdDensity(BaseModel):
    """Represents crowd occupancy, capacity, and calculated density for a zone."""

    zone_id: str
    occupancy: int
    capacity: int
    density: float  # 0.0..1.0 (occupancy / capacity)

    def level(self) -> str:
        """Determines the crowd density level category.

        Returns:
            A string indicating "low", "moderate", or "high" density.
        """
        if self.density < 0.5:
            return "low"
        if self.density < 0.85:
            return "moderate"
        return "high"


class GateStatus(BaseModel):
    """Represents the operational status and queue metrics for a stadium gate."""

    gate_id: str
    label: str
    status: str  # "open" | "restricted" | "closed"
    throughput_per_min: int
    queue_minutes: float


class IncidentSeverity(str, Enum):
    """Represents the severity level of an incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Incident(BaseModel):
    """Represents an active or resolved incident in the stadium."""

    incident_id: str
    type: str  # "medical" | "congestion" | "lost_child" | "entry_bottleneck"
    location: str
    zone_id: str = ""
    severity: IncidentSeverity
    status: str = "active"  # "active" | "resolved"
    created_at: float  # sim seconds
    resolved_at: float | None = None
    description: str = ""
    assigned_staff: str | None = None


class TransitLoad(BaseModel):
    """Represents the congestion and wait times for transit nodes."""

    node_id: str
    name: str
    mode: str
    congestion: str  # "low" | "moderate" | "high"
    wait_minutes: float


class MatchState(BaseModel):
    """Represents the match configuration and timing details."""

    match_id: str
    name: str
    phase: MatchPhase
    sim_time: float  # seconds since sim start
    kickoff_at: float
    halftime_at: float
    full_time_at: float


class StadiumSnapshot(BaseModel):
    """A point-in-time view of the whole stadium, consumed by the agent,
    the API, and the dashboard."""

    venue_name: str
    match: MatchState
    crowd: list[CrowdDensity] = Field(default_factory=list)
    gates: list[GateStatus] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)
    transit: list[TransitLoad] = Field(default_factory=list)

    _crowd_by_zone: dict[str, CrowdDensity] = PrivateAttr(default_factory=dict)
    _gates_by_id: dict[str, GateStatus] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._crowd_by_zone = {c.zone_id: c for c in self.crowd}
        self._gates_by_id = {g.gate_id: g for g in self.gates}

    def crowd_by_zone(self, zone_id: str) -> CrowdDensity | None:
        """Retrieves the CrowdDensity object for the specified zone ID.

        Args:
            zone_id: The ID of the zone to find.

        Returns:
            The CrowdDensity object if found, otherwise None.
        """
        return self._crowd_by_zone.get(zone_id)

    def gate_by_id(self, gate_id: str) -> GateStatus | None:
        """Retrieves the GateStatus object for the specified gate ID.

        Args:
            gate_id: The ID of the gate to find.

        Returns:
            The GateStatus object if found, otherwise None.
        """
        return self._gates_by_id.get(gate_id)

    def summary(self) -> str:
        """Short text summary injected into the agent system prompt.

        Returns:
            A text summary summarizing the venue, phase, sim time, density, and active incidents.
        """
        active = [i for i in self.incidents if i.status == "active"]
        high = [c for c in self.crowd if c.level() == "high"]
        return (
            f"Venue: {self.venue_name}. Match phase: {self.match.phase.value}. "
            f"Sim time: {int(self.match.sim_time)}s. "
            f"High-density zones: {len(high)}/{len(self.crowd)}. "
            f"Active incidents: {len(active)}."
        )

    def static_for(self, zone: Zone, gate: Gate | None) -> str:
        """Generates a static description string for a zone and optional gate.

        Args:
            zone: The Zone model.
            gate: The optional Gate model.

        Returns:
            A string description.
        """
        return f"Zone {zone.name} (level {zone.level.value}, cap {zone.capacity})."

