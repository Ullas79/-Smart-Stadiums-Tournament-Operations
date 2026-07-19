import { memo, useEffect, useRef, useState } from "react";
import type { StadiumSnapshot, Role } from "../types";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from "recharts";
import "./OpsDashboard.css";

interface Props {
  snapshot: StadiumSnapshot | null;
  role: Role;
}

function phaseLabel(phase: string): string {
  return phase.replace(/_/g, " ");
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={{ background: "rgba(15, 23, 42, 0.9)", border: "1px solid rgba(148,163,184,0.2)", padding: "0.5rem", borderRadius: "8px", color: "#f8fafc", fontSize: "0.85rem" }}>
        <p style={{ margin: 0, fontWeight: "bold" }}>{data.zone_name}</p>
        <p style={{ margin: "0.2rem 0 0", color: data.color }}>{data.densityPercent}% ({data.level_label})</p>
      </div>
    );
  }
  return null;
};

const triggerChat = (text: string) => {
  window.dispatchEvent(new CustomEvent("send-chat", { detail: text }));
};

export const OpsDashboard = memo(
  function OpsDashboard({ snapshot, role }: Props) {
    const { t } = useTranslation();
    const prevSnapshotRef = useRef<StadiumSnapshot | null>(null);
    const [liveAnnouncement, setLiveAnnouncement] = useState("");

    useEffect(() => {
      if (!snapshot) return;
      const prev = prevSnapshotRef.current;
      if (prev) {
        const alerts: string[] = [];
        snapshot.crowd.forEach((c) => {
          const prevZone = prev.crowd.find((pz) => pz.zone_id === c.zone_id);
          const prevDensity = prevZone ? prevZone.density : 0;
          if (c.density > 0.85 && prevDensity <= 0.85) {
            alerts.push(`Alert: ${c.zone_name} crowd density is critically high at ${Math.round(c.density * 100)}%!`);
            toast.error(`Critical Density: ${c.zone_name}`, { description: `Density reached ${Math.round(c.density * 100)}%` });
          }
        });
        snapshot.incidents.forEach((i) => {
          const prevInc = prev.incidents.find((pi) => pi.incident_id === i.incident_id);
          if (!prevInc) {
            alerts.push(`New active incident: ${i.type.replace(/_/g, " ")} (${i.severity} severity) reported at ${i.location}.`);
            if (i.severity === 'critical') {
              toast.error(`Critical Incident: ${i.type.replace(/_/g, " ")}`, { description: i.location, duration: 8000 });
            } else {
              toast.warning(`New Incident: ${i.type.replace(/_/g, " ")}`, { description: i.location });
            }
          }
        });
        snapshot.gates.forEach((g) => {
          const prevGate = prev.gates.find((pg) => pg.gate_id === g.gate_id);
          if (prevGate && prevGate.status !== g.status) {
            alerts.push(`Gate ${g.label} status changed to ${g.status}.`);
            toast.info(`Gate Status Update`, { description: `Gate ${g.label} is now ${g.status}` });
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
          <div className="live-indicator">{t('loading')}</div>
        </div>
      );
    }

    const { match, crowd, gates, incidents, transit } = snapshot;
    const chartData = crowd.map(c => ({
      ...c,
      densityPercent: Math.round(c.density * 100),
      color: c.level_label === 'high' ? '#ef4444' : c.level_label === 'moderate' ? '#f59e0b' : '#10b981'
    }));

    // Calculate Executive Summary (Organizer only)
    const totalOccupancy = crowd.reduce((sum, c) => sum + c.occupancy, 0);
    const totalCapacity = crowd.reduce((sum, c) => sum + c.capacity, 0);
    const overallDensity = totalCapacity > 0 ? (totalOccupancy / totalCapacity) * 100 : 0;
    
    // Quick Actions based on role
    const quickActions = role === "volunteer" ? [
      { label: "Report Medical Issue", prompt: "I need to report a medical incident in my sector." },
      { label: "Report Spillage", prompt: "There is a spillage blocking a walkway." },
      { label: "Request Gate Backup", prompt: "My gate is getting overcrowded, we need backup." }
    ] : role === "staff" ? [
      { label: "Dispatch Medical", prompt: "Dispatch medical personnel to the active incidents." },
      { label: "Close High-Queue Gate", prompt: "Close the gate with the highest wait time." },
      { label: "Check Transit Nodes", prompt: "What is the status of the transit nodes?" }
    ] : [];

    return (
      <section className="ops-dashboard" aria-label="Live operations dashboard">
        <div className="sr-only" aria-live="polite" role="status" aria-atomic="true">
          {liveAnnouncement}
        </div>

        <header className="dashboard-header">
          <h2>{snapshot.venue_name}</h2>
          <div className="live-indicator" aria-label={`Match Phase: ${phaseLabel(match.phase)}`}>
            {t('phase', { phase: phaseLabel(match.phase) })}
          </div>
        </header>

        <div className="dashboard-grid">
          {role === "organizer" && (
            <section className="stat-card exec-summary" style={{ gridColumn: "1 / -1" }}>
              <div className="exec-stat">
                <span className="exec-label">Global Occupancy</span>
                <span className="exec-value">{overallDensity.toFixed(1)}%</span>
              </div>
              <div className="exec-stat">
                <span className="exec-label">Total Attendance</span>
                <span className="exec-value">{totalOccupancy.toLocaleString()}</span>
              </div>
              <div className="exec-stat">
                <span className="exec-label">Active Incidents</span>
                <span className={`exec-value ${incidents.length > 2 ? 'text-red' : ''}`}>{incidents.length}</span>
              </div>
            </section>
          )}

          {role === "organizer" && (
            <section className="stat-card" aria-labelledby="crowd-density-heading" style={{ gridColumn: "1 / -1", height: "250px" }}>
              <h3 id="crowd-density-heading" className="stat-title">{t('crowdDensity')}</h3>
              <div style={{ flex: 1, minHeight: 0, marginTop: "1rem" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis dataKey="zone_id" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
                    <Bar dataKey="densityPercent" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          <section className="stat-card" aria-labelledby="gates-heading">
            <h3 id="gates-heading" className="stat-title">{t('gates')}</h3>
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

          <section className="stat-card" aria-labelledby="incidents-heading">
            <h3 id="incidents-heading" className="stat-title">{t('activeIncidents', { count: incidents.length })}</h3>
            {incidents.length === 0 ? (
              <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{t('noIncidents')}</div>
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

          {(role === "organizer" || role === "staff") && (
            <section className="stat-card" aria-labelledby="transit-heading">
              <h3 id="transit-heading" className="stat-title">{t('transit')}</h3>
              {transit.map((tItem) => (
                <div key={tItem.node_id} className="density-meter">
                  <div className="density-label">
                    <span>{tItem.name} ({tItem.congestion})</span>
                    <span>{tItem.wait_minutes.toFixed(0)}m</span>
                  </div>
                  <div className={`density-bar-bg density-${tItem.congestion === 'heavy' ? 'critical' : tItem.congestion === 'moderate' ? 'warning' : 'safe'}`}>
                    <div className="density-bar-fill" style={{ width: `${Math.min((tItem.wait_minutes / 60) * 100, 100)}%` }} />
                  </div>
                </div>
              ))}
            </section>
          )}

          {(role === "volunteer" || role === "staff") && (
            <section className="stat-card" aria-labelledby="quick-actions-heading" style={{ gridColumn: role === "volunteer" ? "1 / -1" : "auto" }}>
              <h3 id="quick-actions-heading" className="stat-title">Quick Actions</h3>
              <div className="quick-actions-grid">
                {quickActions.map((action, i) => (
                  <button key={i} className="quick-action-btn" onClick={() => triggerChat(action.prompt)}>
                    {action.label}
                  </button>
                ))}
              </div>
            </section>
          )}
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
