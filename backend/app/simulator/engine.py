"""MetLife Stadium dynamic simulator.

Ticks on an asyncio schedule, advancing the match clock and evolving crowd
density, gate throughput, incidents, and transit load according to the match
phase. The same query to the agent returns different answers as the phase
changes (arrival surge -> settle -> halftime concourse spike -> exit surge).
"""
from __future__ import annotations

import asyncio
import random
import threading
from typing import Any

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
    """Determines the MatchPhase based on simulator time in seconds.

    Args:
        sim_time: The current simulator time in seconds.

    Returns:
        The corresponding MatchPhase enum value.

    """
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
    """Holds and advances live stadium state.

    Ticks on an asyncio schedule to advance crowd dynamics, gate wait times,
    incident lifetimes, and transit congestion parameters based on match timeline.
    """

    def __init__(self, model: StadiumModel | None = None, tick_seconds: int = 5, speed: int = 60) -> None:
        """Initializes the StadiumSimulator.

        Args:
            model: The static stadium model venue configuration.
            tick_seconds: Real seconds between simulation ticks.
            speed: Speed factor (simulation seconds per real second).

        """
        self._lock = threading.RLock()
        self.model = model or fixtures.load_stadium_model()
        self.tick_seconds = tick_seconds
        self.speed = speed  # sim seconds advanced per real second
        self.sim_time: float = -10 * 60  # start 10 min before gates open
        self._crowd: dict[str, CrowdDensity] = {}
        self._gates: dict[str, GateStatus] = {}
        self._incidents: list[Incident] = []
        self._transit: dict[str, TransitLoad] = {}
        self._rng = random.Random(42)
        self._task: asyncio.Task[None] | None = None
        self._snapshot_cache: StadiumSnapshot | None = None
        self._active_scenarios: set[str] = set()
        self._gate_overrides: dict[str, str] = {}
        self._initialize_state()

    # ---- initialization -------------------------------------------------
    def _initialize_state(self) -> None:
        """Initializes crowd, gate, and transit states from the stadium model."""
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
        """Advance the simulation by dt_sim_seconds (deterministic-ish).

        Args:
            dt_sim_seconds: The number of simulation seconds to advance.

        """
        with self._lock:
            self.sim_time += dt_sim_seconds
            phase = _phase_for(self.sim_time)
            self._update_crowd(phase, dt_sim_seconds)
            self._update_gates(phase)
            self._update_transit(phase)
            self._update_incidents(dt_sim_seconds)
            self._maybe_spawn_incident(phase)
            self._snapshot_cache = None

    async def _run(self) -> None:
        """Run loop that ticks the simulator at the configured interval."""
        try:
            while True:
                await asyncio.sleep(self.tick_seconds)
                self.step(self.tick_seconds * self.speed)
        except asyncio.CancelledError:
            pass

    async def start(self) -> None:
        """Starts the background simulator task if not already running."""
        with self._lock:
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stops the background simulator task."""
        with self._lock:
            task = self._task
            if task:
                task.cancel()
                self._task = None
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass

    # ---- state updates --------------------------------------------------
    def _is_concourse_zone(self, zone_id: str) -> bool:
        """Checks if a zone ID corresponds to a concourse zone.

        Args:
            zone_id: The zone ID to check.

        Returns:
            True if the zone is a concourse, False otherwise.

        """
        return zone_id.startswith("C-")

    def _update_crowd(self, phase: MatchPhase, dt: float) -> None:
        """Updates crowd occupancies and densities towards targets for the phase.

        Args:
            phase: The current MatchPhase.
            dt: The simulation time delta in seconds.

        """
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

        if "concession_surge" in self._active_scenarios:
            if "C-N" in self._crowd:
                self._crowd["C-N"].occupancy = int(self._crowd["C-N"].capacity * 0.90)
                self._crowd["C-N"].density = 0.90

    def _update_gates(self, phase: MatchPhase) -> None:
        """Updates gate throughput and queue wait times based on phase and crowd density.

        Args:
            phase: The current MatchPhase.

        """
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
            override = self._gate_overrides.get(gid)
            if override == "closed":
                gs.status = "closed"
                gs.throughput_per_min = 0
                gs.queue_minutes = 99.0
                continue

            if override == "restricted":
                base_tp = base // 2
                tp = max(0, int(base_tp + self._rng.gauss(0, base_tp * 0.1))) if base_tp else 0
            else:
                tp = max(0, int(base + self._rng.gauss(0, base * 0.1))) if base else 0

            gs.throughput_per_min = tp

            served = self.model.gate_by_id(gid)
            dense = 0.0
            if served:
                total_density = 0.0
                count = 0
                for z in served.served_zone_ids:
                    cd = self._crowd.get(z)
                    if cd:
                        total_density += cd.density
                        count += 1
                dense = total_density / count if count > 0 else 0.0

            if override == "restricted":
                gs.status = "restricted"
                gs.queue_minutes = max(15.0, tp / 60.0 + dense * 12.0)
            elif override == "open":
                gs.status = "open"
                gs.queue_minutes = min(12.0, max(0.0, tp / 60.0 + dense * 6.0))
            else:
                gs.queue_minutes = max(0.0, tp / 60.0 + dense * 6.0)
                gs.status = "restricted" if gs.queue_minutes > 12 else "open"

        if "gate_malfunction" in self._active_scenarios:
            if "G-S" in self._gates and "G-S" not in self._gate_overrides:
                self._gates["G-S"].status = "restricted"
                self._gates["G-S"].queue_minutes = 45.0
                self._gates["G-S"].throughput_per_min = 0

    def _update_transit(self, phase: MatchPhase) -> None:
        """Updates transit nodes congestion levels and wait times based on phase.

        Args:
            phase: The current MatchPhase.

        """
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
        """Randomly spawns new active incidents with probabilities based on match phase.

        Args:
            phase: The current MatchPhase.

        """
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
        """Advances active incident lifetimes and resolves them after threshold.

        Args:
            dt: The simulation time delta in seconds.

        """
        for inc in self._incidents:
            if inc.status != "active":
                continue
            if inc.incident_id.startswith("INC-SCENARIO-"):
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
    def get_gate_ids(self) -> list[str]:
        """Returns a list of all gate IDs in a thread-safe manner.

        Returns:
            A list of gate ID strings.

        """
        with self._lock:
            return list(self._gates.keys())

    def get_zone_ids(self) -> list[str]:
        """Returns a list of all zone IDs in a thread-safe manner.

        Returns:
            A list of zone ID strings.

        """
        with self._lock:
            return list(self._crowd.keys())

    def report_incident(self, type: str, location: str, severity: str, description: str = "") -> Incident:
        """Manually reports a new incident.

        Args:
            type: The incident type (e.g. "medical", "lost_child").
            location: Description of the incident location.
            severity: Severity level (e.g. "low", "medium", "high").
            description: Optional detailed description of the incident.

        Returns:
            The newly created Incident object.

        """
        with self._lock:
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

    def trigger_scenario(self, scenario: str) -> Incident | None:
        """Injects a specific scenario incident or resets scenarios.

        Args:
            scenario: Name of the scenario ("gate_malfunction", "medical_emergency",
                      "concession_surge", "reset").

        Returns:
            The injected Incident object if applicable, otherwise None.

        Raises:
            ValueError: If the scenario name is invalid.

        """
        with self._lock:
            valid_scenarios = {"gate_malfunction", "medical_emergency", "concession_surge", "reset"}
            if scenario not in valid_scenarios:
                raise ValueError(f"Invalid scenario name: {scenario}")

            if scenario == "reset":
                self._active_scenarios.clear()
                self._incidents = [i for i in self._incidents if not i.incident_id.startswith("INC-SCENARIO-")]
                phase = _phase_for(self.sim_time)
                self._update_gates(phase)
                for zid, cd in self._crowd.items():
                    if phase == MatchPhase.PRE_OPEN:
                        target_frac = 0.0
                    elif self._is_concourse_zone(zid):
                        concourse_boost = _PHASE_CONCOURSE_BOOST.get(phase, 0.0)
                        target_frac = min(1.0, concourse_boost + 0.1)
                    else:
                        seat_target = _PHASE_SEAT_TARGET.get(phase, 0.0)
                        target_frac = seat_target
                    cd.occupancy = int(cd.capacity * target_frac)
                    cd.density = target_frac
                self._snapshot_cache = None
                return None

            elif scenario == "gate_malfunction":
                self._active_scenarios.add("gate_malfunction")
                if "G-S" in self._gates:
                    self._gates["G-S"].status = "restricted"
                    self._gates["G-S"].queue_minutes = 45.0
                    self._gates["G-S"].throughput_per_min = 0
                incident = Incident(
                    incident_id=f"INC-SCENARIO-GATE-{int(self.sim_time)}",
                    type="entry_bottleneck",
                    location="Gate 2 (South Gate)",
                    zone_id="G-S",
                    severity=IncidentSeverity.HIGH,
                    status="active",
                    created_at=self.sim_time,
                    description="Gate 2 turnstile malfunction: multiple scanner units offline. Queue wait times exceeding 20 minutes."
                )
                self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]
                self._incidents.append(incident)
                self._snapshot_cache = None
                return incident

            elif scenario == "medical_emergency":
                self._active_scenarios.add("medical_emergency")
                incident = Incident(
                    incident_id=f"INC-SCENARIO-MEDICAL-{int(self.sim_time)}",
                    type="medical",
                    location="Section 104 (Lower North)",
                    zone_id="L-N",
                    severity=IncidentSeverity.HIGH,
                    status="active",
                    created_at=self.sim_time,
                    description="Medical emergency reported at Section 104. Paramedics dispatched."
                )
                self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]
                self._incidents.append(incident)
                self._snapshot_cache = None
                return incident

            elif scenario == "concession_surge":
                self._active_scenarios.add("concession_surge")
                if "C-N" in self._crowd:
                    self._crowd["C-N"].occupancy = int(self._crowd["C-N"].capacity * 0.90)
                    self._crowd["C-N"].density = 0.90
                incident = Incident(
                    incident_id=f"INC-SCENARIO-CONCESSION-{int(self.sim_time)}",
                    type="congestion",
                    location="Concourse A (Club North)",
                    zone_id="C-N",
                    severity=IncidentSeverity.HIGH,
                    status="active",
                    created_at=self.sim_time,
                    description="Half-time concession surge reported at Concourse A. Volumetric queue times >15 minutes."
                )
                self._incidents = [i for i in self._incidents if i.incident_id != incident.incident_id]
                self._incidents.append(incident)
                self._snapshot_cache = None
                return incident
            return None

    def dispatch_incident(self, incident_id: str, assigned_staff: str) -> Incident:
        """Finds and updates the incident with the assigned staff.

        Args:
            incident_id: The ID of the incident to dispatch staff to.
            assigned_staff: The name/ID of the staff/volunteer dispatched.

        Returns:
            The updated Incident.

        Raises:
            KeyError: If the incident is not found.
            ValueError: If the incident is already resolved.

        """
        with self._lock:
            for i in self._incidents:
                if i.incident_id == incident_id:
                    if i.status == "resolved":
                        raise ValueError("Incident is already resolved")
                    i.assigned_staff = assigned_staff
                    i.description = f"{i.description} [Dispatched: {assigned_staff}]"
                    self._snapshot_cache = None
                    return i
            raise KeyError(f"Incident {incident_id} not found")

    def resolve_incident(self, incident_id: str) -> Incident:
        """Finds and resolves the incident.

        Args:
            incident_id: The ID of the incident to resolve.

        Returns:
            The updated Incident.

        Raises:
            KeyError: If the incident is not found.
            ValueError: If the incident is already resolved.

        """
        with self._lock:
            for i in self._incidents:
                if i.incident_id == incident_id:
                    if i.status == "resolved":
                        raise ValueError("Incident is already resolved")
                    i.status = "resolved"
                    i.resolved_at = self.sim_time
                    self._snapshot_cache = None
                    return i
            raise KeyError(f"Incident {incident_id} not found")

    def set_gate_status(self, gate_id: str, status: str) -> GateStatus:
        """Finds the gate, updates its status, and adjusts throughput/queues.

        Args:
            gate_id: The ID of the gate.
            status: The status to set.

        Returns:
            The updated GateStatus.

        Raises:
            KeyError: If the gate is not found.
            ValueError: If the status is invalid.

        """
        with self._lock:
            if gate_id not in self._gates:
                raise KeyError(f"Gate {gate_id} not found")
            status = status.lower()
            if status not in {"open", "restricted", "closed"}:
                raise ValueError(f"Invalid status: {status}")

            gs = self._gates[gate_id]
            gs.status = status
            self._gate_overrides[gate_id] = status

            if status == "closed":
                gs.throughput_per_min = 0
                gs.queue_minutes = 99.0
            elif status == "open":
                if gs.throughput_per_min == 0:
                    gs.throughput_per_min = 150
                gs.queue_minutes = max(0.0, gs.queue_minutes / 2.0)
            elif status == "restricted":
                gs.throughput_per_min = max(0, int(gs.throughput_per_min * 0.5))
                gs.queue_minutes = max(15.0, gs.queue_minutes * 1.5)

            self._snapshot_cache = None
            return gs

    def mitigate_bottleneck(self, zone_id: str, strategy: str | None = None) -> dict[str, Any]:
        """Reduces crowd density/occupancy in a zone to mitigate bottlenecks.

        Args:
            zone_id: The ID of the zone to mitigate.
            strategy: Optional mitigation strategy description.

        Returns:
            A dictionary containing the details of the mitigation.

        Raises:
            KeyError: If the zone is not found.

        """
        with self._lock:
            if zone_id not in self._crowd:
                raise KeyError(f"Zone {zone_id} not found")

            cd = self._crowd[zone_id]
            old_occupancy = cd.occupancy
            old_density = cd.density

            cd.occupancy = int(cd.occupancy * 0.75)
            cd.density = cd.occupancy / cd.capacity if cd.capacity else 0.0

            self._snapshot_cache = None
            return {
                "zone_id": zone_id,
                "strategy": strategy or "standard_flow_diversion",
                "old_occupancy": old_occupancy,
                "new_occupancy": cd.occupancy,
                "old_density": round(old_density, 3),
                "new_density": round(cd.density, 3),
            }

    def snapshot(self) -> StadiumSnapshot:
        """Generates a snapshot of the current simulator state.

        Returns:
            The current StadiumSnapshot.

        """
        with self._lock:
            match: MatchState = fixtures.load_match_state(self.sim_time, _phase_for(self.sim_time))
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

