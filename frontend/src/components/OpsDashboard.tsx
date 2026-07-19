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
        <div className="ops-dashboard" role="status" aria-live="polite">
          <div className="live-indicator">Loading live state…</div>
        </div>
      );
    }

    const { match, crowd, gates, incidents, transit } = snapshot;

    return (
      <section className="ops-dashboard" aria-label="Live operations dashboard">
        {/* Dynamic accessibility alerts for live state changes */}
        <div className="sr-only" aria-live="polite" role="status" aria-atomic="true">
          {liveAnnouncement}
        </div>

        <header className="dashboard-header">
          <h2>{snapshot.venue_name}</h2>
          <div className="live-indicator" aria-label={`Match Phase: ${phaseLabel(match.phase)}`}>
            Phase: {phaseLabel(match.phase)}
          </div>
        </header>

        <div className="dashboard-grid">
          {/* Crowd Density Card */}
          <section className="stat-card" aria-labelledby="crowd-density-heading">
            <h3 id="crowd-density-heading" className="stat-title">Crowd Density</h3>
            {crowd.map((c) => (
              <div key={c.zone_id} className="density-meter" aria-label={`${c.zone_name} (${c.zone_id}) density`}>
                <div className="density-label">
                  <span>{c.zone_name}</span>
                  <span>{Math.round(c.density * 100)}%</span>
                </div>
                <div 
                  className={`density-bar-bg density-${c.level_label === 'high' ? 'critical' : c.level_label === 'moderate' ? 'warning' : 'safe'}`}
                  role="progressbar"
                  aria-valuenow={Math.round(c.density * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="density-bar-fill" style={{ width: `${Math.round(c.density * 100)}%` }} />
                </div>
              </div>
            ))}
          </section>

          {/* Gates Card */}
          <section className="stat-card" aria-labelledby="gates-heading">
            <h3 id="gates-heading" className="stat-title">Gates & Queues</h3>
            {gates.map((g) => (
              <div key={g.gate_id} className="density-meter">
                <div className="density-label">
                  <span>{g.label} ({g.status})</span>
                  <span>{g.queue_minutes.toFixed(1)}m</span>
                </div>
                <div className={`density-bar-bg density-${g.queue_minutes > 15 ? 'critical' : g.queue_minutes > 5 ? 'warning' : 'safe'}`}>
                  <div className="density-bar-fill" style={{ width: `${Math.min((g.queue_minutes / 30) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </section>

          {/* Incidents Card */}
          <section className="stat-card" aria-labelledby="incidents-heading">
            <h3 id="incidents-heading" className="stat-title">Active Incidents ({incidents.length})</h3>
            {incidents.length === 0 ? (
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>No active incidents.</div>
            ) : (
              <div className="incidents-list">
                {incidents.map((i) => (
                  <div key={i.incident_id} className="incident-item">
                    <div className="incident-header">
                      <span className="incident-type">{i.type.replace(/_/g, " ")}</span>
                      <span className="incident-severity">{i.severity}</span>
                    </div>
                    <span className="incident-location">{i.location}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Transit Card */}
          <section className="stat-card" aria-labelledby="transit-heading">
            <h3 id="transit-heading" className="stat-title">Transit Wait Times</h3>
            {transit.map((t) => (
              <div key={t.node_id} className="density-meter">
                <div className="density-label">
                  <span>{t.name} ({t.congestion})</span>
                  <span>{t.wait_minutes.toFixed(0)}m</span>
                </div>
                <div className={`density-bar-bg density-${t.congestion === 'heavy' ? 'critical' : t.congestion === 'moderate' ? 'warning' : 'safe'}`}>
                  <div className="density-bar-fill" style={{ width: `${Math.min((t.wait_minutes / 60) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
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
