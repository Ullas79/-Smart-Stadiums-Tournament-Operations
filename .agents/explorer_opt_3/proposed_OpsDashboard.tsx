import { memo } from "react";
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
    if (!snapshot) {
      return <div className="dashboard">Loading live state…</div>;
    }
    const { match, crowd, gates, incidents, transit } = snapshot;
    return (
      <section className="dashboard" aria-label="Live operations dashboard">
        <header className="dashboard-head">
          <h2>{snapshot.venue_name}</h2>
          <div className="phase-badge">Phase: {phaseLabel(match.phase)}</div>
        </header>

        <div className="dashboard-grid">
          <div className="panel">
            <h3>Crowd density</h3>
            <div className="zone-grid">
              {crowd.map((c) => (
                <div
                  key={c.zone_id}
                  className="zone-cell"
                  title={`${c.zone_name}: ${Math.round(c.density * 100)}%`}
                  role="progressbar"
                  aria-valuenow={Math.round(c.density * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="zone-bar" style={{ height: `${Math.round(c.density * 100)}%`, background: densityColor(c.level_label) }} />
                  <span className="zone-label">{c.zone_id}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <h3>Gates</h3>
            <ul className="gate-list">
              {gates.map((g) => (
                <li key={g.gate_id}>
                  <span className="gate-label">{g.label}</span>
                  <span className={`gate-status ${g.status}`}>{g.status}</span>
                  <span className="gate-queue">{g.queue_minutes.toFixed(1)} min queue</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h3>Active incidents ({incidents.length})</h3>
            {incidents.length === 0 ? (
              <p className="muted">No active incidents.</p>
            ) : (
              <ul className="incident-list">
                {incidents.map((i) => (
                  <li key={i.incident_id} className={`sev-${i.severity}`}>
                    <strong>{i.type.replace(/_/g, " ")}</strong> — {i.location}
                    <span className={`sev-tag ${i.severity}`}>{i.severity}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h3>Transit</h3>
            <ul className="transit-list">
              {transit.map((t) => (
                <li key={t.node_id}>
                  <span className="transit-name">{t.name}</span>
                  <span className={`congestion ${t.congestion}`}>{t.congestion}</span>
                  <span className="transit-wait">{t.wait_minutes.toFixed(0)} min</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    );
  },
  (prev, next) => {
    if (prev.snapshot === next.snapshot) return true;
    if (!prev.snapshot || !next.snapshot) return false;
    // Deep comparison check using JSON stringification to prevent rendering when fetched snapshot is unchanged
    return JSON.stringify(prev.snapshot) === JSON.stringify(next.snapshot);
  }
);
