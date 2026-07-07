"""Static MetLife Stadium fixtures (FIFA World Cup 2026 Final).

Structurally faithful to the real venue: capacity, bowl levels, concourses,
gate taxonomy, parking lots, and the NJ Transit Meadowlands rail connection.
Exact gate lettering and concession placement are illustrative where public
data is ambiguous. See the README fidelity statement.
"""
from __future__ import annotations

from ..models.stadium import (
    Amenity,
    AmenityType,
    EdgeKind,
    Gate,
    Level,
    LevelName,
    ParkingLot,
    PathEdge,
    StadiumModel,
    TransitNode,
    Venue,
    Waypoint,
    Zone,
)
from ..models.state import MatchState

# ---- Match timeline (sim seconds from sim start = gates open) ----
# The Final: gates open at t=0, kickoff at 60min, halftime at 105min,
# full-time at 150min. Values are in seconds for the sim clock.
KICKOFF_AT = 60 * 60
HALFTIME_AT = 105 * 60
FULL_TIME_AT = 150 * 60


def load_venue() -> Venue:
    return Venue(
        name="MetLife Stadium",
        city="East Rutherford",
        state="New Jersey",
        capacity=82500,
        latitude=40.8128,
        longitude=-74.0742,
        notes="Host of the 2026 FIFA World Cup Final.",
    )


def load_levels() -> list[Level]:
    return [
        Level(name=LevelName.LOWER_BOWL, description="Field-level seating, closest to the pitch."),
        Level(name=LevelName.CLUB_LEVEL, description="Mid-level concourse with premium amenities."),
        Level(name=LevelName.UPPER_BOWL, description="Upper-tier seating."),
        Level(name=LevelName.SUITES, description="Private suites and hospitality boxes."),
    ]


# 12 zones: four per bowl tier (North/South/East/West stands).
def load_zones() -> list[Zone]:
    specs = [
        # (zone_id, name, level, capacity, gate_id, concourse_id)
        ("L-N", "Lower North", LevelName.LOWER_BOWL, 9000, "G-N", "C-L-N"),
        ("L-S", "Lower South", LevelName.LOWER_BOWL, 9000, "G-S", "C-L-S"),
        ("L-E", "Lower East", LevelName.LOWER_BOWL, 7000, "G-E", "C-L-E"),
        ("L-W", "Lower West", LevelName.LOWER_BOWL, 7000, "G-W", "C-L-W"),
        ("C-N", "Club North", LevelName.CLUB_LEVEL, 6000, "G-N", "C-CL-N"),
        ("C-S", "Club South", LevelName.CLUB_LEVEL, 6000, "G-S", "C-CL-S"),
        ("C-E", "Club East", LevelName.CLUB_LEVEL, 5000, "G-E", "C-CL-E"),
        ("C-W", "Club West", LevelName.CLUB_LEVEL, 5000, "G-W", "C-CL-W"),
        ("U-N", "Upper North", LevelName.UPPER_BOWL, 8000, "G-N", "C-U-N"),
        ("U-S", "Upper South", LevelName.UPPER_BOWL, 8000, "G-S", "C-U-S"),
        ("U-E", "Upper East", LevelName.UPPER_BOWL, 6250, "G-E", "C-U-E"),
        ("U-W", "Upper West", LevelName.UPPER_BOWL, 6250, "G-W", "C-U-W"),
    ]
    return [
        Zone(
            zone_id=zid,
            name=name,
            level=level,
            capacity=cap,
            nearest_gate_id=gate,
            concourse_id=conc,
        )
        for zid, name, level, cap, gate, conc in specs
    ]


def load_gates() -> list[Gate]:
    return [
        Gate(gate_id="G-N", label="North Gate", served_zone_ids=["L-N", "C-N", "U-N"]),
        Gate(gate_id="G-S", label="South Gate", served_zone_ids=["L-S", "C-S", "U-S"]),
        Gate(gate_id="G-E", label="East Gate", served_zone_ids=["L-E", "C-E", "U-E"]),
        Gate(gate_id="G-W", label="West Gate", served_zone_ids=["L-W", "C-W", "U-W"]),
    ]


def load_amenities() -> list[Amenity]:
    """One of each amenity type per concourse quadrant (representative)."""
    am = []
    for conc in ["C-L-N", "C-L-S", "C-L-E", "C-L-W", "C-CL-N", "C-CL-S"]:
        wp = f"WP-{conc}"
        am.append(Amenity(amenity_id=f"RR-{conc}", name=f"Restroom {conc}", type=AmenityType.RESTROOM, concourse_id=conc, waypoint_id=wp))
        am.append(Amenity(amenity_id=f"CC-{conc}", name=f"Concession {conc}", type=AmenityType.CONCESSION, concourse_id=conc, waypoint_id=wp))
        am.append(Amenity(amenity_id=f"WT-{conc}", name=f"Water Station {conc}", type=AmenityType.WATER, concourse_id=conc, waypoint_id=wp))
    # First-aid and retail at main concourses only
    am.append(Amenity(amenity_id="FA-N", name="First Aid North", type=AmenityType.FIRST_AID, concourse_id="C-L-N", waypoint_id="WP-C-L-N"))
    am.append(Amenity(amenity_id="FA-S", name="First Aid South", type=AmenityType.FIRST_AID, concourse_id="C-L-S", waypoint_id="WP-C-L-S"))
    am.append(Amenity(amenity_id="RT-N", name="Team Store North", type=AmenityType.RETAIL, concourse_id="C-L-N", waypoint_id="WP-C-L-N"))
    am.append(Amenity(amenity_id="RT-S", name="Team Store South", type=AmenityType.RETAIL, concourse_id="C-L-S", waypoint_id="WP-C-L-S"))
    am.append(Amenity(amenity_id="AT-N", name="ATM North", type=AmenityType.ATM, concourse_id="C-L-N", waypoint_id="WP-C-L-N"))
    return am


def load_waypoints() -> list[Waypoint]:
    wps = []
    # Gate plazas
    for g in ["G-N", "G-S", "G-E", "G-W"]:
        wps.append(Waypoint(waypoint_id=f"WP-{g}", name=f"{g} Plaza", level=LevelName.LOWER_BOWL))
    # Concourse nodes
    concourses = [
        "C-L-N", "C-L-S", "C-L-E", "C-L-W",
        "C-CL-N", "C-CL-S", "C-CL-E", "C-CL-W",
        "C-U-N", "C-U-S", "C-U-E", "C-U-W",
    ]
    level_map = {
        "C-L-": LevelName.LOWER_BOWL,
        "C-CL-": LevelName.CLUB_LEVEL,
        "C-U-": LevelName.UPPER_BOWL,
    }
    for c in concourses:
        lvl = next(v for k, v in level_map.items() if c.startswith(k))
        wps.append(Waypoint(waypoint_id=f"WP-{c}", name=f"Concourse {c}", level=lvl, concourse_id=c))
    # Zone seats (one waypoint per zone)
    for zid in [z.zone_id for z in load_zones()]:
        wps.append(Waypoint(waypoint_id=f"WP-Z-{zid}", name=f"Seats {zid}", level=LevelName.LOWER_BOWL))
    return wps


def load_edges() -> list[PathEdge]:
    """Indoor graph: gate plaza -> concourse -> seats, plus vertical connectors
    between bowl tiers (escalator + elevator for accessibility)."""
    e: list[PathEdge] = []

    def add(a: str, b: str, kind: EdgeKind, dist: float) -> None:
        e.append(PathEdge.make(f"WP-{a}", f"WP-{b}", kind, dist))
        e.append(PathEdge.make(f"WP-{b}", f"WP-{a}", kind, dist))

    # Gate plaza -> lower concourse (one per direction)
    add("G-N", "C-L-N", EdgeKind.FLAT, 60)
    add("G-S", "C-L-S", EdgeKind.FLAT, 60)
    add("G-E", "C-L-E", EdgeKind.FLAT, 60)
    add("G-W", "C-L-W", EdgeKind.FLAT, 60)

    # Lower concourse -> seats
    for zid in ["L-N", "L-S", "L-E", "L-W"]:
        add(f"C-{zid}", f"Z-{zid}", EdgeKind.STAIRS, 30)

    # Vertical connectors: lower <-> club <-> upper (escalator + elevator)
    for side in ["N", "S", "E", "W"]:
        add(f"C-L-{side}", f"C-CL-{side}", EdgeKind.ESCALATOR, 40)
        add(f"C-L-{side}", f"C-CL-{side}", EdgeKind.ELEVATOR, 45)
        add(f"C-CL-{side}", f"C-U-{side}", EdgeKind.ESCALATOR, 40)
        add(f"C-CL-{side}", f"C-U-{side}", EdgeKind.ELEVATOR, 45)
        add(f"C-CL-{side}", f"Z-C-{side}", EdgeKind.STAIRS, 25)
        add(f"C-U-{side}", f"Z-U-{side}", EdgeKind.STAIRS, 25)

    return e


def load_parking() -> list[ParkingLot]:
    return [
        ParkingLot(lot_id="P-N", name="Lot N", nearest_gate_id="G-N", capacity=5000),
        ParkingLot(lot_id="P-S", name="Lot S", nearest_gate_id="G-S", capacity=5000),
        ParkingLot(lot_id="P-E", name="Lot E", nearest_gate_id="G-E", capacity=4000),
        ParkingLot(lot_id="P-W", name="Lot W", nearest_gate_id="G-W", capacity=4000),
    ]


def load_transit() -> list[TransitNode]:
    return [
        TransitNode(
            node_id="T-RAIL",
            name="Meadowlands Rail Station (NJ Transit)",
            mode="rail",
            nearest_gate_id="G-S",
            description="Secaucus Junction connection to the sports complex.",
        ),
        TransitNode(
            node_id="T-BUS",
            name="Coach USA Bus Terminal",
            mode="bus",
            nearest_gate_id="G-E",
            description="Express bus service from NYC Port Authority.",
        ),
    ]


def load_stadium_model() -> StadiumModel:
    return StadiumModel(
        venue=load_venue(),
        levels=load_levels(),
        zones=load_zones(),
        gates=load_gates(),
        amenities=load_amenities(),
        waypoints=load_waypoints(),
        edges=load_edges(),
        parking=load_parking(),
        transit=load_transit(),
    )


def load_match_state(sim_time: float = 0.0, phase=None) -> MatchState:
    from ..models.state import MatchPhase

    return MatchState(
        match_id="WC2026-FINAL",
        name="FIFA World Cup 2026 Final",
        phase=phase or MatchPhase.PRE_OPEN,
        sim_time=sim_time,
        kickoff_at=KICKOFF_AT,
        halftime_at=HALFTIME_AT,
        full_time_at=FULL_TIME_AT,
    )
