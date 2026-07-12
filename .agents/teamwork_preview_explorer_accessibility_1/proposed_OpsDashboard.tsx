import { memo, useEffect, useRef, useState } from "react";
import type { StadiumSnapshot } from "../types";
import "./OpsDashboard.css";

interface Props {
  snapshot: StadiumSnapshot | null;
}

function densityColor(level: string): string {
  if (level === "high") return "#ef4444";
  if (level === "moderate") return "#f59e0b";
  return "#22c55e";
}

function phaseLabel(phase: string): string {
  return phase.replace(/_/g, " ");
}

export const OpsDashboard = memo(
  function OpsDashboard({ snapshot }: Props) {
    const prevSnapshotRef = useRef<StadiumSnapshot | null>(null);
    const [liveAnnouncement, setLiveAnnouncement] = useState("");

    // Detect critical dynamic changes to announce via live region (WCAG 4.1.3 Compliance)
    useEffect(() => {
      if (!snapshot) return;
      const prev = prevSnapshotRef.current;
      if (prev) {
        const alerts: string[] = [];

        // 1. Check for new crowd density spikes > 85%
        snapshot.crowd.forEach((c) => {
          const prevZone = prev.crowd.find((pz) => pz.zone_id === c.zone_id);
          const prevDensity = prevZone ? prevZone.density : 0;
          if (c.density > 0.85 && prevDensity <= 0.85) {
            alerts.push(`Alert: ${c.zone_name} crowd density is critically high at ${Math.round(c.density * 100)}%!`);
          }
        });

        // 2. Check for newly spawned active incidents
        snapshot.incidents.forEach((i) => {
          const prevInc = prev.incidents.find((pi) => pi.incident_id === i.incident_id);
          if (!prevInc) {
            alerts.push(`New active incident: ${i.type.replace(/_/g, " ")} (${i.severity} severity) reported at ${i.location}.`);
          }
        });

        // 3. Check for gate status transitions
        snapshot.gates.forEach((g) => {
          const prevGate = prev.gates.find((pg) => pg.gate_id === g.gate_id);
          if (prevGate && prevGate.status !== g.status) {
            alerts.push(`Gate ${g.label} status changed to ${g.status}.`);
          }
        });

        if (alerts.length > 0) {
          setLiveAnnouncement(alerts.join(" "));
        }
      }
      prevSnapshotRef.current = snapshot;
    }, [snapshot]);

    if (!snapshot) {
      return (
        <div className="dashboard" role="status" aria-live="polite">
          Loading live state…
        </div>
      );
    }

    const { match, crowd, gates, incidents, transit } = snapshot;

    return (
      <section className="dashboard" aria-label="Live operations dashboard">
        {/* Dynamic accessibility alerts for live state changes */}
        <div className="sr-only" aria-live="polite" role="status" aria-atomic="true">
          {liveAnnouncement}
        </div>

        <header className="dashboard-head">
          <h2>{snapshot.venue_name}</h2>
          <div className="phase-badge" aria-label={`Match Phase: ${phaseLabel(match.phase)}`}>
            Phase: {phaseLabel(match.phase)}
          </div>
        </header>

        <div className="dashboard-grid">
          <section className="panel" aria-labelledby="crowd-density-heading">
            <h3 id="crowd-density-heading">Crowd density</h3>
            <div className="zone-grid" role="group" aria-label="Crowd density by zone">
              {crowd.map((c) => (
                <div
                  key={c.zone_id}
                  className="zone-cell"
                  role="progressbar"
                  aria-valuenow={Math.round(c.density * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${c.zone_name} (${c.zone_id}) density`}
                  aria-valuetext={`${Math.round(c.density * 100)}% density, congestion level: ${c.level_label}`}
                  tabIndex={0}
                  title={`${c.zone_name}: ${Math.round(c.density * 100)}% (${c.level_label})`}
                >
                  <div
                    className="zone-bar"
                    style={{
                      height: `${Math.round(c.density * 100)}%`,
                      background: densityColor(c.level_label),
                    }}
                  />
                  <span className="zone-label" aria-hidden="true">
                    {c.zone_id}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel" aria-labelledby="gates-heading">
            <h3 id="gates-heading">Gates</h3>
            <ul className="gate-list">
              {gates.map((g) => (
                <li key={g.gate_id}>
                  <span className="gate-label">{g.label}</span>
                  <span className={`gate-status ${g.status}`} aria-label={`Status: ${g.status}`}>
                    {g.status}
                  </span>
                  <span className="gate-queue">{g.queue_minutes.toFixed(1)} min queue</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel" aria-labelledby="incidents-heading">
            <h3 id="incidents-heading">Active incidents ({incidents.length})</h3>
            {incidents.length === 0 ? (
              <p className="muted">No active incidents.</p>
            ) : (
              <ul className="incident-list">
                {incidents.map((i) => (
                  <li key={i.incident_id} className={`sev-${i.severity}`}>
                    <strong>{i.type.replace(/_/g, " ")}</strong> — {i.location}
                    <span className={`sev-tag ${i.severity}`} aria-label={`Severity: ${i.severity}`}>
                      {i.severity}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel" aria-labelledby="transit-heading">
            <h3 id="transit-heading">Transit</h3>
            <ul className="transit-list">
              {transit.map((t) => (
                <li key={t.node_id}>
                  <span className="transit-name">{t.name}</span>
                  <span className={`congestion ${t.congestion}`} aria-label={`Congestion: ${t.congestion}`}>
                    {t.congestion}
                  </span>
                  <span className="transit-wait">{t.wait_minutes.toFixed(0)} min</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </section>
    );
  },
  (prev, next) => {
    if (prev.snapshot === next.snapshot) return true;
    if (!prev.snapshot || !next.snapshot) return false;
    return JSON.stringify(prev.snapshot) === JSON.stringify(next.snapshot);
  }
);
