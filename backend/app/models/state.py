"""Dynamic stadium state produced by the simulator."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .stadium import Gate, LevelName, Zone


class MatchPhase(str, Enum):
    PRE_OPEN = "pre_open"          # before gates open
    ARRIVAL = "arrival"            # gates open, fans arriving
    PRE_KICKOFF = "pre_kickoff"    # close to kickoff, peak arrival
    LIVE = "live"                  # match in play, fans in seats
    HALFTIME = "halftime"          # concourse spike
    FULL_TIME = "full_time"        # exit surge
    POST_EVENT = "post_event"      # winding down


class CrowdDensity(BaseModel):
    zone_id: str
    occupancy: int
    capacity: int
    density: float  # 0.0..1.0 (occupancy / capacity)

    def level(self) -> str:
        if self.density < 0.5:
            return "low"
        if self.density < 0.8:
            return "moderate"
        return "high"


class GateStatus(BaseModel):
    gate_id: str
    label: str
    status: str  # "open" | "restricted" | "closed"
    throughput_per_min: int
    queue_minutes: float


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Incident(BaseModel):
    incident_id: str
    type: str  # "medical" | "congestion" | "lost_child" | "entry_bottleneck"
    location: str
    zone_id: str = ""
    severity: IncidentSeverity
    status: str = "active"  # "active" | "resolved"
    created_at: float  # sim seconds
    resolved_at: float | None = None
    description: str = ""


class TransitLoad(BaseModel):
    node_id: str
    name: str
    mode: str
    congestion: str  # "low" | "moderate" | "high"
    wait_minutes: float


class MatchState(BaseModel):
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

    def crowd_by_zone(self, zone_id: str) -> CrowdDensity | None:
        return next((c for c in self.crowd if c.zone_id == zone_id), None)

    def summary(self) -> str:
        """Short text summary injected into the agent system prompt."""
        active = [i for i in self.incidents if i.status == "active"]
        high = [c for c in self.crowd if c.level() == "high"]
        return (
            f"Venue: {self.venue_name}. Match phase: {self.match.phase.value}. "
            f"Sim time: {int(self.match.sim_time)}s. "
            f"High-density zones: {len(high)}/{len(self.crowd)}. "
            f"Active incidents: {len(active)}."
        )

    def static_for(self, zone: Zone, gate: Gate | None) -> str:
        return f"Zone {zone.name} (level {zone.level.value}, cap {zone.capacity})."
