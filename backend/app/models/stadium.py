"""Static stadium domain model.

Structurally faithful to MetLife Stadium (East Rutherford, NJ), host of the
FIFA World Cup 2026 Final. Fine-grained details (exact gate lettering,
concession placement) are illustrative where public data is ambiguous; see the
README fidelity statement.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr


class LevelName(str, Enum):
    """Represents stadium level names."""

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
    """Represents static stadium metadata and capacity."""

    name: str
    city: str
    state: str
    capacity: int
    latitude: float
    longitude: float
    notes: str = ""


class Level(BaseModel):
    """Represents a stadium level configuration."""

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
    """Represents a physical entrance gate in the stadium."""

    gate_id: str
    label: str
    served_zone_ids: list[str] = Field(default_factory=list)
    description: str = ""


class AmenityType(str, Enum):
    """Represents types of stadium amenities available to fans."""

    RESTROOM = "restroom"
    CONCESSION = "concession"
    FIRST_AID = "first_aid"
    RETAIL = "retail"
    ATM = "atm"
    WATER = "water"


class Amenity(BaseModel):
    """Represents a specific amenity (e.g. food stand, restroom) in the stadium."""

    amenity_id: str
    name: str
    type: AmenityType
    concourse_id: str
    waypoint_id: str
    description: str = ""


class Waypoint(BaseModel):
    """Represents a navigation node within the stadium."""

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
        """Creates a PathEdge, automatically determining accessibility.

        Args:
            from_id: The starting waypoint ID.
            to_id: The ending waypoint ID.
            kind: The connection type (e.g. stairs, elevator).
            distance_m: The distance in meters.

        Returns:
            A new PathEdge instance.

        """
        return cls(
            from_id=from_id,
            to_id=to_id,
            kind=kind,
            distance_m=distance_m,
            accessible=kind in (EdgeKind.ELEVATOR, EdgeKind.RAMP, EdgeKind.FLAT),
        )


class ParkingLot(BaseModel):
    """Represents a parking lot associated with the stadium."""

    lot_id: str
    name: str
    nearest_gate_id: str
    capacity: int


class TransitNode(BaseModel):
    """Represents a transit connection node (e.g. rail or bus station)."""

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

    _zones_by_id: dict[str, Zone] = PrivateAttr(default_factory=dict)
    _gates_by_id: dict[str, Gate] = PrivateAttr(default_factory=dict)
    _waypoints_by_id: dict[str, Waypoint] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._zones_by_id = {z.zone_id: z for z in self.zones}
        self._gates_by_id = {g.gate_id: g for g in self.gates}
        self._waypoints_by_id = {w.waypoint_id: w for w in self.waypoints}

    def zone_by_id(self, zone_id: str) -> Zone | None:
        """Finds a Zone by its unique ID.

        Args:
            zone_id: The ID of the zone to find.

        Returns:
            The Zone instance if found, otherwise None.

        """
        return self._zones_by_id.get(zone_id)

    def gate_by_id(self, gate_id: str) -> Gate | None:
        """Finds a Gate by its unique ID.

        Args:
            gate_id: The ID of the gate to find.

        Returns:
            The Gate instance if found, otherwise None.

        """
        return self._gates_by_id.get(gate_id)

    def waypoint_by_id(self, waypoint_id: str) -> Waypoint | None:
        """Finds a Waypoint by its unique ID.

        Args:
            waypoint_id: The ID of the waypoint to find.

        Returns:
            The Waypoint instance if found, otherwise None.

        """
        return self._waypoints_by_id.get(waypoint_id)

