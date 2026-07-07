"""Static stadium domain model.

Structurally faithful to MetLife Stadium (East Rutherford, NJ), host of the
FIFA World Cup 2026 Final. Fine-grained details (exact gate lettering,
concession placement) are illustrative where public data is ambiguous; see the
README fidelity statement.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LevelName(str, Enum):
    LOWER_BOWL = "Lower Bowl"
    CLUB_LEVEL = "Club Level"
    UPPER_BOWL = "Upper Bowl"
    SUITES = "Suites"


class EdgeKind(str, Enum):
    """Accessibility characteristics of a path edge."""

    STAIRS = "stairs"
    ESCALATOR = "escalator"
    ELEVATOR = "elevator"
    RAMP = "ramp"
    FLAT = "flat"


class Venue(BaseModel):
    name: str
    city: str
    state: str
    capacity: int
    latitude: float
    longitude: float
    notes: str = ""


class Level(BaseModel):
    name: LevelName
    description: str = ""


class Zone(BaseModel):
    """A seating group within a level."""

    zone_id: str
    name: str
    level: LevelName
    capacity: int
    nearest_gate_id: str
    concourse_id: str
    description: str = ""


class Gate(BaseModel):
    gate_id: str
    label: str
    served_zone_ids: list[str] = Field(default_factory=list)
    description: str = ""


class AmenityType(str, Enum):
    RESTROOM = "restroom"
    CONCESSION = "concession"
    FIRST_AID = "first_aid"
    RETAIL = "retail"
    ATM = "atm"
    WATER = "water"


class Amenity(BaseModel):
    amenity_id: str
    name: str
    type: AmenityType
    concourse_id: str
    waypoint_id: str
    description: str = ""


class Waypoint(BaseModel):
    waypoint_id: str
    name: str
    level: LevelName
    concourse_id: str = ""
    description: str = ""


class PathEdge(BaseModel):
    """A directed connection between two waypoints.

    `accessible` is True when the edge can be used by wheelchair users
    (elevator / ramp / flat). Stairs and escalator are not accessible.
    """

    from_id: str
    to_id: str
    kind: EdgeKind
    distance_m: float
    accessible: bool

    @classmethod
    def make(cls, from_id: str, to_id: str, kind: EdgeKind, distance_m: float) -> "PathEdge":
        return cls(
            from_id=from_id,
            to_id=to_id,
            kind=kind,
            distance_m=distance_m,
            accessible=kind in (EdgeKind.ELEVATOR, EdgeKind.RAMP, EdgeKind.FLAT),
        )


class ParkingLot(BaseModel):
    lot_id: str
    name: str
    nearest_gate_id: str
    capacity: int


class TransitNode(BaseModel):
    node_id: str
    name: str
    mode: str  # "rail" | "bus"
    nearest_gate_id: str
    description: str = ""


class StadiumModel(BaseModel):
    """The full static description of the venue, loaded from fixtures."""

    venue: Venue
    levels: list[Level]
    zones: list[Zone]
    gates: list[Gate]
    amenities: list[Amenity]
    waypoints: list[Waypoint]
    edges: list[PathEdge]
    parking: list[ParkingLot]
    transit: list[TransitNode]

    def zone_by_id(self, zone_id: str) -> Zone | None:
        return next((z for z in self.zones if z.zone_id == zone_id), None)

    def gate_by_id(self, gate_id: str) -> Gate | None:
        return next((g for g in self.gates if g.gate_id == gate_id), None)

    def waypoint_by_id(self, waypoint_id: str) -> Waypoint | None:
        return next((w for w in self.waypoints if w.waypoint_id == waypoint_id), None)
