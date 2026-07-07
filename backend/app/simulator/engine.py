"""MetLife Stadium dynamic simulator.

Ticks on an asyncio schedule, advancing the match clock and evolving crowd
density, gate throughput, incidents, and transit load according to the match
phase. The same query to the agent returns different answers as the phase
changes (arrival surge -> settle -> halftime concourse spike -> exit surge).
"""
from __future__ import annotations

import asyncio
import random

from ..models.state import (
    CrowdDensity,
    GateStatus,
    Incident,
    IncidentSeverity,
    MatchPhase,
    MatchState,
    StadiumSnapshot,
    TransitLoad,
)
from ..models.stadium import StadiumModel
from . import fixtures


def _phase_for(sim_time: float) -> MatchPhase:
    k = fixtures.KICKOFF_AT
    h = fixtures.HALFTIME_AT
    ft = fixtures.FULL_TIME_AT
    if sim_time < 0:
        return MatchPhase.PRE_OPEN
    if sim_time < k - 20 * 60:
        return MatchPhase.ARRIVAL
    if sim_time < k:
        return MatchPhase.PRE_KICKOFF
    if sim_time < h:
        return MatchPhase.LIVE
    if sim_time < h + 15 * 60:
        return MatchPhase.HALFTIME
    if sim_time < ft:
        return MatchPhase.LIVE
    if sim_time < ft + 45 * 60:
        return MatchPhase.FULL_TIME
    return MatchPhase.POST_EVENT


# Target occupancy fraction per phase. Halftime pushes people OUT of seats
# (lower) and INTO concourses (club) for food/restrooms.
_PHASE_SEAT_TARGET = {
    MatchPhase.PRE_OPEN: 0.0,
    MatchPhase.ARRIVAL: 0.35,
    MatchPhase.PRE_KICKOFF: 0.85,
    MatchPhase.LIVE: 0.92,
    MatchPhase.HALFTIME: 0.45,
    MatchPhase.FULL_TIME: 0.10,
    MatchPhase.POST_EVENT: 0.0,
}

_PHASE_CONCOURSE_BOOST = {
    MatchPhase.HALFTIME: 0.7,   # concourses packed
    MatchPhase.PRE_KICKOFF: 0.35,
    MatchPhase.ARRIVAL: 0.25,
    MatchPhase.FULL_TIME: 0.4,
}


class StadiumSimulator:
    """Holds and advances live stadium state. Thread-unsafe; run in one loop."""

    def __init__(self, model: StadiumModel | None = None, tick_seconds: int = 5, speed: int = 60) -> None:
        self.model = model or fixtures.load_stadium_model()
        self.tick_seconds = tick_seconds
        self.speed = speed  # sim seconds advanced per real second
        self.sim_time: float = -10 * 60  # start 10 min before gates open
        self._crowd: dict[str, CrowdDensity] = {}
        self._gates: dict[str, GateStatus] = {}
        self._incidents: list[Incident] = []
        self._transit: dict[str, TransitLoad] = {}
        self._rng = random.Random(42)
        self._task: asyncio.Task | None = None
        self._snapshot_cache: StadiumSnapshot | None = None
        self._initialize_state()

    # ---- initialization -------------------------------------------------
    def _initialize_state(self) -> None:
        for z in self.model.zones:
            self._crowd[z.zone_id] = CrowdDensity(
                zone_id=z.zone_id, occupancy=0, capacity=z.capacity, density=0.0
            )
        for g in self.model.gates:
            self._gates[g.gate_id] = GateStatus(
                gate_id=g.gate_id, label=g.label, status="open", throughput_per_min=0, queue_minutes=0.0
            )
        for t in self.model.transit:
            self._transit[t.node_id] = TransitLoad(
                node_id=t.node_id, name=t.name, mode=t.mode, congestion="low", wait_minutes=2.0
            )

    # ---- ticking --------------------------------------------------------
    def step(self, dt_sim_seconds: float) -> None:
        """Advance the simulation by dt_sim_seconds (deterministic-ish)."""
        self.sim_time += dt_sim_seconds
        phase = _phase_for(self.sim_time)
        self._update_crowd(phase, dt_sim_seconds)
        self._update_gates(phase)
        self._update_transit(phase)
        self._update_incidents(dt_sim_seconds)
        self._maybe_spawn_incident(phase)
        self._snapshot_cache = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.tick_seconds)
                self.step(self.tick_seconds * self.speed)
        except asyncio.CancelledError:
            pass

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # ---- state updates --------------------------------------------------
    def _is_concourse_zone(self, zone_id: str) -> bool:
        return zone_id.startswith("C-")

    def _update_crowd(self, phase: MatchPhase, dt: float) -> None:
        seat_target = _PHASE_SEAT_TARGET.get(phase, 0.0)
        concourse_boost = _PHASE_CONCOURSE_BOOST.get(phase, 0.0)
        # rate of approach toward target (faster during transitions)
        rate = 0.05 if phase in (MatchPhase.LIVE, MatchPhase.POST_EVENT) else 0.12
        for zid, cd in self._crowd.items():
            if self._is_concourse_zone(zid):
                target_frac = min(1.0, concourse_boost + 0.1)
            else:
                target_frac = seat_target
            target_occ = cd.capacity * target_frac
            cd.occupancy = int(cd.occupancy + (target_occ - cd.occupancy) * rate * (dt / 60.0))
            cd.occupancy = max(0, min(cd.capacity, cd.occupancy))
            cd.density = cd.occupancy / cd.capacity if cd.capacity else 0.0

    # CrowdDensity has no occupant() method; fix helper below.
    def _update_gates(self, phase: MatchPhase) -> None:
        # Throughput depends on phase: arrival/pre-kickoff high, halftime low,
        # full-time high (exits), live near zero.
        base = {
            MatchPhase.PRE_OPEN: 0,
            MatchPhase.ARRIVAL: 220,
            MatchPhase.PRE_KICKOFF: 320,
            MatchPhase.LIVE: 20,
            MatchPhase.HALFTIME: 40,
            MatchPhase.FULL_TIME: 300,
            MatchPhase.POST_EVENT: 60,
        }.get(phase, 0)
        for gid, gs in self._gates.items():
            tp = max(0, int(base + self._rng.gauss(0, base * 0.1))) if base else 0
            gs.throughput_per_min = tp
            # queue grows with throughput and nearby seat-zone density
            served = self.model.gate_by_id(gid)
            dense = 0.0
            if served:
                zs = [self._crowd[z] for z in served.served_zone_ids if z in self._crowd]
                dense = sum(z.density for z in zs) / len(zs) if zs else 0.0
            gs.queue_minutes = max(0.0, tp / 60.0 + dense * 6.0)
            # restrict a gate when its queue is bad
            gs.status = "restricted" if gs.queue_minutes > 12 else "open"

    def _update_transit(self, phase: MatchPhase) -> None:
        load = {
            MatchPhase.ARRIVAL: ("moderate", 8.0),
            MatchPhase.PRE_KICKOFF: ("high", 16.0),
            MatchPhase.LIVE: ("low", 3.0),
            MatchPhase.HALFTIME: ("low", 2.0),
            MatchPhase.FULL_TIME: ("high", 18.0),
            MatchPhase.POST_EVENT: ("moderate", 9.0),
            MatchPhase.PRE_OPEN: ("low", 2.0),
        }.get(phase, ("low", 2.0))
        for tn in self._transit.values():
            tn.congestion, tn.wait_minutes = load

    def _maybe_spawn_incident(self, phase: MatchPhase) -> None:
        # Higher chance during dense phases.
        p = {
            MatchPhase.PRE_KICKOFF: 0.15,
            MatchPhase.HALFTIME: 0.2,
            MatchPhase.FULL_TIME: 0.15,
            MatchPhase.ARRIVAL: 0.08,
            MatchPhase.LIVE: 0.04,
        }.get(phase, 0.02)
        active = [i for i in self._incidents if i.status == "active"]
        if len(active) >= 4 or self._rng.random() > p:
            return
        kind = self._rng.choice(["medical", "congestion", "lost_child", "entry_bottleneck"])
        zone = self._rng.choice(self.model.zones)
        sev = self._rng.choice(list(IncidentSeverity))
        inc = Incident(
            incident_id=f"INC-{int(self.sim_time)}-{self._rng.randint(100, 999)}",
            type=kind,
            location=zone.name,
            zone_id=zone.zone_id,
            severity=sev,
            status="active",
            created_at=self.sim_time,
            description=f"{kind.replace('_', ' ')} reported near {zone.name}.",
        )
        self._incidents.append(inc)

    def _update_incidents(self, dt: float) -> None:
        for inc in self._incidents:
            if inc.status != "active":
                continue
            lifetime = {
                IncidentSeverity.LOW: 8 * 60,
                IncidentSeverity.MEDIUM: 5 * 60,
                IncidentSeverity.HIGH: 3 * 60,
            }[inc.severity]
            if self.sim_time - inc.created_at >= lifetime:
                inc.status = "resolved"
                inc.resolved_at = self.sim_time
        # keep history bounded
        self._incidents = [i for i in self._incidents if i.status == "active" or (i.resolved_at and self.sim_time - i.resolved_at < 30 * 60)]

    # ---- public read API ------------------------------------------------
    def report_incident(self, type: str, location: str, severity: str, description: str = "") -> Incident:
        inc = Incident(
            incident_id=f"INC-MAN-{int(self.sim_time)}-{self._rng.randint(1000, 9999)}",
            type=type,
            location=location,
            severity=IncidentSeverity(severity),
            status="active",
            created_at=self.sim_time,
            description=description or f"{type.replace('_', ' ')} reported by staff at {location}.",
        )
        self._incidents.append(inc)
        self._snapshot_cache = None
        return inc

    def snapshot(self) -> StadiumSnapshot:
        if self._snapshot_cache is not None:
            return self._snapshot_cache
        match = fixtures.load_match_state(self.sim_time, _phase_for(self.sim_time))
        snap = StadiumSnapshot(
            venue_name=self.model.venue.name,
            match=match,
            crowd=[c.model_copy() for c in self._crowd.values()],
            gates=[g.model_copy() for g in self._gates.values()],
            incidents=[i.model_copy() for i in self._incidents if i.status == "active"],
            transit=[t.model_copy() for t in self._transit.values()],
        )
        self._snapshot_cache = snap
        return snap
